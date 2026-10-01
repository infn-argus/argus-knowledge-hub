"""Which hardware a control channel drives (asset-model-revision §6 `acts on`, §18.1, D12).

A control configuration knows its channels (Control Devices), the IOC that
provides each and the endpoint it is reached through; it does not say which
physical unit a channel drives. An inventory knows its units and does not say
which channel drives them. Two pieces of evidence join them, and nothing else
is guessed:

- the naming convention: a channel and its unit carry the same zone, function
  code and number in different spellings (`FI33TRB01` and `FI33-V-PMP-TRB-001`,
  `FI8-HMN-02` and `FI8-W-MOT-HMN-002`, `FI8-CAM-06` and `FI8-B-CAM-VIS-006`);
- the network: an Ethernet instrument's address is its own (`cceuapscam14` is the
  camera whose Address Record or `ip`/`hostname` says so).

Each unique match becomes an *inferred* `acts on` claim (Control Device → unit)
in the workspace's binding stream, under a versioned rule, with its evidence. An
inferred relation is advisory under the default policy, so it is **proposed**,
not effective: it waits in the review queue for Controls (who own channel-to-
hardware mappings) to confirm it, one by one or in bulk. An Ethernet instrument's
Access Point is likewise proposed as `implemented by` the instrument.

The design points `acts on` at a Position, and at a unit only while it has no
position (§6). Until a workspace's records are split into positions and units
(the legacy migration, §12), they point at the unit; the claims move with that
migration's relation rewrites.

`drives` (IOC → the unit it is) is derived, never stated: an IOC drives the units
its devices act on, or the unit realizing the position a device acts on.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.models.asset import Asset, Relation

RULE_TAG = "bind.control.tag/1"
RULE_HOST = "bind.control.host/1"
EQUIPMENT_ROOT = "Asset"
NOT_DRIVEN = {"Equipment Port", "Cable Run"}
ENDPOINT_KINDS = {"Camera", "Instrument"}          # endpoints that are the instrument's own network socket


def parse_tag(name: Optional[str]) -> Optional[tuple]:
    """(zone, function codes, number) of a tag in any of its spellings, or None:
    FI33-V-PMP-TRB-001 → (FI33, {V, PMP, TRB}, 1); FI33TRB01 → (FI33, {TRB}, 1)."""
    n = (name or "").upper().strip().replace("_", "-")
    m = re.match(r"^([A-Z]+\d+)(.*?)(\d{1,3})$", n)
    if not m:
        return None
    zone, middle, number = m.group(1), m.group(2), int(m.group(3))
    codes = {t for t in re.split(r"[^A-Z]+", middle) if t}
    return (zone, codes, number) if codes else None


def _host(value) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().split(".")[0].lower()


def _equipment(db: Session, workspace_id: str) -> list[Asset]:
    out = []
    for a in db.scalars(select(Asset).where(Asset.workspace_id == workspace_id, Asset.deleted_at.is_(None),
                                            Asset.record_status.notin_(("Retired", "Merged")))):
        lineage = engine._type_lineage(db, a)
        if EQUIPMENT_ROOT in lineage and not (set(lineage) & NOT_DRIVEN):
            out.append(a)
    return out


def _hosts_of(db: Session, unit: Asset) -> set[str]:
    """The names a unit answers to on the network: its own fields and its Address Records."""
    a = unit.attributes or {}
    hosts = {_host(a.get(k)) for k in ("hostname", "fqdn", "ip")}
    for rel in db.scalars(select(Relation).where(Relation.from_asset_uid == unit.uid,
                                                 Relation.relation_type == "described by")):
        rec = db.get(Asset, rel.to_asset_uid)
        if rec is not None:
            hosts |= {_host((rec.attributes or {}).get(k)) for k in ("hostname", "fqdn", "ip")}
    return {h for h in hosts if h}


class InventoryMatcher:
    """A workspace's inventory units by tag and network name, for an import to link a channel to the unit
    that is already recorded instead of inferring a second one. Units an import itself inferred
    (`argus_source` = that import) are not inventory."""

    def __init__(self, db: Session, workspace_id: str, exclude_source: Optional[str] = None):
        self.by_tag: dict[tuple, list[tuple]] = defaultdict(list)
        self.by_host: dict[str, list[Asset]] = defaultdict(list)
        for u in _equipment(db, workspace_id):
            if exclude_source and (u.attributes or {}).get("argus_source") == exclude_source:
                continue
            p = parse_tag(u.name)
            if p:
                self.by_tag[(p[0], p[2])].append((p[1], u))
            for h in _hosts_of(db, u):
                self.by_host[h].append(u)

    def match(self, name: str, pv: Optional[str] = None, address: Optional[str] = None) -> Optional[Asset]:
        """The one unit the channel's tag or network address names, or None (none, or more than one)."""
        for candidate in [name] + ([str(pv).split(":")[-1]] if pv else []):
            p = parse_tag(candidate)
            hits = [u for codes, u in self.by_tag.get((p[0], p[2]), []) if p[1] & codes] if p else []
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                return None
        hosts = self.by_host.get(_host(address), []) if address else []
        return hosts[0] if len(hosts) == 1 else None


def _claim(subject: str, predicate: str, target: str, rule: str, evidence: dict, confidence: float) -> dict:
    return {"source_ref": f"uid:{subject}", "predicate": predicate, "value": {"ref": f"uid:{target}"},
            "rule_id": rule, "method": "inferred", "evidence": evidence, "confidence": confidence}


def propose(db: Session, workspace_id: str) -> dict:
    """Propose `acts on` (and `implemented by` for Ethernet instruments) for every channel of the workspace
    that does not act on anything yet. A re-run replaces the previous proposals: one no longer supported
    is withdrawn, one already confirmed or rejected stays decided."""
    devices = [d for d in db.scalars(select(Asset).where(Asset.workspace_id == workspace_id,
                                                         Asset.type == "Control Device",
                                                         Asset.record_status.notin_(("Retired", "Merged"))))]
    units = _equipment(db, workspace_id)
    by_tag: dict[tuple, list[tuple]] = defaultdict(list)
    by_host: dict[str, list[Asset]] = defaultdict(list)
    for u in units:
        p = parse_tag(u.name)
        if p:
            by_tag[(p[0], p[2])].append((p[1], u))
        for h in _hosts_of(db, u):
            by_host[h].append(u)
    acting = set(db.scalars(select(Relation.from_asset_uid).where(Relation.relation_type == "acts on",
                                                                  Relation.workspace_id == workspace_id)))

    claims, report = [], {"proposed": 0, "by_tag": 0, "by_host": 0, "already_bound": 0,
                          "ambiguous": [], "unmatched": []}
    for d in sorted(devices, key=lambda x: x.name):
        a = d.attributes or {}
        host = _host(a.get("address"))
        names = [d.name] + ([str(a["pv"]).split(":")[-1]] if a.get("pv") else [])
        tag_hits: list[Asset] = []
        for name in names:
            p = parse_tag(name)
            if p:
                tag_hits = [u for codes, u in by_tag.get((p[0], p[2]), []) if p[1] & codes]
                if tag_hits:
                    break
        host_hits = by_host.get(host, []) if host else []
        if len(tag_hits) == 1:
            unit = tag_hits[0]
            also_host = unit in host_hits
            evidence = {"device": d.name, "pv": a.get("pv"), "unit": unit.name,
                        "matched_on": "zone, function code and number" + (" and network address" if also_host else "")}
            confidence, rule = (0.95 if also_host else 0.9), RULE_TAG
            report["by_tag"] += 1
        elif len(host_hits) == 1 and not tag_hits:
            unit = host_hits[0]
            evidence = {"device": d.name, "address": a.get("address"), "unit": unit.name,
                        "matched_on": "network address"}
            confidence, rule = 0.85, RULE_HOST
            report["by_host"] += 1
        else:
            candidates = tag_hits or host_hits
            entry = {"device": d.name, "uid": d.uid, "candidates": [{"uid": u.uid, "name": u.name, "type": u.type}
                                                                    for u in candidates[:6]]}
            (report["ambiguous"] if candidates else report["unmatched"]).append(entry)
            continue
        if d.uid in acting:
            report["already_bound"] += 1
        claims.append(_claim(d.uid, "rel:acts on", unit.uid, rule, evidence, confidence))

    # An Ethernet instrument's Access Point is the instrument's own socket.
    for ap in db.scalars(select(Asset).where(Asset.workspace_id == workspace_id, Asset.type == "Access Point",
                                             Asset.record_status.notin_(("Retired", "Merged")))):
        a = ap.attributes or {}
        if a.get("endpoint_kind") not in ENDPOINT_KINDS:
            continue
        hits = {u.uid: u for h in {_host(a.get(k)) for k in ("hostname", "fqdn", "address", "ip")} - {None}
                for u in by_host.get(h, [])}
        if len(hits) == 1:
            unit = next(iter(hits.values()))
            claims.append(_claim(ap.uid, "rel:implemented by", unit.uid, RULE_HOST,
                                 {"access_point": ap.name, "unit": unit.name, "matched_on": "network address"}, 0.85))

    report["proposed"] = len(claims)
    content = engine.canonical(sorted(claims, key=engine.canonical)).encode()
    digest = hashlib.sha256(content).hexdigest()
    stream = engine.register_stream(db, f"bind:{workspace_id}", workspace_id, "resolver")
    from app.models.ledger import SourceRevision
    latest = db.scalar(select(SourceRevision.revision).where(SourceRevision.stream_id == stream.id)
                       .order_by(SourceRevision.number.desc()).limit(1))
    if latest != digest[:12]:                       # the same proposals as last time: nothing to ingest
        engine.ingest(db, stream.id, revision=digest[:12], content=content, observed_at=engine.now(),
                      parser="resolved", cause="control binding")
    report["stream"] = stream.id
    return report


def proposals(db: Session, workspace_id: str) -> list[dict]:
    """The binding claims still waiting for a person, with their evidence."""
    from app.models.ledger import Claim, FactState
    out = []
    for f in db.scalars(select(FactState).where(FactState.status == "proposed",
                                                FactState.contributor.like("claim:%"))):
        claim = db.get(Claim, f.contributor[6:])
        if claim is None or claim.rule_id not in (RULE_TAG, RULE_HOST) or not claim.stream_id.startswith("bind:"):
            continue
        subject = db.get(Asset, f.subject_uid)
        if subject is None or subject.workspace_id != workspace_id:
            continue
        target = db.get(Asset, engine.resolve_ref(db, (claim.value or {}).get("ref", "")) or "")
        from app.models.ledger import ClaimEvent
        event = db.scalar(select(ClaimEvent).where(ClaimEvent.claim_id == claim.claim_id,
                                                   ClaimEvent.kind.in_(("appeared", "evidence_changed")))
                          .order_by(ClaimEvent.seq.desc()).limit(1))
        out.append({"claim_id": claim.claim_id, "subject": {"uid": subject.uid, "name": subject.name,
                                                            "type": subject.type},
                    "predicate": claim.predicate[4:], "target": {"uid": target.uid, "name": target.name,
                                                                "type": target.type} if target else None,
                    "rule": claim.rule_id, "confidence": event.confidence if event else None,
                    "evidence": event.evidence if event else None})
    return sorted(out, key=lambda p: (-(p["confidence"] or 0), p["subject"]["name"]))


def decide(db: Session, workspace_id: str, actor: str, claim_ids: list[str], accept: bool,
           reason: Optional[str] = None) -> int:
    """Confirm (or reject) binding proposals, as one ledger batch."""
    if not claim_ids:
        return 0
    batch = [{"kind": "accept" if accept else "reject", "target": {"claim_id": cid},
              "reason": reason or ("control binding confirmed" if accept else "control binding rejected")}
             for cid in claim_ids]
    engine.apply_decisions(db, workspace_id, actor, batch)
    return len(batch)


# --------------------------------------------------------------------------- B: drives

def derive_drives(db: Session, workspace_ids=None) -> dict:
    """Derived `drives` edges: IOC → each unit one of its devices acts on, or the unit realizing the position
    a device acts on. They follow `provided by`, `acts on` and `realized by` and are never stated."""
    rq = select(Relation).where(Relation.derivation == "derived", Relation.relation_type == "drives")
    dq = select(Relation).where(Relation.relation_type == "provided by")
    if workspace_ids is not None:
        ids = list(set(workspace_ids))
        rq = rq.where(Relation.workspace_id.in_(ids))
        dq = dq.where(Relation.workspace_id.in_(ids))
    wanted: set[tuple] = set()
    for provided in db.scalars(dq):
        device, ioc = provided.from_asset_uid, provided.to_asset_uid
        ioc_rec = db.get(Asset, ioc)
        if ioc_rec is None or ioc_rec.type != "IOC":
            continue
        for acts in db.scalars(select(Relation).where(Relation.from_asset_uid == device,
                                                      Relation.relation_type == "acts on")):
            target = db.get(Asset, acts.to_asset_uid)
            if target is None:
                continue
            realized = list(db.scalars(select(Relation.to_asset_uid).where(
                Relation.from_asset_uid == target.uid, Relation.relation_type == "realized by")))
            for unit in realized or [target.uid]:
                wanted.add((ioc, unit, ioc_rec.workspace_id))
    current = {(r.from_asset_uid, r.to_asset_uid): r for r in db.scalars(rq)}
    keys = {(i, u) for i, u, _ in wanted}
    for key, row in current.items():
        if key not in keys:
            db.delete(row)
    for ioc, unit, ws in wanted:
        if (ioc, unit) not in current:
            db.add(Relation(workspace_id=ws, from_asset_uid=ioc, to_asset_uid=unit, relation_type="drives",
                            derivation="derived", rule="drives/1"))
    db.flush()
    return {"drives": len(keys)}
