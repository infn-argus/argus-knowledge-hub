"""Guided equipment replacement (flutter-app-design §8, revision §8.4, §24.8, A68).

One command replaces the unit at a Position. A dry run shows the checks and consequences first;
the submission then either applies the swap in one ledger batch or becomes a proposal.

A replacement becomes a proposal, a `replacement_proposal` review item carrying the command and
its evidence, when any of these holds:
- the unit the person scanned as outgoing is not the one recorded (a separate
  `outgoing_discrepancy` item records it: never a silent correction);
- a segment behind the Position needs port confirmation: a safety class (§9.3, D14), or no
  unique registry-backed port on the incoming unit;
- the person does not hold the owner's rights (`approve`).

An approver confirms the proposal, which runs the same atomic swap after re-checking the Position,
or rejects it. Port confirmations then follow the ordinary derive rules (A22).

Refused outright, with nothing written:
- an incoming unit that is unknown, retired or merged;
- an incoming unit installed elsewhere now (I-INS-1);
- an incoming unit that is not a physical unit.

No unit is ever created here (I-MOB-6): an unknown incoming unit goes through registration first.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import connectivity, engine, service, temporal
from app.models.asset import Asset
from app.models.ledger import Conflict, ConflictEvent

PROPOSAL = "replacement_proposal"
DISCREPANCY = "outgoing_discrepancy"
ERROR, WARNING, INFO = "error", "warning", "info"


def _check(level: str, cid: str, message: str, **extra) -> dict:
    return {"id": cid, "level": level, "message": message, **extra}


def _brief(a: Optional[Asset], visible) -> Optional[dict]:
    if a is None:
        return None
    if not visible(a):
        return {"uid": None, "key": None, "name": "Restricted record", "type": None, "restricted": True}
    return {"uid": a.uid, "key": a.key, "name": a.name, "type": a.type, "record_status": a.record_status}


def current_installations(db: Session, position_uid: str) -> list[dict]:
    return [v for v in engine.installations(db, position_uid=position_uid, status="Confirmed")
            if (v["valid_until"] or {"kind": "open"}).get("kind") == "open"]


def _segments_behind(db: Session, position_uid: str) -> list[Asset]:
    out = []
    for ap in connectivity.edge_sources(db, "assigned to", position_uid):
        for path in connectivity.edge_sources(db, "enters at", ap):
            for seg in connectivity.edge_sources(db, "served by", path):
                s = db.get(Asset, seg)
                if s is not None and s.record_status == "Active":
                    out.append(s)
    return out


def _port_outcome(db: Session, segment: Asset, incoming: Asset) -> dict:
    """What §9.3 would say about this segment once the incoming unit is installed."""
    a = segment.attributes or {}
    req = a.get("required_port") or {}
    safety = a.get("safety_class") or "none"
    if not req:
        return {"status": "not_applicable", "safety_class": safety}
    ports = [p for p in (db.get(Asset, u) for u in connectivity.edge_sources(db, "port of", incoming.uid))
             if p is not None and p.record_status != "Retired"]
    candidates = [p for p in ports if connectivity._first_failure(p.attributes or {}, req) is None]
    if safety != "none":
        return {"status": "confirmation_required", "safety_class": safety, "reason": f"safety class {safety}",
                "candidates": len(candidates)}
    if len(candidates) == 1 and connectivity._registry_backed(db, candidates[0].uid, connectivity._used_fields(req)) \
            and connectivity._requirement_firm(db, segment.uid):
        return {"status": "attaches", "safety_class": safety}
    return {"status": "confirmation_required" if len(candidates) == 1 else "unresolved", "safety_class": safety,
            "reason": "no unique registry-backed port" if len(candidates) != 1 else "the match is not registry-backed",
            "candidates": len(candidates)}


def preview(db: Session, workspace_id: str, *, position_uid: str, incoming_uid: str,
            outgoing_uid: Optional[str] = None, seen_installation_uid: Optional[str] = None,
            seen_given: bool = False, visible=lambda a: True, can_approve: bool = False,
            access=None) -> dict:
    """The checks and consequences of a replacement; writes nothing."""
    from app.intake.guide import lineage, nature
    from app.models.schema import Schema
    checks: list[dict] = []
    position = db.get(Asset, position_uid)
    if position is None or not visible(position) or position.workspace_id != workspace_id:
        return {"outcome": "refused", "checks": [_check(ERROR, "position", "No such Position here.")],
                "reasons": [], "consequences": {}}
    if position.type not in engine.INSTALLABLE:
        checks.append(_check(ERROR, "position", f"{position.type} is not a Position that holds a unit (I-INS-4)."))
    current = current_installations(db, position_uid)
    recorded_uid = current[0]["asset_uid"] if current else None
    recorded = db.get(Asset, recorded_uid) if recorded_uid else None
    stale = seen_given and sorted(v["uid"] for v in current) != ([seen_installation_uid] if seen_installation_uid else [])
    if stale:
        checks.append(_check(ERROR, "stale", "The Position's installation changed since you saw it. Look again."))

    discrepancy = None
    if outgoing_uid and outgoing_uid != recorded_uid:
        scanned = db.get(Asset, outgoing_uid)
        discrepancy = {"recorded": _brief(recorded, visible), "scanned": _brief(scanned, visible)}
        checks.append(_check(WARNING, "outgoing", "The unit you scanned is not the one recorded at this Position. "
                             "The difference goes to review; nothing is corrected silently.", **discrepancy))

    incoming = db.get(Asset, incoming_uid)
    if incoming is None or not visible(incoming):
        checks.append(_check(ERROR, "incoming", "The incoming unit is not known here. Register it first, from its "
                             "nameplate; a unit is never made from the Position's name."))
    else:
        schema = db.get(Schema, incoming.schema_uid) if incoming.schema_uid else None
        kind = nature(db, schema) if schema is not None else "other"
        if kind in ("position", "control"):
            checks.append(_check(ERROR, "incoming", f"{incoming.type} is not a physical unit."))
        if incoming.record_status in ("Retired", "Merged"):
            checks.append(_check(ERROR, "incoming", f"The incoming unit is {incoming.record_status.lower()}."))
        elif incoming.record_status == "Provisional":
            checks.append(_check(WARNING, "incoming", "The incoming unit is provisional: its identity is not confirmed."))
        if incoming.uid == recorded_uid:
            checks.append(_check(ERROR, "incoming", "That unit is already installed here."))
        elsewhere = [v for v in engine.installations(db, asset_uid=incoming.uid, status="Confirmed")
                     if (v["valid_until"] or {"kind": "open"}).get("kind") == "open" and v["position_uid"] != position_uid]
        if elsewhere:
            where = db.get(Asset, elsewhere[0]["position_uid"])
            checks.append(_check(ERROR, "installed_elsewhere",
                                 f"The incoming unit is installed at {(_brief(where, visible) or {}).get('name')} now. "
                                 "Remove it there first (I-INS-1).", invariant="I-INS-1"))
        expected = (position.attributes or {}).get("position_class")
        if expected and schema is not None and expected not in lineage(db, schema):
            checks.append(_check(WARNING, "compatibility",
                                 f"This Position expects a {expected}; the incoming unit is a {incoming.type}."))
        dupes = db.scalars(select(Conflict).where(Conflict.subject_uid == incoming.uid,
                                                  Conflict.conflict_type == "identity_candidate")).all()
        if dupes:
            checks.append(_check(WARNING, "duplicates", "The incoming unit may be a duplicate of another record; "
                                 "the identity review is still open."))

    segments, hidden, ports_needed = [], 0, []
    if incoming is not None:
        for seg in _segments_behind(db, position_uid):
            outcome = _port_outcome(db, seg, incoming)
            if outcome["status"] in ("confirmation_required", "unresolved"):
                ports_needed.append(outcome)
            if visible(seg):
                segments.append({**_brief(seg, visible), **outcome})
            else:
                hidden += 1
    if ports_needed:
        protected = [p for p in ports_needed if p["safety_class"] != "none"]
        checks.append(_check(WARNING, "ports", f"{len(ports_needed)} segment(s) behind this Position need their port "
                             "confirmed after the replacement" + (f", {len(protected)} of them safety-classed "
                             f"({', '.join(sorted({p['safety_class'] for p in protected}))})" if protected else "")
                             + ". A controls steward confirms them; the replacement is submitted as a proposal."))
    from app.services import knowledge_hub as hub
    access = access or hub.Access(assets=True, tickets=True, documents=True)
    context = hub.asset_context(db, workspace_id, position, access)
    consequences = {
        "access_points": [_brief(db.get(Asset, u), visible) for u in connectivity.edge_sources(db, "assigned to", position_uid)],
        "segments": segments,
        "hidden_segments": hidden,
        "documents": [{"uid": d["uid"], "code": d["code"], "title": d["title"]} for d in context.get("documents", [])],
        "open_tickets": [{"uid": t["uid"], "title": t["title"]} for t in context.get("tickets", []) if t.get("open")],
        "graph": "confirmed",
    }
    reasons = []
    if discrepancy:
        reasons.append("the outgoing unit differs from the recorded one")
    if ports_needed:
        reasons.append("port confirmation is needed")
    if not can_approve:
        reasons.append("the owner's rights are needed to confirm it")
    errors = [c for c in checks if c["level"] == ERROR]
    outcome = "refused" if errors else ("propose" if reasons else "apply")
    return {"outcome": outcome, "reasons": [] if errors else reasons, "checks": checks,
            "position": _brief(position, visible), "current": {
                "installation_uid": current[0]["uid"] if current else None, "unit": _brief(recorded, visible)},
            "incoming": _brief(incoming, visible), "discrepancy": discrepancy, "consequences": consequences}


def _open(db: Session, ctype: str, position: Asset, detail: dict, actor: str) -> str:
    cid = hashlib.sha256(json.dumps([ctype, position.uid, detail.get("command"), detail.get("submitted_at")],
                                    sort_keys=True, default=str).encode()).hexdigest()[:24]
    if db.get(Conflict, cid) is None:
        ev = ConflictEvent(conflict_id=cid, kind="opened", conflict_type=ctype, subject_uid=position.uid,
                           detail=detail, cause=f"replacement by {actor}", at=datetime.now(timezone.utc))
        db.add(ev)
        db.flush()
        db.add(Conflict(conflict_id=cid, conflict_type=ctype, severity="non-blocking",
                        workspace_id=position.workspace_id, subject_uid=position.uid, detail=detail,
                        opened_seq=ev.seq))
    return cid


def close(db: Session, cid: str, actor: str, outcome: str, reason: Optional[str] = None) -> Conflict:
    c = db.get(Conflict, cid)
    db.add(ConflictEvent(conflict_id=cid, kind="resolved", conflict_type=c.conflict_type, subject_uid=c.subject_uid,
                         detail={**(c.detail or {}), "outcome": outcome, "reason": reason},
                         cause=f"{outcome} by {actor}", at=datetime.now(timezone.utc)))
    db.delete(c)
    return c


def submit(db: Session, workspace_id: str, actor: str, command: dict, preview_result: dict,
           evidence: Optional[dict]) -> dict:
    """Apply, or record as a proposal (and a discrepancy item). The caller has refused errors."""
    position = db.get(Asset, command["position_uid"])
    now = datetime.now(timezone.utc).isoformat()
    out: dict = {"outcome": preview_result["outcome"], "reasons": preview_result["reasons"]}
    if preview_result["discrepancy"]:
        out["discrepancy_item"] = _open(db, DISCREPANCY, position, {
            "command": command, "submitted_by": actor, "submitted_at": now, "evidence": evidence or {},
            **preview_result["discrepancy"]}, actor)
    if preview_result["outcome"] == "apply":
        out.update(_apply(db, workspace_id, actor, command))
        return out
    out["review_item"] = _open(db, PROPOSAL, position, {
        "command": command, "submitted_by": actor, "submitted_at": now, "evidence": evidence or {},
        "reasons": preview_result["reasons"], "checks": preview_result["checks"],
        "current": preview_result["current"], "incoming": preview_result["incoming"]}, actor)
    return out


def _apply(db: Session, workspace_id: str, actor: str, command: dict) -> dict:
    at = temporal.instant(command["at"], command.get("precision") or "instant")
    reason = command.get("reason") or "Replacement"
    result = service.swap(db, workspace_id, actor, command["position_uid"], command["incoming_uid"], at, reason)
    ref = command.get("work_reference")
    if ref:
        _note_on_ticket(db, workspace_id, actor, ref, command)
    return {"ended": result["ended"], "installation_uid": result["installation_uid"]}


def _note_on_ticket(db: Session, workspace_id: str, actor: str, ticket_uid: str, command: dict) -> None:
    """The work reference gets a line saying what was replaced, so the ticket tells the story."""
    import uuid
    from app.models.issue import Issue, IssueComment
    issue = db.get(Issue, ticket_uid)
    if issue is None or issue.workspace_id != workspace_id:
        return
    incoming = db.get(Asset, command["incoming_uid"])
    position = db.get(Asset, command["position_uid"])
    db.add(IssueComment(uid=str(uuid.uuid4()), issue_uid=issue.uid, author=actor,
                        body=f"Replacement at {position.key}: {incoming.key} installed "
                             f"({command.get('reason') or 'Replacement'})."))


def confirm(db: Session, workspace_id: str, actor: str, cid: str, visible) -> dict:
    """An approver confirms a proposed replacement: the same checks, then the atomic swap."""
    c = db.get(Conflict, cid)
    if c is None or c.conflict_type != PROPOSAL or c.workspace_id != workspace_id:
        raise LookupError(cid)
    command = dict(c.detail["command"])
    check = preview(db, workspace_id, position_uid=command["position_uid"], incoming_uid=command["incoming_uid"],
                    seen_installation_uid=command.get("seen_installation_uid"),
                    seen_given="seen_installation_uid" in command, visible=visible, can_approve=True)
    errors = [x for x in check["checks"] if x["level"] == ERROR]
    if errors:
        return {"outcome": "refused", "checks": errors}
    out = _apply(db, workspace_id, actor, command)
    close(db, cid, actor, "confirmed")
    return {"outcome": "applied", **out}
