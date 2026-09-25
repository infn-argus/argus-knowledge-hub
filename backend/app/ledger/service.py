"""What people do, expressed as claims and decisions (§3.2: a UI edit is a
claim from the person's stream plus a confirm decision by the same person)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.ledger import engine, temporal
from app.ledger.engine import INSTALLATION, InvariantError, LedgerError, ParsedClaim
from app.models.asset import Asset


def _active(db: Session, uid: str, predicate: str, member: Optional[str] = None) -> list[str]:
    return [d.decision_id for d in engine._active_decisions(db, uid, predicate, member)]


def confirm_value(uid: str, predicate: str, value, *, member: Optional[str] = None,
                  replaces: Optional[list[str]] = None, reason: Optional[str] = None) -> dict:
    """One decision: supersede what is confirmed now, or confirm afresh."""
    if replaces:
        return {"kind": "supersede", "subject_uid": uid, "predicate": predicate, "member": member,
                "value": value, "supersedes": replaces, "reason": reason}
    return {"kind": "confirm", "subject_uid": uid, "predicate": predicate, "member": member, "value": value,
            "reason": reason}


def edit_value(db: Session, workspace_id: str, actor: str, uid: str, predicate: str, value,
               reason: Optional[str] = None, defer_derive: bool = False) -> list:
    """A person setting a field: their statement, confirmed, replacing any
    confirmation they could see (an edit form shows the current value)."""
    from app.ledger.cutover import assert_writable
    assert_writable(db, workspace_id, "objects")
    stream = engine.person_stream(db, workspace_id, actor)
    engine.add_manual_claims(db, stream, [ParsedClaim(f"uid:{uid}", predicate, value, method="manual")],
                             cause=f"edit by {actor}")
    return engine.apply_decisions(db, workspace_id, actor, [
        confirm_value(uid, predicate, value, replaces=_active(db, uid, predicate), reason=reason)],
        defer_derive=defer_derive)


def set_member(db: Session, workspace_id: str, actor: str, uid: str, predicate: str, member_value,
               present: bool, reason: Optional[str] = None, defer_derive: bool = False) -> list:
    """Add or remove one member of a set as a confirmed positive or negative
    fact (§7.8.1). Removing is never a `reject`."""
    import json
    from app.ledger.cutover import assert_writable
    assert_writable(db, workspace_id, "objects")
    member = json.dumps(member_value)
    stream = engine.person_stream(db, workspace_id, actor)
    engine.add_manual_claims(db, stream, [ParsedClaim(f"uid:{uid}", predicate, member_value, method="manual",
                                                      member=member,
                                                      polarity="present" if present else "absent")],
                             cause=f"edit by {actor}")
    return engine.apply_decisions(db, workspace_id, actor, [
        confirm_value(uid, predicate, "present" if present else "absent", member=member,
                      replaces=_active(db, uid, predicate, member), reason=reason)], defer_derive=defer_derive)


def confirm_installation(db: Session, workspace_id: str, actor: str, installation_uid: str, *,
                         valid_from: Optional[dict] = None) -> list:
    inst = db.get(Asset, installation_uid)
    if inst is None or inst.type != INSTALLATION:
        raise LedgerError("not an Installation")
    batch = [confirm_value(installation_uid, "exists", "present", replaces=_active(db, installation_uid, "exists"))]
    if valid_from is not None:
        batch.append(confirm_value(installation_uid, "attr:valid_from", valid_from,
                                   replaces=_active(db, installation_uid, "attr:valid_from")))
    return engine.apply_decisions(db, workspace_id, actor, batch)


def reject_installation(db: Session, workspace_id: str, actor: str, installation_uid: str,
                        reason: Optional[str] = None) -> list:
    batch = [confirm_value(installation_uid, "exists", "absent", replaces=_active(db, installation_uid, "exists"),
                           reason=reason)]
    return engine.apply_decisions(db, workspace_id, actor, batch)


def new_installation_claims(db: Session, workspace_id: str, actor: str, position_uid: str, asset_uid: str,
                            valid_from: dict, valid_until: Optional[dict] = None) -> str:
    """A person records a unit at a position; returns the new record's uid."""
    position, unit = db.get(Asset, position_uid), db.get(Asset, asset_uid)
    if position is None or unit is None:
        raise LedgerError("unknown position or asset")
    if position.type not in engine.INSTALLABLE:
        raise InvariantError("I-INS-4", f"{position.type} is not an installable position")
    temporal.bounds(valid_from, "from")
    ref = f"person:inst:{engine.ulid()}"
    claims = [
        ParsedClaim(ref, "exists", {"type": INSTALLATION}, method="manual"),
        ParsedClaim(ref, "rel:installed at", {"ref": f"uid:{position_uid}"}, method="manual"),
        ParsedClaim(ref, "rel:installation of", {"ref": f"uid:{asset_uid}"}, method="manual"),
        ParsedClaim(ref, "attr:valid_from", valid_from, method="manual"),
    ]
    if valid_until is not None:
        claims.append(ParsedClaim(ref, "attr:valid_until", valid_until, method="manual"))
    stream = engine.person_stream(db, workspace_id, actor)
    # The record lives in the position's workspace (I-INS-5).
    if position.workspace_id != workspace_id:
        raise InvariantError("I-INS-5", "an Installation belongs to its position's workspace")
    engine.add_manual_claims(db, stream, claims, cause=f"installation by {actor}")
    uid = engine.resolve_ref(db, ref)
    engine.project_subject(db, uid, f"installation by {actor}")
    return uid


def swap(db: Session, workspace_id: str, actor: str, position_uid: str, new_asset_uid: str, at: dict,
         reason: str = "Unknown") -> dict:
    """End the current installation at a position and start a new one at the
    same instant, as one atomic batch (§8.4). Validation runs once, at the end."""
    current = [v for v in engine.installations(db, position_uid=position_uid, status="Confirmed")
               if v["valid_until"] in (None, {"kind": "open"}) or (v["valid_until"] or {}).get("kind") == "open"]
    batch = []
    for v in current:
        batch.append(confirm_value(v["uid"], "attr:valid_until", at,
                                   replaces=_active(db, v["uid"], "attr:valid_until")))
        batch.append(confirm_value(v["uid"], "attr:removal_reason", reason,
                                   replaces=_active(db, v["uid"], "attr:removal_reason")))
    new_uid = new_installation_claims(db, workspace_id, actor, position_uid, new_asset_uid, at)
    batch.append(confirm_value(new_uid, "exists", "present"))
    engine.apply_decisions(db, workspace_id, actor, batch)
    return {"ended": [v["uid"] for v in current], "installation_uid": new_uid}


def reassign_access_point(db: Session, workspace_id: str, actor: str, ap_uid: str, position_uid: str,
                          at: dict) -> str:
    """A person moves an address to another position (§9.2): the Access Point
    retires with a successor, which serves the new position from `at`."""
    from app.ledger import connectivity
    ap = db.get(Asset, ap_uid)
    if ap is None or ap.type != engine.ACCESS_POINT or ap.workspace_id != workspace_id:
        raise LedgerError("not an Access Point of this workspace")
    if db.get(Asset, position_uid) is None:
        raise LedgerError("unknown position")
    temporal.bounds(at, "from")
    touched = connectivity.reassign(db, ap, position_uid, handover=at, actor=actor, cause=f"reassigned by {actor}")
    for uid in sorted(touched):
        engine.project_subject(db, uid, f"reassigned by {actor}")
    connectivity.validate_access_points(db, touched)
    engine.derive_all(db, [workspace_id])
    return next(v["uid"] for v in connectivity.access_points(db, workspace_id, (ap.attributes or {}).get("address"))
                if v["record_status"] == "Active")
