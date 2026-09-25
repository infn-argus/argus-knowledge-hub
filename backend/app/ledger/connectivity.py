"""Access Points and port mapping (asset-model-revision §9.2, §9.3).

An Access Point is the endpoint as a configuration names it: an opaque
`AP-<ULID>` record whose address is an attribute. Its assignment to a
position is written once (I-AP-2). When a source names the same address for
a different position, the old Access Point retires with a successor and a new
one takes the address, in one batch; the handover lies somewhere between the
previous and the new observation, and is stored as exactly that range.

Port mapping runs in the derive stage: a Bus Segment attaches to a port of
the unit installed where its path's Access Point is assigned, only when
exactly one port matches on identity and every hard compatibility check
passes, from registry-backed facts. Everything else is a review item.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine, temporal
from app.ledger.engine import (ACCESS_POINT, InvariantError, LedgerError, ParsedClaim, canonical, now)
from app.models.asset import Asset, Relation
from app.models.ledger import Claim, Conflict, ConflictEvent, FactState, IdentityBinding, LedgerStream, RecordEvent

BUS_SEGMENT = "Bus Segment"
EQUIPMENT_PORT = "Equipment Port"
PORT_CONFLICTS = ("port_mapping_unresolved", "port_confirmation_required", "port_map_invalid")
PORT_RULE = "port-match/1"
REGISTRY_KINDS = {"it-registry"}
# A configured kind is compatible with the kinds a requirement may name.
KIND_COMPATIBLE = {"RS-485-4w": {"RS-485-4w", "RS-422"}}


# --------------------------------------------------------------------------- helpers

def edge_target(db: Session, uid: str, rel: str) -> Optional[str]:
    return db.scalar(select(Relation.to_asset_uid).where(
        Relation.from_asset_uid == uid, Relation.relation_type == rel, Relation.derivation == "ledger").limit(1))


def edge_sources(db: Session, rel: str, uid: str) -> list[str]:
    return list(db.scalars(select(Relation.from_asset_uid).where(
        Relation.to_asset_uid == uid, Relation.relation_type == rel, Relation.derivation == "ledger")))


def system_stream(db: Session, workspace_id: str) -> LedgerStream:
    """Facts the pipeline itself establishes (service intervals, successors).
    They are claims like any other, so a person's confirmation outranks them."""
    return engine.register_stream(db, f"system:{workspace_id}", workspace_id, "system")


def _range(earliest, latest) -> dict:
    return {"kind": "range", "earliest": temporal.parse_instant(earliest).isoformat(),
            "latest": temporal.parse_instant(latest).isoformat()}


def _has_claim(db: Session, stream_id: str, uid: str, predicate: str) -> bool:
    return db.scalar(select(Claim.claim_id).where(Claim.stream_id == stream_id, Claim.source_ref == f"uid:{uid}",
                                                  Claim.predicate == predicate).limit(1)) is not None


# --------------------------------------------------------------------------- Access Points (§9.2)

def reconcile_access_points(db: Session, stream: LedgerStream, before: Iterable[str], after: Iterable[str],
                            previous_observed: Optional[datetime], observed: datetime, cause: str) -> set[str]:
    """Runs when a revision publishes, after records exist and before they
    are projected. Returns the uids whose projection it changed."""
    before, after = set(before), set(after)
    sys = system_stream(db, stream.workspace_id)
    touched: set[str] = set()
    handover = _range(previous_observed or observed, observed)
    for cid in sorted(after):
        c = db.get(Claim, cid)
        if c.predicate != "rel:assigned to" or c.polarity != "present":
            continue
        ap_uid = engine.resolve_ref(db, c.source_ref)
        ap = db.get(Asset, ap_uid) if ap_uid else None
        position = engine.resolve_ref(db, (c.value or {}).get("ref", ""))
        if ap is None or ap.type != ACCESS_POINT or position is None:
            continue
        current = edge_target(db, ap.uid, "assigned to")
        if current is not None and current != position:
            touched |= reassign(db, ap, position, source_ref=c.source_ref, handover=handover,
                                actor="system", cause=cause)
    # First observation: in service since before the records began (§9.2).
    for cid in sorted(after - before):
        c = db.get(Claim, cid)
        if c.predicate != "exists" or not isinstance(c.value, dict) or c.value.get("type") != ACCESS_POINT:
            continue
        uid = engine.resolve_ref(db, c.source_ref)
        if uid and not _has_claim(db, sys.id, uid, "attr:in_service_from"):
            engine.add_manual_claims(db, sys, [ParsedClaim(
                f"uid:{uid}", "attr:in_service_from", {"kind": "before_records", "bound": observed.isoformat()},
                method="reconciled")], cause=cause)
            touched.add(uid)
    # Retirement without a successor: the address left the configuration.
    for cid in sorted(before - after):
        c = db.get(Claim, cid)
        if c.predicate != "exists" or not isinstance(c.value, dict) or c.value.get("type") != ACCESS_POINT:
            continue
        if any(db.get(Claim, x).source_ref == c.source_ref and db.get(Claim, x).predicate == "exists" for x in after):
            continue
        uid = engine.resolve_ref(db, c.source_ref)
        if uid and not _has_claim(db, sys.id, uid, "attr:in_service_until"):
            engine.add_manual_claims(db, sys, [ParsedClaim(f"uid:{uid}", "attr:in_service_until", handover,
                                                           method="reconciled")], cause=cause)
            touched.add(uid)
    return touched


def reassign(db: Session, old: Asset, position_uid: str, *, handover: dict, actor: str, cause: str,
             source_ref: Optional[str] = None) -> set[str]:
    """The reassignment batch (§9.2): the old Access Point keeps what it was
    and retires with a successor; a new one takes the address at the new
    position; the source ref moves to the new one. Returns touched uids."""
    if old.record_status == "Retired":
        raise LedgerError("a retired Access Point cannot be reassigned")
    old_position = edge_target(db, old.uid, "assigned to")
    attrs = old.attributes or {}
    address = attrs.get("address")
    sys = system_stream(db, old.workspace_id)
    schema = engine.ensure_type(db, old.workspace_id, ACCESS_POINT)
    new = Asset(uid=str(uuid.uuid4()), workspace_id=old.workspace_id, schema_uid=schema.uid,
                key=f"AP-{engine.ulid()}", name=old.name, type=ACCESS_POINT, attributes={}, record_status="Active")
    db.add(new)
    db.flush()
    db.add(RecordEvent(uid=new.uid, kind="created", after={"key": new.key, "type": ACCESS_POINT,
                                                           "predecessor": old.uid}, cause=cause, at=now()))
    kw = {"method": "reconciled"}
    old_ref = f"uid:{old.uid}"
    claims = [ParsedClaim(old_ref, "exists", {"type": ACCESS_POINT}, polarity="absent", **kw),
              ParsedClaim(old_ref, "attr:address", address, **kw),
              ParsedClaim(old_ref, "attr:in_service_until", handover, **kw),
              ParsedClaim(old_ref, "attr:successor", new.uid, **kw)]
    if old_position:
        claims.append(ParsedClaim(old_ref, "rel:assigned to", {"ref": f"uid:{old_position}"}, **kw))
    if attrs.get("in_service_from"):
        claims.append(ParsedClaim(old_ref, "attr:in_service_from", attrs["in_service_from"], **kw))
    new_ref = f"uid:{new.uid}"
    claims.append(ParsedClaim(new_ref, "attr:in_service_from", handover, **kw))
    if source_ref is None:
        # A person moved it: nothing states the new one but this batch.
        claims += [ParsedClaim(new_ref, "exists", {"type": ACCESS_POINT}, **kw),
                   ParsedClaim(new_ref, "attr:address", address, **kw),
                   ParsedClaim(new_ref, "rel:assigned to", {"ref": f"uid:{position_uid}"}, **kw)]
    engine.add_manual_claims(db, sys, claims, cause=cause)
    touched = {old.uid, new.uid}
    if source_ref is None:
        # A person's move: every source ref of the old one follows the address.
        refs = [b.source_ref for b in db.scalars(select(IdentityBinding).where(IdentityBinding.uid == old.uid))
                if not b.source_ref.startswith("uid:")]
    else:
        refs = [source_ref]
    for ref in refs:
        engine.bind(db, ref, new.uid, f"rebound: reassignment ({cause})")
        # Whatever pointed at the endpoint (a path's `enters at`) now resolves to the new one.
        for c in db.scalars(select(Claim).where(Claim.member == ref)):
            uid = engine.resolve_ref(db, c.source_ref)
            if uid:
                touched.add(uid)
    db.add(RecordEvent(uid=old.uid, kind="successor", before={"position": old_position},
                       after={"successor": new.uid, "position": position_uid}, cause=cause, at=now()))
    engine._record_decision(db, "reassign", actor, old.workspace_id, subject_uid=old.uid,
                            target={"successor": new.uid, "from": old_position, "to": position_uid},
                            value=handover, reason=cause)
    db.flush()
    return touched


def access_point_view(db: Session, ap: Asset) -> dict:
    a = ap.attributes or {}
    iv = temporal.interval(a.get("in_service_from"), a.get("in_service_until"))
    return {"uid": ap.uid, "key": ap.key, "address": a.get("address"), "record_status": ap.record_status,
            "position_uid": edge_target(db, ap.uid, "assigned to"), "in_service_from": a.get("in_service_from"),
            "in_service_until": a.get("in_service_until"), "successor": a.get("successor"),
            "workspace_id": ap.workspace_id, "interval": iv}


def access_points(db: Session, workspace_id: str, address: Optional[str] = None) -> list[dict]:
    from app.ledger.sources import normalize_address
    wanted = normalize_address(address) if address else None
    out = [access_point_view(db, ap) for ap in db.scalars(select(Asset).where(
        Asset.workspace_id == workspace_id, Asset.type == ACCESS_POINT))]
    if wanted:
        out = [v for v in out if v["address"] == wanted]
    return sorted(out, key=lambda v: (v["address"] or "", v["interval"].start.earliest))


def who_used(db: Session, workspace_id: str, address: str, t) -> list[dict]:
    """Which position and equipment used address X at time T (§9.2 query).
    Several rows appear only around an uncertain handover, each with its
    certainty."""
    t = temporal.parse_instant(t)
    rows = []
    for ap in access_points(db, workspace_id, address):
        c = temporal.covers(ap["interval"], t)
        if c == "none":
            continue
        hits = engine.installations_at(db, t, position_uid=ap["position_uid"]) if ap["position_uid"] else []
        if not hits:
            rows.append({"access_point_uid": ap["uid"], "position_uid": ap["position_uid"], "asset_uid": None,
                         "certainty": c})
        for i in hits:
            rows.append({"access_point_uid": ap["uid"], "position_uid": ap["position_uid"],
                         "asset_uid": i["asset_uid"], "installation_uid": i["uid"],
                         "certainty": temporal.combine(c, i["certainty"])})
    return rows


def check_assignment_decision(record: Asset, predicate: str, db: Session) -> None:
    """I-AP-2: `assigned to` is written once; changing it is a reassignment."""
    if record.type == ACCESS_POINT and predicate == "rel:assigned to" \
            and edge_target(db, record.uid, "assigned to") is not None:
        raise InvariantError("I-AP-2", "an Access Point's assignment is written once; reassign it instead, "
                                       "which retires it with a successor")


def validate_access_points(db: Session, subjects: Iterable[str]) -> None:
    """I-AP-1 and I-AP-3 for the addresses of these Access Points."""
    seen = set()
    for uid in subjects:
        ap = db.get(Asset, uid)
        if ap is None or ap.type != ACCESS_POINT:
            continue
        address = (ap.attributes or {}).get("address")
        if not address or (ap.workspace_id, address) in seen:
            continue
        seen.add((ap.workspace_id, address))
        views = access_points(db, ap.workspace_id, address)
        active = [v for v in views if v["record_status"] == "Active"]
        if len(active) > 1:
            raise InvariantError("I-AP-1", f"two Active Access Points for {address}")
        for i, a in enumerate(views):
            for b in views[i + 1:]:
                if temporal.overlap(a["interval"], b["interval"]) == "definite":
                    raise InvariantError("I-AP-3", f"{a['key']} and {b['key']} served {address} at the same time")


# --------------------------------------------------------------------------- port mapping (§9.3)

def _effective_sources(db: Session, uid: str, predicate: str) -> list[tuple[str, Optional[str], Optional[str]]]:
    """(contributor kind, stream kind, method) of the effective contributors of one fact."""
    out = []
    for f in db.scalars(select(FactState).where(FactState.subject_uid == uid, FactState.predicate == predicate,
                                                FactState.effective.is_(True))):
        if f.contributor.startswith("decision:"):
            out.append(("decision", None, None))
            continue
        c = db.get(Claim, f.contributor[6:])
        stream = db.get(LedgerStream, c.stream_id) if c else None
        out.append(("claim", stream.kind if stream else None, c.method if c else None))
    return out


def _registry_backed(db: Session, port_uid: str, names: Iterable[str]) -> bool:
    for name in names:
        sources = _effective_sources(db, port_uid, f"attr:{name}")
        if not sources or any(k == "claim" and (sk not in REGISTRY_KINDS or m == "inferred")
                              for k, sk, m in sources):
            return False
    return True


def _requirement_firm(db: Session, segment_uid: str) -> bool:
    """Every field of `required_port` is stated or confirmed, never advisory."""
    sources = _effective_sources(db, segment_uid, "attr:required_port")
    return bool(sources) and all(k == "decision" or m in ("stated", "manual") for k, _sk, m in sources)


def _first_failure(port: dict, req: dict) -> Optional[str]:
    """The first criterion a port fails, in the order of §9.3 step 3."""
    if req.get("role"):
        if port.get("port_role") != req["role"]:
            return "3a identity (role)"
    elif port.get("port_label") != req.get("label"):
        return "3a identity (label)"
    return _hard_failure(port, req)


def _hard_failure(port: dict, req: dict) -> Optional[str]:
    kind = port.get("port_kind")
    if req.get("kind") and req["kind"] not in KIND_COMPATIBLE.get(kind, {kind}):
        return "3b kind"
    if req.get("mode") and port.get("operating_mode") != req["mode"]:
        return "3c mode"
    if req.get("tcp_port") is not None and port.get("tcp_port") != req["tcp_port"]:
        return "3c tcp port"
    for field in ("signal_level", "termination"):
        if req.get(field) is not None and port.get(field) != req[field]:
            return "3d electrical"
    return None


def _used_fields(req: dict) -> list[str]:
    names = ["port_role" if req.get("role") else "port_label", "port_kind", "operating_mode"]
    if req.get("tcp_port") is not None:
        names.append("tcp_port")
    names += [f for f in ("signal_level", "termination") if req.get(f) is not None]
    return names


def match_segment(db: Session, segment: Asset, t: Optional[datetime] = None) -> dict:
    """Where a Bus Segment attaches at time t, per §9.3. The result's
    `status` is attached, unresolved, confirmation_required, invalid, or
    not_applicable (no assigned Access Point or no unit installed)."""
    t = t or now()
    a = segment.attributes or {}
    req = a.get("required_port") or {}
    path = edge_target(db, segment.uid, "served by")
    ap = edge_target(db, path, "enters at") if path else None
    position = edge_target(db, ap, "assigned to") if ap else None
    hits = [h for h in engine.installations_at(db, t, position_uid=position) if h["certainty"] == "definite"] \
        if position else []
    if not req or len(hits) != 1:
        return {"status": "not_applicable", "position_uid": position}
    inst = hits[0]
    unit = inst["asset_uid"]
    ports = [p for p in (db.get(Asset, uid) for uid in edge_sources(db, "port of", unit))
             if p is not None and p.record_status != "Retired"]
    base = {"position_uid": position, "installation_uid": inst["uid"], "unit_uid": unit, "required": req}
    safety = a.get("safety_class") or "none"
    port_map = a.get("port_map") if isinstance(a.get("port_map"), dict) else None
    confirmed = port_map if port_map and port_map.get("installation_uid") == inst["uid"] else None
    listing = [{"port_uid": p.uid, "label": (p.attributes or {}).get("port_label") or p.name,
                "failed": _first_failure(p.attributes or {}, req)} for p in ports]

    # 1. A confirmed map for this Installation identifies the port; it never
    #    overrides a hard compatibility check.
    if confirmed:
        port = db.get(Asset, confirmed.get("port_uid"))
        failure = "not a port of the installed unit" if port is None or port.uid not in {p.uid for p in ports} \
            else _hard_failure(port.attributes or {}, req)
        if failure:
            return {**base, "status": "invalid", "port_uid": confirmed.get("port_uid"), "failed": failure}
        return {**base, "status": "attached", "port_uid": port.uid, "evidence": {"confirmed_map": True}}
    candidates = [p for p in ports if _first_failure(p.attributes or {}, req) is None]
    # 2. A safety-classed segment always needs a person for a new Installation.
    if safety != "none":
        return {**base, "status": "confirmation_required", "reason": f"safety class {safety}",
                "candidates": [{"port_uid": p.uid, "label": (p.attributes or {}).get("port_label") or p.name}
                               for p in candidates]}
    # 3-5. Exactly one registry-backed, fully compatible candidate attaches.
    if len(candidates) == 1:
        port = candidates[0]
        if _registry_backed(db, port.uid, _used_fields(req)) and _requirement_firm(db, segment.uid):
            return {**base, "status": "attached", "port_uid": port.uid,
                    "evidence": {"criteria": _used_fields(req), "registry_backed": True}}
        return {**base, "status": "confirmation_required", "reason": "the match is not registry-backed",
                "candidates": [{"port_uid": port.uid, "label": (port.attributes or {}).get("port_label")}]}
    return {**base, "status": "unresolved", "ports": listing,
            "candidates": [{"port_uid": p.uid, "label": (p.attributes or {}).get("port_label") or p.name}
                           for p in candidates]}


def _scope(db: Session, workspace_ids: Optional[Iterable[str]]):
    """The Access Points and Bus Segments a derive run over these workspaces
    can change: their own, and those reaching a position in them or a
    position where a unit of theirs is installed (a registry revision in the
    IT workspace moves segments owned by a beamline)."""
    if workspace_ids is None:
        return None, None
    ids = list(set(workspace_ids))
    in_ws = select(Asset.uid).where(Asset.workspace_id.in_(ids))
    installations_here = select(Relation.from_asset_uid).where(
        Relation.relation_type == "installation of", Relation.to_asset_uid.in_(in_ws))
    positions = set(db.scalars(in_ws.where(Asset.type.in_(engine.INSTALLABLE)))) | set(db.scalars(
        select(Relation.to_asset_uid).where(Relation.relation_type == "installed at",
                                            Relation.from_asset_uid.in_(installations_here))))
    aps = set(db.scalars(in_ws.where(Asset.type == ACCESS_POINT))) | set(db.scalars(
        select(Relation.from_asset_uid).where(Relation.relation_type == "assigned to",
                                              Relation.to_asset_uid.in_(positions))))
    paths = set(db.scalars(select(Relation.from_asset_uid).where(Relation.relation_type == "enters at",
                                                                Relation.to_asset_uid.in_(aps))))
    segments = set(db.scalars(in_ws.where(Asset.type == BUS_SEGMENT))) | set(db.scalars(
        select(Relation.from_asset_uid).where(Relation.relation_type == "served by",
                                              Relation.to_asset_uid.in_(paths))))
    return aps, segments


_STATUS_CONFLICT = {"unresolved": "port_mapping_unresolved", "confirmation_required": "port_confirmation_required",
                    "invalid": "port_map_invalid"}


def derive_ports(db: Session, workspace_ids: Optional[Iterable[str]] = None) -> dict:
    """Derived `attached to` edges and their review items (I-PORT-1…3)."""
    _aps, scope = _scope(db, workspace_ids)
    wanted_edges: set[tuple] = set()
    wanted_items: dict[str, tuple] = {}
    q = select(Asset).where(Asset.type == BUS_SEGMENT, Asset.record_status != "Retired")
    if scope is not None:
        q = q.where(Asset.uid.in_(scope))
    segments = list(db.scalars(q))
    for seg in segments:
        m = match_segment(db, seg)
        if m["status"] == "attached":
            wanted_edges.add((seg.uid, m["port_uid"], seg.workspace_id))
        elif m["status"] in _STATUS_CONFLICT:
            ctype = _STATUS_CONFLICT[m["status"]]
            cid = hashlib.sha256(canonical([ctype, seg.uid]).encode()).hexdigest()[:24]
            wanted_items[cid] = (ctype, seg, {k: v for k, v in m.items() if k != "status"})
    rq = select(Relation).where(Relation.derivation == "derived", Relation.relation_type == "attached to")
    cq = select(Conflict).where(Conflict.conflict_type.in_(PORT_CONFLICTS))
    if scope is not None:
        rq = rq.where(Relation.from_asset_uid.in_(scope))
        cq = cq.where(Conflict.subject_uid.in_(scope))
    current = {(r.from_asset_uid, r.to_asset_uid): r for r in db.scalars(rq)}
    for key, row in current.items():
        if (key[0], key[1]) not in {(s, p) for s, p, _w in wanted_edges}:
            db.delete(row)
    for seg_uid, port_uid, ws in wanted_edges:
        if (seg_uid, port_uid) not in current:
            db.add(Relation(workspace_id=ws, from_asset_uid=seg_uid, to_asset_uid=port_uid,
                            relation_type="attached to", derivation="derived", rule=PORT_RULE))
    existing = {c.conflict_id: c for c in db.scalars(cq)}
    for cid, (ctype, seg, detail) in wanted_items.items():
        if cid in existing:
            existing[cid].detail = detail
            continue
        ev = ConflictEvent(conflict_id=cid, kind="opened", conflict_type=ctype, subject_uid=seg.uid,
                           predicate="attr:port_map", detail=detail, cause="derive", at=now())
        db.add(ev)
        db.flush()
        db.add(Conflict(conflict_id=cid, conflict_type=ctype, severity="non-blocking", workspace_id=seg.workspace_id,
                        subject_uid=seg.uid, predicate="attr:port_map", detail=detail, opened_seq=ev.seq))
    for cid, row in existing.items():
        if cid not in wanted_items:
            db.add(ConflictEvent(conflict_id=cid, kind="resolved", conflict_type=row.conflict_type,
                                 subject_uid=row.subject_uid, predicate=row.predicate, detail=row.detail,
                                 cause="derive", at=now()))
            db.delete(row)
    db.flush()
    return {"attached": len(wanted_edges), "items": len(wanted_items)}


def attachments_at(db: Session, segment_uid: str, t) -> Optional[dict]:
    """The port a segment was attached to at time t: the previous unit's
    attachment stays in history through its Installation interval."""
    seg = db.get(Asset, segment_uid)
    if seg is None:
        return None
    m = match_segment(db, seg, temporal.parse_instant(t))
    return m if m["status"] == "attached" else None


def derive_implemented_by(db: Session, workspace_ids: Optional[Iterable[str]] = None) -> dict:
    """`implemented by` (§9.2): an assigned Access Point -> the unit of the
    definitely current Confirmed Installation at its position."""
    scope, _segments = _scope(db, workspace_ids)
    wanted: dict[tuple, str] = {}
    t = now()
    q = select(Asset).where(Asset.type == ACCESS_POINT, Asset.record_status == "Active")
    rq = select(Relation).where(Relation.derivation == "derived", Relation.relation_type == "implemented by")
    if scope is not None:
        q = q.where(Asset.uid.in_(scope))
        rq = rq.where(Relation.from_asset_uid.in_(scope))
    for ap in db.scalars(q):
        position = edge_target(db, ap.uid, "assigned to")
        if not position:
            continue
        for h in engine.installations_at(db, t, position_uid=position):
            if h["certainty"] == "definite":
                wanted[(ap.uid, h["asset_uid"])] = ap.workspace_id
    current = {(r.from_asset_uid, r.to_asset_uid): r for r in db.scalars(rq)}
    for key, row in current.items():
        if key not in wanted:
            db.delete(row)
    for (ap, unit), ws in wanted.items():
        if (ap, unit) not in current:
            db.add(Relation(workspace_id=ws, from_asset_uid=ap, to_asset_uid=unit, relation_type="implemented by",
                            derivation="derived", rule="implemented-by/1"))
    db.flush()
    return {"implemented_by": len(wanted)}


def confirm_port_map(segment_uid: str, installation_uid: str, port_uid: str, replaces: list[str]) -> dict:
    value = {"installation_uid": installation_uid, "port_uid": port_uid}
    if replaces:
        return {"kind": "supersede", "subject_uid": segment_uid, "predicate": "attr:port_map", "value": value,
                "supersedes": replaces}
    return {"kind": "confirm", "subject_uid": segment_uid, "predicate": "attr:port_map", "value": value}


def active_port_map_decisions(db: Session, segment_uid: str) -> list[str]:
    return [d.decision_id for d in engine._active_decisions(db, segment_uid, "attr:port_map", None)]

