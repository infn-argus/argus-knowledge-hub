"""Sources for the vertical slice: what a stream's bytes say, as claims.

* `epik8s-slice` — IOCs and devices of a values.yaml, with the inference rule
  `infer.vac.sip/1` (a vacuum channel named …SIP… is an ion-pump position).
  It creates **positions**, never physical assets (§4.2).
* `insight-fixture` — equipment exported from Jira Insight (migration source,
  §16): one object per entry, identified by its immutable objectId.
* `resolved` — the resolver's own output (installation proposals from
  `asset:` URLs, rule `resolve.asset_url/1`), ingested like any other stream.

Every rule has a semantic id that is part of claim identity (§7.9).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Callable

import yaml
from sqlalchemy import String, cast, select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.ledger.engine import ParsedClaim, canonical
from app.models.ledger import Claim, ClaimEvent, JobRun, LedgerStream, SourceRevision, StreamHead

# The rule catalogue: semantic id -> meaning and output signature (§7.9).
RULES = {
    "epik8s.ioc/1": {"meaning": "an IOC entry is a control-plane IOC record",
                     "outputs": ["exists:IOC", "attr:template"]},
    "epik8s.device/1": {"meaning": "a device of an IOC is a Control Device",
                        "outputs": ["exists:Control Device", "attr:channel", "attr:zones", "attr:inventory_url",
                                    "rel:provided by"]},
    "infer.vac.sip/1": {"meaning": "a vacuum channel whose name contains SIP or IONP denotes an Equipment "
                                   "Position of class Ion Pump, which the channel acts on",
                        "outputs": ["exists:Equipment Position", "attr:position_class", "rel:acts on"]},
    "insight.object/1": {"meaning": "an Insight object is a piece of equipment",
                         "outputs": ["exists:*", "attr:*"]},
    "resolve.asset_url/1": {"meaning": "a device's asset: URL naming one inventory object, on a device acting on "
                                       "exactly one position, proposes an Installation of that object there",
                            "outputs": ["exists:Installation", "rel:installed at", "rel:installation of",
                                        "attr:valid_from"]},
}


@dataclass(frozen=True)
class Parser:
    version: str
    impl_version: str
    parse: Callable[[bytes, LedgerStream], list[ParsedClaim]]


def _ioc_entries(iocs) -> list[dict]:
    if isinstance(iocs, dict):
        return [{"name": k, **v} if isinstance(v, dict) else {"name": k} for k, v in iocs.items()]
    return [e for e in iocs or [] if isinstance(e, dict)]


def _zones(value) -> list[str]:
    if value is None:
        return []
    return [str(z) for z in (value if isinstance(value, list) else [value])]


def parse_epik8s(content: bytes, stream: LedgerStream) -> list[ParsedClaim]:
    values = yaml.safe_load(content) or {}
    fac = str(values.get("beamline") or stream.facility or "X").upper()
    iocs = _ioc_entries((values.get("epicsConfiguration") or {}).get("iocs"))
    out: list[ParsedClaim] = []
    for ioc in iocs:
        name = str(ioc["name"])
        ioc_ref = f"epik8s:{fac}:ioc:{name}"
        path = f"epicsConfiguration.iocs.{name}"
        out.append(ParsedClaim(ioc_ref, "exists", {"type": "IOC", "key": f"{fac}:IOC:{name}", "name": name},
                               rule_id="epik8s.ioc/1", evidence={"path": path}))
        if ioc.get("template"):
            out.append(ParsedClaim(ioc_ref, "attr:template", str(ioc["template"]), rule_id="epik8s.ioc/1",
                                   evidence={"path": f"{path}.template"}))
        is_vac = "vac" in str(ioc.get("devgroup") or "").lower() or "vac" in str(ioc.get("template") or "").lower()
        for i, dev in enumerate(ioc.get("devices") or []):
            if not isinstance(dev, dict) or not dev.get("name"):
                continue
            dname = str(dev["name"])
            dref = f"epik8s:{fac}:dev:{name}/{dname}"
            dpath = f"{path}.devices[{i}]"
            out.append(ParsedClaim(dref, "exists", {"type": "Control Device", "key": f"{fac}:DEV:{name}:{dname}",
                                                    "name": dname}, rule_id="epik8s.device/1",
                                   evidence={"path": dpath}))
            out.append(ParsedClaim(dref, "rel:provided by", {"ref": ioc_ref}, rule_id="epik8s.device/1",
                                   evidence={"path": dpath}))
            if dev.get("channel") is not None:
                out.append(ParsedClaim(dref, "attr:channel", dev["channel"], rule_id="epik8s.device/1",
                                       evidence={"path": f"{dpath}.channel"}))
            for zone in _zones(dev.get("zones", ioc.get("zones"))):
                out.append(ParsedClaim(dref, "attr:zones", zone, member=json.dumps(zone), rule_id="epik8s.device/1",
                                       evidence={"path": f"{dpath}.zones"}))
            if dev.get("asset"):
                out.append(ParsedClaim(dref, "attr:inventory_url", str(dev["asset"]), rule_id="epik8s.device/1",
                                       evidence={"path": f"{dpath}.asset"}))
            if is_vac and ("SIP" in dname.upper() or "IONP" in dname.upper()):
                pref = f"infer:{fac}:pos:{dname}"
                ev = {"devgroup": ioc.get("devgroup"), "template": ioc.get("template"), "name_token": "SIP",
                      "path": dpath}
                out.append(ParsedClaim(pref, "exists", {"type": "Equipment Position", "key": f"{fac}:POS:{dname}",
                                                        "name": dname}, method="inferred", rule_id="infer.vac.sip/1",
                                       evidence=ev, confidence=0.9))
                out.append(ParsedClaim(pref, "attr:position_class", "Ion Pump", method="inferred",
                                       rule_id="infer.vac.sip/1", evidence=ev, confidence=0.9))
                out.append(ParsedClaim(dref, "rel:acts on", {"ref": pref}, method="inferred",
                                       rule_id="infer.vac.sip/1", evidence=ev, confidence=0.9))
    return out


def parse_insight(content: bytes, stream: LedgerStream) -> list[ParsedClaim]:
    data = json.loads(content)
    out: list[ParsedClaim] = []
    for obj in data.get("objects", []):
        ref = f"insight:object:{obj['objectId']}"
        out.append(ParsedClaim(ref, "exists", {"type": obj["type"], "key": obj["key"], "name": obj.get("name")},
                               rule_id="insight.object/1", evidence={"objectId": obj["objectId"]}))
        for k, v in (obj.get("attributes") or {}).items():
            out.append(ParsedClaim(ref, f"attr:{k}", v, rule_id="insight.object/1",
                                   evidence={"objectId": obj["objectId"], "field": k}))
    return out


def parse_resolved(content: bytes, stream: LedgerStream) -> list[ParsedClaim]:
    return [ParsedClaim(**c) for c in json.loads(content)]


PARSERS = {
    "epik8s-slice": Parser("epik8s-slice/1+infer.vac.sip/1", "slice-impl/1", parse_epik8s),
    "insight-fixture": Parser("insight-fixture/1", "slice-impl/1", parse_insight),
    "resolved": Parser("resolved/1", "resolver/1", parse_resolved),
}

OBJECT_ID = re.compile(r"objectId=(\d+)")


def _published_claims(db: Session, stream_id: str) -> list[Claim]:
    head = db.get(StreamHead, stream_id)
    present = engine._presence(db, stream_id, head.published_number if head else 0)
    return [db.get(Claim, cid) for cid in present]


def workspaces_referencing(db: Session, changed: list) -> set[str]:
    """Workspaces whose configuration names one of these inventory objects in
    an `asset:` URL."""
    object_ids = {c.source_ref.rsplit(":", 1)[-1] for c in changed
                  if c is not None and c.source_ref.startswith("insight:object:")}
    out: set[str] = set()
    for oid in object_ids:
        for c in db.scalars(select(Claim).where(Claim.predicate == "attr:inventory_url",
                                                cast(Claim.value, String).like(f"%objectId={oid}%"))):
            stream = db.get(LedgerStream, c.stream_id)
            if stream is not None:
                out.add(stream.workspace_id)
    return out


def resolve_installations(db: Session, workspace_id: str) -> dict:
    """The resolve stage for one workspace (§8.4): an `asset:` URL on a device
    that names one inventory object, where the device acts on exactly one
    position, becomes an Installation *proposal*. Reruns whenever its inputs
    change (config claims, inventory bindings), even if no config bytes did."""
    streams = [s for s in db.scalars(select(LedgerStream).where(LedgerStream.workspace_id == workspace_id))
               if s.kind == "epik8s"]
    urls: dict[str, tuple[str, str]] = {}
    acts: dict[str, set] = {}
    for s in streams:
        for c in _published_claims(db, s.id):
            if c.predicate == "attr:inventory_url" and (m := OBJECT_ID.search(str(c.value))):
                urls[c.source_ref] = (m.group(1), c.claim_id)
            elif c.predicate == "rel:acts on" and c.polarity == "present":
                acts.setdefault(c.source_ref, set()).add(c.value["ref"])
    proposals: list[dict] = []
    inputs = []
    for dev_ref, (object_id, url_claim) in sorted(urls.items()):
        equipment_ref = f"insight:object:{object_id}"
        equipment_uid = engine.resolve_ref(db, equipment_ref)
        positions = sorted(acts.get(dev_ref, set()))
        inputs.append([dev_ref, object_id, url_claim, equipment_uid, positions])
        if equipment_uid is None or len(positions) != 1:
            continue
        pos_ref = positions[0]
        ref = f"resolve:inst:{pos_ref}|{equipment_ref}"
        appeared = db.scalar(select(ClaimEvent).where(ClaimEvent.claim_id == url_claim, ClaimEvent.kind == "appeared")
                             .order_by(ClaimEvent.seq).limit(1))
        rev = db.get(SourceRevision, appeared.revision_id) if appeared else None
        bound = (rev.observed_at if rev else engine.now()).isoformat()
        base = {"rule_id": "resolve.asset_url/1", "method": "resolved", "derived_from": [url_claim],
                "evidence": {"device": dev_ref, "objectId": object_id}, "confidence": 0.9}
        proposals += [
            {"source_ref": ref, "predicate": "exists", "value": {"type": "Installation"}, **base},
            {"source_ref": ref, "predicate": "rel:installed at", "value": {"ref": pos_ref}, **base},
            {"source_ref": ref, "predicate": "rel:installation of", "value": {"ref": equipment_ref}, **base},
            # The unit was there before these records began; the bound is the
            # first observation of the evidence, not an exact installation date.
            {"source_ref": ref, "predicate": "attr:valid_from",
             "value": {"kind": "before_records", "bound": bound}, **base},
        ]
    digest = hashlib.sha256(canonical(inputs).encode()).hexdigest()
    last = db.scalar(select(JobRun).where(JobRun.stage == "resolve", JobRun.scope == workspace_id)
                     .order_by(JobRun.id.desc()).limit(1))
    if last is not None and last.input_digest == digest:
        db.add(JobRun(stage="resolve", stage_version="resolver/1", scope=workspace_id, input_digest=digest,
                      status="skipped", counts={}, at=engine.now()))
        db.flush()
        return {"status": "skipped"}
    db.add(JobRun(stage="resolve", stage_version="resolver/1", scope=workspace_id, input_digest=digest,
                  status="ran", counts={"proposals": len(proposals) // 4}, at=engine.now()))
    db.flush()
    stream = engine.register_stream(db, f"resolve:{workspace_id}", workspace_id, "resolver",
                                    may_create=["Installation"])
    engine.ingest(db, stream.id, revision=digest[:12], content=canonical(proposals).encode(),
                  observed_at=engine.now(), parser="resolved", cause="resolve")
    return {"status": "ran", "proposals": len(proposals) // 4}
