"""Guided conversion of the old importer's Serial Lines (asset-model-revision
§9.1, §9.3, §12.4).

The old importer wrote a Serial Line per converter port, with the devices
`on line`, the line `port of` its Access Point and `carried by` the
converter. The model since has no device-to-line edge. A **Communication
Path** runs from an IOC to the endpoint (`enters at` the Access Point), it
`continues on` a **Bus Segment** (the line itself, retyped in place, so its
uid, key, tickets and documents stay), and each device `uses path`. The
line's port number becomes an advisory `required_port` claim: a number never
attaches a port on its own.

One line at a time: `propose` says what would be built and what is unclear,
a person confirms or adjusts it, and `convert` builds it through the ledger.
The golden incidents are walked before and after; if the walk loses a cause
it knew, the conversion is refused unless the person overrides it.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine, golden, service
from app.ledger.engine import LedgerError
from app.models.asset import Asset, Relation
from app.models.ledger import RecordEvent

SERIAL_LINE = "Serial Line"
BUS_SEGMENT = "Bus Segment"
PATH = "Communication Path"
OLD_VERBS = ("on line", "port of", "carried by")


class ConversionError(LedgerError):
    pass


def _targets(db: Session, uid: str, rel: str) -> list[Asset]:
    return [a for a in (db.get(Asset, t) for t in db.scalars(select(Relation.to_asset_uid).where(
        Relation.from_asset_uid == uid, Relation.relation_type == rel))) if a is not None]


def _sources(db: Session, rel: str, uid: str) -> list[Asset]:
    return [a for a in (db.get(Asset, s) for s in db.scalars(select(Relation.from_asset_uid).where(
        Relation.to_asset_uid == uid, Relation.relation_type == rel))) if a is not None]


def _tcp_port(line: Asset) -> Optional[int]:
    value = (line.attributes or {}).get("tcp_port")
    if value is None:
        m = re.search(r":(\d{2,5})$", line.key or "")
        value = m.group(1) if m else None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def propose(db: Session, line: Asset) -> dict:
    """What converting this line would build, and what a person must settle."""
    ports = _targets(db, line.uid, "port of")
    aps = [a for a in ports if a.type == "Access Point"]
    converters = _targets(db, line.uid, "carried by") + [a for a in ports if a.type != "Access Point"]
    devices = _sources(db, "on line", line.uid)
    iocs: dict[str, list[str]] = {}
    no_ioc = []
    for d in devices:
        provided = _targets(db, d.uid, "provided by")
        if provided:
            iocs.setdefault(provided[0].uid, []).append(d.uid)
        else:
            no_ioc.append(d.uid)
    questions = []
    if len(aps) != 1:
        questions.append(f"the line names {len(aps)} Access Points; say which one it enters at")
    if no_ioc:
        questions.append(f"{len(no_ioc)} device(s) have no IOC; their path cannot be drawn")
    if not devices:
        questions.append("no device is on this line")
    ap = aps[0] if len(aps) == 1 else None
    implemented = _targets(db, ap.uid, "implemented by") if ap else []
    return {
        "line": {"uid": line.uid, "key": line.key, "name": line.name},
        "access_point": {"uid": ap.uid, "key": ap.key} if ap else None,
        "access_points": [{"uid": a.uid, "key": a.key} for a in aps],
        "converter": {"uid": converters[0].uid, "key": converters[0].key} if converters else None,
        "implements_access_point": bool(implemented) or not converters,
        "paths": [{"ioc": {"uid": i, "key": db.get(Asset, i).key}, "devices": ds} for i, ds in iocs.items()],
        "devices": [{"uid": d.uid, "key": d.key} for d in devices],
        "required_port": {"tcp_port": _tcp_port(line)} if _tcp_port(line) else None,
        "questions": questions,
        "ready": not questions,
    }


def lines(db: Session, workspace_id: str) -> list[dict]:
    return [propose(db, l) for l in db.scalars(select(Asset).where(
        Asset.workspace_id == workspace_id, Asset.type == SERIAL_LINE, Asset.record_status != "Retired")
        .order_by(Asset.key))]


def convert(db: Session, workspace_id: str, actor: str, line_uid: str, *, access_point_uid: Optional[str] = None,
            reason: str, accept_golden_loss: Optional[str] = None) -> dict:
    """Build the path and segment for one line, through the ledger. The caller
    commits; on ConversionError it rolls back."""
    line = db.get(Asset, line_uid)
    if line is None or line.workspace_id != workspace_id or line.type != SERIAL_LINE:
        raise ConversionError("not a Serial Line of this workspace")
    if not reason.strip():
        raise ConversionError("a conversion needs a reason")
    p = propose(db, line)
    ap_uid = access_point_uid or (p["access_point"] or {}).get("uid")
    ap = db.get(Asset, ap_uid) if ap_uid else None
    if ap is None or ap.type != "Access Point" or ap.workspace_id != workspace_id or ap.record_status == "Retired":
        raise ConversionError("say which Access Point the line enters at")
    if not p["paths"]:
        raise ConversionError("no device on this line has an IOC: there is no path to draw")
    no_ioc = [d for d in p["devices"] if not any(d["uid"] in g["devices"] for g in p["paths"])]
    if no_ioc:
        # Removing their edge would leave them unreachable in the model: settle them first.
        raise ConversionError(f"{len(no_ioc)} device(s) on this line have no IOC (provided by): "
                              + ", ".join(d["key"] for d in no_ioc))
    before = golden.run(db, workspace_id)
    built = {"paths": [], "segment": line.uid, "removed": [], "required_port": p["required_port"]}

    # The line becomes the Bus Segment, in place (same uid, key, tickets, documents).
    from app.ledger.writer import writing
    with writing(db):
        db.add(RecordEvent(uid=line.uid, kind="retyped", before={"type": SERIAL_LINE}, after={"type": BUS_SEGMENT},
                           cause=f"serial line conversion by {actor}", at=engine.now()))
        line.type = BUS_SEGMENT
        line.schema_uid = engine.ensure_type(db, workspace_id, BUS_SEGMENT).uid
    if p["required_port"]:
        # Advisory only (§9.3): an inferred statement nobody has confirmed.
        engine.add_manual_claims(db, engine.person_stream(db, workspace_id, actor), [
            engine.ParsedClaim(f"uid:{line.uid}", "attr:required_port", p["required_port"], method="inferred")],
            cause=f"serial line conversion by {actor}")

    for group in p["paths"]:
        ioc = db.get(Asset, group["ioc"]["uid"])
        uid = engine.ulid()
        path = service.create_record(db, workspace_id, actor, uid=f"path-{uid.lower()}",
                                     schema_uid=engine.ensure_type(db, workspace_id, PATH).uid,
                                     key=f"PATH:{ioc.key}:{line.key}", name=f"{ioc.name} → {line.name}",
                                     type_name=PATH, attributes={})
        service.relate(db, workspace_id, actor, path.uid, "enters at", ap_uid)
        service.relate(db, workspace_id, actor, path.uid, "continues on", line.uid)
        service.relate(db, workspace_id, actor, line.uid, "served by", path.uid)
        for d in group["devices"]:
            service.relate(db, workspace_id, actor, d, "uses path", path.uid)
        built["paths"].append({"uid": path.uid, "key": path.key, "devices": len(group["devices"])})

    # The converter the line was carried by is the equipment behind the endpoint,
    # unless the endpoint already names one.
    if p["converter"] and not _targets(db, ap_uid, "implemented by"):
        service.relate(db, workspace_id, actor, ap_uid, "implemented by", p["converter"]["uid"])
        built["implemented_by"] = p["converter"]["uid"]

    for rel in list(db.scalars(select(Relation).where(
            Relation.relation_type.in_(OLD_VERBS),
            (Relation.from_asset_uid == line.uid) | (Relation.to_asset_uid == line.uid)))):
        if rel.relation_type == "on line" and rel.to_asset_uid != line.uid:
            continue
        built["removed"].append({"type": rel.relation_type, "from": rel.from_asset_uid, "to": rel.to_asset_uid})
        if rel.derivation == "ledger":
            service.relate(db, workspace_id, actor, rel.from_asset_uid, rel.relation_type, rel.to_asset_uid,
                           present=False, reason=reason)
        else:
            service.remove_legacy_edge(db, workspace_id, actor, rel, reason=reason)

    after = golden.run(db, workspace_id)
    check = golden.compare(before, after) if before["incidents"] else {"ok": None, "incidents": 0}
    if check["ok"] is False and not (accept_golden_loss or "").strip():
        raise ConversionError("the root-cause walk would lose a cause the golden incidents know: "
                              + "; ".join(f"{l['incident']}: {l['cause']}" for l in check["lost"]))
    built["golden"] = check
    engine._record_decision(db, "convert_serial_line", actor, workspace_id, subject_uid=line.uid,
                            value={"paths": [x["key"] for x in built["paths"]], "removed": len(built["removed"]),
                                   "golden": check.get("ok"), "golden_loss_accepted": accept_golden_loss},
                            reason=reason)
    db.flush()
    return built
