"""The fact ledger's API: sources, decisions, the review queue, provenance and
installation history (asset-model-revision §7, §8, §11, §13 step S1)."""
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import OidcIdentity, get_identity, require_permission
from app.db import get_db
from app.ledger import connectivity, engine, rules, service, temporal, tickets
from app.ledger.engine import LedgerError
from app.ledger.policy import PolicyError
from app.models.asset import Asset
from app.services.visibility import asset_visible_in, can_see, hidden_fields, restriction_clause
from app.models.ledger import (Claim, ClaimEvent, Conflict, Decision, FactState, IdentityBinding, LedgerStream,
                               RevisionEvent, SourceRevision, StreamHead)

router = APIRouter(prefix="/v1/ledger", tags=["ledger"])
installations_router = APIRouter(prefix="/v1/installations", tags=["installations"])
access_points_router = APIRouter(prefix="/v1/access-points", tags=["access points"])


def actor_of(identity) -> str:
    if isinstance(identity, OidcIdentity):
        return identity.user.email or identity.user.id
    return "api-token"


def _fail(db: Session, exc: Exception, workspace_id: Optional[str] = None, actor: str = "",
          batch: Optional[list] = None):
    db.rollback()
    if batch is not None and workspace_id:
        # The attempt itself is audit data, even though nothing it asked for applied.
        engine.record_rejected_batch(db, workspace_id, actor, batch, str(exc))
        db.commit()
    code = getattr(exc, "code", None)
    raise HTTPException(status_code=409 if code else 422, detail={"error": str(exc), "invariant": code})


# --------------------------------------------------------------------------- streams

class StreamIn(BaseModel):
    id: str
    kind: str
    facility: Optional[str] = None
    may_create: list[str] = []


@router.post("/streams", status_code=201)
def register_stream(body: StreamIn, workspace_id: str = Depends(require_permission("create")),
                    db: Session = Depends(get_db)):
    s = engine.register_stream(db, body.id, workspace_id, body.kind, facility=body.facility,
                               may_create=body.may_create)
    db.commit()
    return {"id": s.id, "kind": s.kind, "note": "the active policy must be validated again for this stream"}


class RevisionIn(BaseModel):
    revision: str
    content: str
    parser: str
    observed_at: datetime


@router.post("/streams/{stream_id}/revisions")
def ingest_revision(stream_id: str, body: RevisionIn, workspace_id: str = Depends(require_permission("create")),
                    db: Session = Depends(get_db)):
    stream = db.get(LedgerStream, stream_id)
    if stream is None or stream.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Stream not found")
    try:
        result = engine.ingest(db, stream_id, revision=body.revision, content=body.content.encode(),
                               observed_at=body.observed_at, parser=body.parser)
    except (LedgerError, KeyError) as exc:
        _fail(db, exc)
    db.commit()
    return result


@router.get("/streams")
def list_streams(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    out = []
    for s in db.scalars(select(LedgerStream).where(LedgerStream.workspace_id == workspace_id)):
        head = db.get(StreamHead, s.id)
        out.append({"id": s.id, "kind": s.kind, "facility": s.facility, "frozen_at": s.frozen_at,
                    "parsed_number": head.parsed_number if head else 0,
                    "published_number": head.published_number if head else 0})
    return out


@router.post("/revisions/{revision_id}/approve")
def approve(revision_id: str, identity=Depends(get_identity),
            workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    try:
        engine.approve_revision(db, revision_id, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {"state": engine.revision_state(db, revision_id)}


@router.post("/revisions/{revision_id}/reject")
def reject(revision_id: str, identity=Depends(get_identity),
           workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    try:
        engine.reject_revision(db, revision_id, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {"state": engine.revision_state(db, revision_id)}


# --------------------------------------------------------------------------- decisions

class DecisionBatch(BaseModel):
    batch: list[dict[str, Any]]


@router.post("/decisions")
def decide(body: DecisionBatch, identity=Depends(get_identity),
           workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    actor = actor_of(identity)
    try:
        written = engine.apply_decisions(db, workspace_id, actor, body.batch)
    except LedgerError as exc:
        _fail(db, exc, workspace_id, actor, body.batch)
    db.commit()
    return {"decisions": [d.decision_id for d in written]}


class EditIn(BaseModel):
    predicate: str
    value: Any = None
    member: Any = None
    present: Optional[bool] = None
    reason: Optional[str] = None


def user_edit_derive_mode() -> str:
    """How a user edit's derive stage runs (D10): `background` (default) —
    after the response, the record showing `deriving` meanwhile; `manual` —
    left queued for a worker; `inline` — within the request."""
    return os.environ.get("LEDGER_USER_EDIT_DERIVE", "background")


def run_pending_derives() -> None:
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        engine.process_derive_requests(db)
        db.commit()
    finally:
        db.close()


@router.post("/records/{uid}/edit")
def edit(uid: str, body: EditIn, background: BackgroundTasks, identity=Depends(get_identity),
         workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    """A person's edit: projected within the request, so the response and the
    next read show it (I-UX-1); derived edges follow asynchronously."""
    actor = actor_of(identity)
    mode = user_edit_derive_mode()
    target = db.get(Asset, uid)
    if target is None or not can_see(target) or body.predicate in {f"attr:{k}" for k in hidden_fields(db, target)}:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        if body.present is not None:
            service.set_member(db, workspace_id, actor, uid, body.predicate, body.member, body.present, body.reason,
                               defer_derive=mode != "inline")
        else:
            service.edit_value(db, workspace_id, actor, uid, body.predicate, body.value, body.reason,
                               defer_derive=mode != "inline")
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    if mode == "background":
        background.add_task(run_pending_derives)
    record = db.get(Asset, uid)
    return {"ok": True, "attributes": record.attributes if record else None,
            "processing": engine.pending_derive(db, record.workspace_id) if record else None}


# --------------------------------------------------------------------------- review and provenance

def _record_brief(db: Session, uid: str) -> Optional[dict]:
    a = db.get(Asset, uid)
    if a is not None and not can_see(a):
        return {"uid": None, "key": None, "name": "Restricted record", "type": None, "record_status": None,
                "restricted": True}
    return {"uid": a.uid, "key": a.key, "name": a.name, "type": a.type, "record_status": a.record_status} if a else None


def _hidden(db: Session, uid: Optional[str]) -> bool:
    a = db.get(Asset, uid) if uid else None
    return a is not None and not can_see(a)


@router.get("/review")
def review(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Everything waiting on a person, with its owner-facing context."""
    conflicts = [{"conflict_id": c.conflict_id, "type": c.conflict_type, "severity": c.severity,
                  "predicate": c.predicate, "member": c.member, "detail": c.detail,
                  "record": _record_brief(db, c.subject_uid)}
                 for c in db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id))
                 if not _hidden(db, c.subject_uid)]
    proposals = []
    ws_uids = set(db.scalars(select(Asset.uid).where(Asset.workspace_id == workspace_id)))
    for f in db.scalars(select(FactState).where(FactState.status == "proposed")):
        if f.subject_uid not in ws_uids or not f.contributor.startswith("claim:") or _hidden(db, f.subject_uid):
            continue
        claim = db.get(Claim, f.contributor[6:])
        proposals.append({"claim_id": claim.claim_id, "predicate": f.predicate, "member": f.member,
                          "value": claim.value, "method": claim.method, "rule_id": claim.rule_id,
                          "stream_id": claim.stream_id, "record": _record_brief(db, f.subject_uid)})
    held = []
    for s in db.scalars(select(LedgerStream).where(LedgerStream.workspace_id == workspace_id)):
        for r in db.scalars(select(SourceRevision).where(SourceRevision.stream_id == s.id)):
            if engine.revision_state(db, r.id) == "held":
                ev = db.scalar(select(RevisionEvent).where(RevisionEvent.revision_id == r.id,
                                                           RevisionEvent.kind == "held"))
                held.append({"revision_id": r.id, "stream_id": s.id, "revision": r.revision,
                             "observed_at": r.observed_at, "reasons": (ev.detail or {}).get("reasons", [])})
    provisional = [_record_brief(db, a.uid) for a in db.scalars(
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.record_status == "Provisional",
                            restriction_clause(Asset)))]
    installations = [
        {**{k: v for k, v in inst.items() if k != "interval"},
         "position": _record_brief(db, inst["position_uid"]) if inst["position_uid"] else None,
         "asset": _record_brief(db, inst["asset_uid"]) if inst["asset_uid"] else None}
        for inst in engine.installations(db, status="Proposed") if inst["workspace_id"] == workspace_id
        and inst["record_status"] != "Retired"]
    return {"conflicts": conflicts, "proposals": proposals, "held_revisions": held,
            "provisional_records": provisional, "installation_proposals": installations,
            "counts": {"conflicts": len(conflicts), "blocking": sum(c["severity"] == "blocking" for c in conflicts),
                       "proposals": len(proposals), "held_revisions": len(held),
                       "installation_proposals": len(installations)}}


@router.get("/registry/report")
def registry_report(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The relation registry in warn mode (§6, S3b): every edge that breaks it."""
    from app.ledger import registry
    return registry.report(db, [workspace_id])


class LedgerOnlyIn(BaseModel):
    enabled: bool
    reason: str


@router.get("/ledger-only")
def ledger_only_status(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """§13 S5: whether this workspace's record facts change only through the
    ledger, and whether it can be switched on (its legacy records migrated)."""
    from app.ledger import legacy
    from app.models.workspace import Workspace
    w = db.get(Workspace, workspace_id)
    return {"enabled": bool(w and w.ledger_only), "legacy": legacy.gate(db, workspace_id)}


@router.put("/ledger-only")
def set_ledger_only(body: LedgerOnlyIn, identity=Depends(get_identity),
                    workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import legacy
    from app.models.workspace import Workspace
    if not body.reason.strip():
        raise HTTPException(status_code=422, detail={"error": "give a reason; it is recorded"})
    w = db.get(Workspace, workspace_id)
    if body.enabled:
        g = legacy.gate(db, workspace_id)
        if not g["ok"]:
            raise HTTPException(status_code=409, detail={
                "error": "migrate the workspace's legacy records first (§12): "
                         f"{len(g['blocked'])} blocked, {len(g['mixed_open'])} to review, {g['unplanned']} unplanned",
                "legacy": g})
    engine._record_decision(db, "set_ledger_only", actor_of(identity), workspace_id,
                            value={"enabled": body.enabled, "before": w.ledger_only}, reason=body.reason)
    w.ledger_only = body.enabled
    db.commit()
    return {"enabled": w.ledger_only}


@router.get("/invariants/report")
def invariants_report(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The data invariants (installations, access points, ports, tickets,
    identifier uniqueness) checked on the state as it is."""
    from app.ledger import invariants
    return invariants.report(db, [workspace_id])


@router.get("/review/queues")
def review_queues(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """§18.2: each queue's size, age distribution and escalation, and who owns it."""
    from app.ledger import queues
    return queues.dashboard(db, workspace_id)


@router.post("/review/escalate")
def escalate_review(workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """Run the escalation for this workspace now (the scheduled job runs it for all)."""
    from app.ledger import queues
    sent = queues.escalate(db, workspace_id=workspace_id)
    db.commit()
    return sent


@router.get("/records/{uid}/facts")
def provenance(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Why each value is what it is: every contributing claim and decision."""
    record = db.get(Asset, uid)
    if record is None or not asset_visible_in(record, workspace_id):
        raise HTTPException(status_code=404, detail="Record not found")
    facts: dict = {}
    hidden = {f"attr:{k}" for k in hidden_fields(db, record)}
    for f in db.scalars(select(FactState).where(FactState.subject_uid == uid).order_by(FactState.id)):
        if f.predicate in hidden:
            continue
        entry = {"status": f.status, "rank": f.rank, "effective": f.effective}
        if f.contributor.startswith("claim:"):
            c = db.get(Claim, f.contributor[6:])
            stream = db.get(LedgerStream, c.stream_id)
            ev = db.scalar(select(ClaimEvent).where(ClaimEvent.claim_id == c.claim_id)
                           .order_by(ClaimEvent.seq.desc()).limit(1))
            rev = db.get(SourceRevision, ev.revision_id) if ev else None
            entry.update({"kind": "claim", "claim_id": c.claim_id, "value": c.value, "polarity": c.polarity,
                          "method": c.method, "rule_id": c.rule_id, "stream": stream.id if stream else c.stream_id,
                          "source_kind": stream.kind if stream else None,
                          "revision": rev.revision if rev else None, "observed_at": rev.observed_at if rev else None,
                          "evidence": ev.evidence if ev else None})
        else:
            d = db.scalar(select(Decision).where(Decision.decision_id == f.contributor[9:]))
            entry.update({"kind": "decision", "decision_id": d.decision_id, "decision": d.kind, "value": d.value,
                          "actor": d.actor, "at": d.at, "reason": d.reason})
        facts.setdefault(f"{f.predicate}|{f.member or ''}", {"predicate": f.predicate, "member": f.member,
                                                             "contributors": []})["contributors"].append(entry)
    return {"record": _record_brief(db, uid), "facts": list(facts.values()),
            "processing": engine.pending_derive(db, record.workspace_id),
            "source_refs": [b.source_ref for b in db.scalars(select(IdentityBinding)
                                                             .where(IdentityBinding.uid == uid))]}


@router.post("/rebuild")
def rebuild(workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    before = engine.snapshot(db, workspace_id)
    engine.rebuild(db, workspace_id)
    after = engine.snapshot(db, workspace_id)
    db.commit()
    return {"identical": before == after}


# --------------------------------------------------------------------------- installations

def _view(db: Session, v: dict, certainty: Optional[str] = None, at=None) -> dict:
    state, state_certainty = temporal.state_at(v["interval"], temporal.parse_instant(at) if at else engine.now())
    return {"uid": v["uid"], "key": v["key"], "status": v["status"], "valid_from": v["valid_from"],
            "valid_until": v["valid_until"], "removal_reason": v["removal_reason"],
            "temporal_state": state, "temporal_certainty": certainty or state_certainty,
            "position": _record_brief(db, v["position_uid"]) if v["position_uid"] else None,
            "asset": _record_brief(db, v["asset_uid"]) if v["asset_uid"] else None}


@installations_router.get("")
def list_installations(position_uid: Optional[str] = None, asset_uid: Optional[str] = None,
                       at: Optional[datetime] = Query(None),
                       workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    if not position_uid and not asset_uid:
        raise HTTPException(status_code=422, detail="position_uid or asset_uid is required")
    if at is not None:
        rows = engine.installations_at(db, at, position_uid=position_uid, asset_uid=asset_uid)
        return [_view(db, v, v["certainty"], at) for v in rows]
    return [_view(db, v) for v in engine.installations(db, position_uid=position_uid, asset_uid=asset_uid)]


class ConfirmIn(BaseModel):
    valid_from: Optional[dict] = None


@installations_router.post("/{uid}/confirm")
def confirm_installation(uid: str, body: ConfirmIn, identity=Depends(get_identity),
                         workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    actor = actor_of(identity)
    try:
        service.confirm_installation(db, workspace_id, actor, uid, valid_from=body.valid_from)
    except (LedgerError, temporal.TemporalError) as exc:
        _fail(db, exc, workspace_id, actor, [{"kind": "confirm_installation", "uid": uid}])
    db.commit()
    return {"ok": True}


@installations_router.post("/{uid}/reject")
def reject_installation(uid: str, identity=Depends(get_identity),
                        workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    try:
        service.reject_installation(db, workspace_id, actor_of(identity), uid)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {"ok": True}


class SwapIn(BaseModel):
    position_uid: str
    new_asset_uid: str
    at: datetime
    precision: str = "instant"
    reason: str = "Unknown"


@installations_router.post("/swap")
def swap(body: SwapIn, identity=Depends(get_identity),
         workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    actor = actor_of(identity)
    try:
        result = service.swap(db, workspace_id, actor, body.position_uid, body.new_asset_uid,
                              temporal.instant(body.at, body.precision), body.reason)
    except (LedgerError, temporal.TemporalError) as exc:
        _fail(db, exc, workspace_id, actor, [{"kind": "swap", **body.model_dump(mode="json")}])
    db.commit()
    return result


@router.post("/policy/activate")
def activate(body: Optional[dict] = None, identity=Depends(get_identity),
             workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    try:
        row = engine.activate_policy(db, body or None, actor_of(identity))
    except PolicyError as exc:
        raise HTTPException(status_code=422, detail={"errors": exc.errors})
    db.commit()
    return {"version": row.version, "report": row.report}


# --------------------------------------------------------------------------- rules (§7.9)

@router.get("/rules")
def rule_catalogue(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    active = engine.active_ruleset(db, workspace_id)
    return {"rules": [{"rule_id": rid, "family": r["family"], "meaning": r["meaning"],
                       "supersedes": r.get("supersedes"), "carries_rejections": bool(r.get("carries_rejections")),
                       "implementations": r["impl"], "signature": rules.signature_hash(rid),
                       "active": active.rules.get(r["family"]) == rid,
                       "active_impl": active.impl_of(rid) if active.rules.get(r["family"]) == rid else None}
                      for rid, r in sorted(rules.RULES.items())],
            "check": rules.check_catalogue()}


class RulesetIn(BaseModel):
    rules: dict[str, str]
    impl: dict[str, str] = {}


@router.post("/rulesets")
def activate_ruleset(body: RulesetIn, identity=Depends(get_identity),
                     workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    try:
        results = engine.activate_ruleset(db, workspace_id, body.rules, body.impl, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {"streams": results}


# --------------------------------------------------------------------------- tickets (§8.6)

@router.get("/tickets/{uid}/links")
def ticket_links(uid: str, workspace_id: str = Depends(require_permission("read", resource="tickets")),
                 db: Session = Depends(get_db)):
    from app.models.issue import Issue
    issue = db.get(Issue, uid)
    if issue is None or issue.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return tickets.links_of_ticket(db, uid)


@router.get("/records/{uid}/tickets")
def record_tickets(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Tickets a record is involved in without being their subject, and its counts."""
    record = db.get(Asset, uid)
    if record is None or not asset_visible_in(record, workspace_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return {"counts": tickets.record_counts(db, uid), "involved": tickets.tickets_involving(db, uid)}


# --------------------------------------------------------------------------- access points and ports (§9)

def _ap_out(db: Session, v: dict) -> dict:
    return {**{k: val for k, val in v.items() if k != "interval"},
            "position": _record_brief(db, v["position_uid"]) if v["position_uid"] else None,
            "successor_record": _record_brief(db, v["successor"]) if v.get("successor") else None}


@access_points_router.get("")
def list_access_points(address: Optional[str] = None, at: Optional[datetime] = Query(None),
                       workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Every Access Point for an address, and — with `at` — who used it then."""
    out = {"access_points": [_ap_out(db, v) for v in connectivity.access_points(db, workspace_id, address)]}
    if address and at is not None:
        out["used_by"] = [{**r, "position": _record_brief(db, r["position_uid"]) if r["position_uid"] else None,
                           "asset": _record_brief(db, r["asset_uid"]) if r["asset_uid"] else None}
                          for r in connectivity.who_used(db, workspace_id, address, at)]
    return out


@access_points_router.get("/{uid}")
def access_point_history(uid: str, workspace_id: str = Depends(require_permission("read")),
                         db: Session = Depends(get_db)):
    ap = db.get(Asset, uid)
    if ap is None or ap.workspace_id != workspace_id or ap.type != engine.ACCESS_POINT:
        raise HTTPException(status_code=404, detail="Access Point not found")
    address = (ap.attributes or {}).get("address")
    history = connectivity.access_points(db, workspace_id, address) if address else [
        connectivity.access_point_view(db, ap)]
    return {"access_point": _ap_out(db, connectivity.access_point_view(db, ap)),
            "address_history": [_ap_out(db, v) for v in history]}


class ReassignIn(BaseModel):
    position_uid: str
    at: dict


@access_points_router.post("/{uid}/reassign")
def reassign_access_point(uid: str, body: ReassignIn, identity=Depends(get_identity),
                          workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    actor = actor_of(identity)
    try:
        new_uid = service.reassign_access_point(db, workspace_id, actor, uid, body.position_uid, body.at)
    except (LedgerError, temporal.TemporalError) as exc:
        _fail(db, exc, workspace_id, actor, [{"kind": "reassign", "uid": uid, **body.model_dump(mode="json")}])
    db.commit()
    return _ap_out(db, connectivity.access_point_view(db, db.get(Asset, new_uid)))


@router.get("/segments/{uid}/port")
def segment_port(uid: str, at: Optional[datetime] = Query(None),
                 workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Where a Bus Segment attaches (now, or at `at`), and why."""
    seg = db.get(Asset, uid)
    if seg is None or seg.workspace_id != workspace_id or seg.type != connectivity.BUS_SEGMENT:
        raise HTTPException(status_code=404, detail="Bus Segment not found")
    m = connectivity.match_segment(db, seg, temporal.parse_instant(at) if at else None)
    return {**m, "port": _record_brief(db, m["port_uid"]) if m.get("port_uid") else None,
            "unit": _record_brief(db, m["unit_uid"]) if m.get("unit_uid") else None}


class PortMapIn(BaseModel):
    installation_uid: str
    port_uid: str


@router.post("/segments/{uid}/port-map")
def confirm_port_map(uid: str, body: PortMapIn, identity=Depends(get_identity),
                     workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """A person identifies the intended port for this Installation. It never
    authorizes an incompatible connection (§9.3 step 1)."""
    actor = actor_of(identity)
    batch = [connectivity.confirm_port_map(uid, body.installation_uid, body.port_uid,
                                           connectivity.active_port_map_decisions(db, uid))]
    try:
        engine.apply_decisions(db, workspace_id, actor, batch)
    except LedgerError as exc:
        _fail(db, exc, workspace_id, actor, batch)
    db.commit()
    seg = db.get(Asset, uid)
    return connectivity.match_segment(db, seg)


# --------------------------------------------------------------------------- identity (§10)

class MergeIn(BaseModel):
    survivor_uid: str
    loser_uid: str
    reason: Optional[str] = None


@router.post("/identity/merge")
def merge_records(body: MergeIn, identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger.identity import merge
    actor = actor_of(identity)
    try:
        d = merge(db, workspace_id, actor, body.survivor_uid, body.loser_uid, body.reason)
    except LedgerError as exc:
        _fail(db, exc, workspace_id, actor, [{"kind": "merge", **body.model_dump()}])
    db.commit()
    return {"decision_id": d.decision_id}


class DismissIn(BaseModel):
    records: list[str]
    kind: str = "reject_candidate"   # or confirm_new
    reason: Optional[str] = None


@router.post("/identity/dismiss")
def dismiss_candidate(body: DismissIn, identity=Depends(get_identity),
                      workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger.identity import dismiss_candidate as dismiss
    try:
        d = dismiss(db, workspace_id, actor_of(identity), body.records, body.kind, body.reason)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {"decision_id": d.decision_id}


class UnmergeIn(BaseModel):
    merge_decision_id: str
    reason: Optional[str] = None


@router.post("/identity/unmerge")
def unmerge_records(body: UnmergeIn, identity=Depends(get_identity),
                    workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger.identity import unmerge
    actor = actor_of(identity)
    try:
        d = unmerge(db, workspace_id, actor, body.merge_decision_id, body.reason)
    except LedgerError as exc:
        _fail(db, exc, workspace_id, actor, [{"kind": "unmerge", **body.model_dump()}])
    db.commit()
    return {"decision_id": d.decision_id}


# --------------------------------------------------------------------------- migration domains (§17)

domains_router = APIRouter(prefix="/v1/domains", tags=["migration domains"])


def _owned_domain(db: Session, domain_id: str, workspace_id: str):
    from app.models.ledger import LedgerDomain
    d = db.get(LedgerDomain, domain_id)
    if d is None or d.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Domain not found")
    return d


class DomainIn(BaseModel):
    id: str
    name: str
    resource: str = "objects"
    stream_ids: list[str] = []
    pilot: bool = False
    archive_url: Optional[str] = None


@domains_router.post("", status_code=201)
def create_domain(body: DomainIn, workspace_id: str = Depends(require_permission("approve")),
                  db: Session = Depends(get_db)):
    from app.ledger import cutover
    try:
        d = cutover.create_domain(db, workspace_id, body.id, body.name, resource=body.resource,
                                  stream_ids=body.stream_ids, pilot=body.pilot, archive_url=body.archive_url)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return cutover.domain_view(db, d)


@domains_router.get("")
def list_domains(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    return [cutover.domain_view(db, d) for d in cutover.domains_of(db, workspace_id)]


@domains_router.get("/{domain_id}")
def get_domain(domain_id: str, workspace_id: str = Depends(require_permission("read")),
               db: Session = Depends(get_db)):
    from app.ledger import cutover
    d = _owned_domain(db, domain_id, workspace_id)
    report = cutover.latest_report(db, domain_id)
    from app.ledger import entry
    return {**cutover.domain_view(db, d), "exit_criteria": cutover.exit_criteria(db, domain_id),
            "entry_criteria": entry.criteria(db, d) if d.stage in ("T0", "T1", "T2") else None,
            "entry_attestations": entry.ATTESTATIONS,
            "report": report.body if report else None, "stages": cutover.STAGE_NAMES}


class StewardsIn(BaseModel):
    steward: str
    backup: str


@domains_router.put("/{domain_id}/stewards")
def set_stewards(domain_id: str, body: StewardsIn, identity=Depends(get_identity),
                 workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    try:
        d = cutover.set_stewards(db, domain_id, actor_of(identity), body.steward, body.backup)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return cutover.domain_view(db, d)


class StageIn(BaseModel):
    stage: str


@domains_router.post("/{domain_id}/stage")
def set_stage(domain_id: str, body: StageIn, identity=Depends(get_identity),
              workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    try:
        d = cutover.advance(db, domain_id, body.stage, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return cutover.domain_view(db, d)


class FreezeIn(BaseModel):
    watermark: dict
    manifest: dict
    attestations: dict[str, bool] = {}
    waivers: dict[str, str] = {}          # criterion id → the governance group's reason


@domains_router.post("/{domain_id}/freeze")
def freeze_domain(domain_id: str, body: FreezeIn, identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    try:
        d = cutover.freeze(db, domain_id, actor_of(identity), body.watermark, body.manifest,
                           body.attestations, body.waivers)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return cutover.domain_view(db, d)


class ManifestIn(BaseModel):
    manifest: dict


@domains_router.post("/{domain_id}/reconcile")
def reconcile_domain(domain_id: str, body: ManifestIn, identity=Depends(get_identity),
                     workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    report = cutover.reconcile(db, domain_id, body.manifest, actor_of(identity))
    db.commit()
    return {"id": report.id, "passed": report.passed, "body_hash": report.body_hash, **report.body}


@domains_router.get("/{domain_id}/reports")
def list_reports(domain_id: str, workspace_id: str = Depends(require_permission("read")),
                 db: Session = Depends(get_db)):
    from app.models.ledger import ReconciliationReport
    _owned_domain(db, domain_id, workspace_id)
    return [{"id": r.id, "passed": r.passed, "created_at": r.created_at, "actor": r.actor,
             "unexplained": r.body["unexplained"], "body_hash": r.body_hash}
            for r in db.scalars(select(ReconciliationReport).where(ReconciliationReport.domain_id == domain_id)
                                .order_by(ReconciliationReport.created_at.desc()))]


class ExplainIn(BaseModel):
    difference: str
    reason: str


@domains_router.post("/{domain_id}/explain")
def explain_difference(domain_id: str, body: ExplainIn, identity=Depends(get_identity),
                       workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """A difference is explained by a decision (a deliberate merge, a record
    left behind on purpose); the next report counts it as explained."""
    _owned_domain(db, domain_id, workspace_id)
    d = engine._record_decision(db, "explain_difference", actor_of(identity), workspace_id,
                                target={"domain": domain_id, "difference": body.difference}, reason=body.reason)
    db.commit()
    return {"decision_id": d.decision_id}


class ExitIn(BaseModel):
    attestations: dict[str, bool] = {}


@domains_router.post("/{domain_id}/exit")
def sign_exit(domain_id: str, body: ExitIn, identity=Depends(get_identity),
              workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    try:
        d = cutover.sign_exit(db, domain_id, actor_of(identity), body.attestations)
    except LedgerError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "error": str(exc), "criteria": cutover.exit_criteria(db, domain_id, body.attestations)})
    db.commit()
    return cutover.domain_view(db, d)


# --------------------------------------------------------------------------- lookup (§17.7)

lookup_router = APIRouter(prefix="/v1/lookup", tags=["lookup"])


def _readable_workspaces(db: Session, identity) -> list[str]:
    from app.auth import PatIdentity
    from app.models.workspace import Workspace
    from app.services.permissions import resolve_permission
    if isinstance(identity, PatIdentity):
        return [identity.workspace_id]
    return [w.id for w in db.scalars(select(Workspace))
            if resolve_permission(db, identity.user, w.id, "read", "objects")
            or resolve_permission(db, identity.user, w.id, "read", "tickets")]


def _resolve_one(db: Session, identifier: str, workspaces: list[str]) -> dict:
    from app.ledger import lookup as lk
    from app.models.issue import Issue
    hit = lk.resolve(db, identifier, workspaces)
    if hit is not None:
        record = db.get(Issue, hit["uid"]) if hit["kind"] == "ticket" else db.get(Asset, hit["uid"])
        if record is not None and can_see(record):
            return {"status": "migrated", **hit}
    return {"status": "not migrated", "identifier": identifier,
            "archive": lk.archive_location(db, identifier, workspaces)}


class LookupBatchIn(BaseModel):
    identifiers: list[str]


@lookup_router.post("/batch")
def lookup_batch(body: LookupBatchIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Many identifiers at once, for an integration re-pointing its stored
    Jira or Insight references (§19 item 8). Answers in the same order."""
    if len(body.identifiers) > 1000:
        raise HTTPException(status_code=422, detail="at most 1000 identifiers per call")
    workspaces = _readable_workspaces(db, identity)
    return [{"identifier": i, **_resolve_one(db, i, workspaces)} for i in body.identifiers]


@lookup_router.get("/{identifier:path}")
def lookup(identifier: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """A Jira key, an old Jira or Insight URL, an Insight key or objectId:
    the ARGUS record it became, or where it can still be read."""
    result = _resolve_one(db, identifier, _readable_workspaces(db, identity))
    if result["status"] == "migrated":
        return result
    raise HTTPException(status_code=404, detail=result)


@domains_router.post("/{domain_id}/reversion-export")
def reversion_export(domain_id: str, identity=Depends(get_identity),
                     workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """The pilot's one-off change report since W (I-SOR-2)."""
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    try:
        report = cutover.reversion_export(db, domain_id, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return report


class RevertIn(BaseModel):
    reason: str


@domains_router.post("/{domain_id}/revert")
def revert_pilot(domain_id: str, body: RevertIn, identity=Depends(get_identity),
                 workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import cutover
    _owned_domain(db, domain_id, workspace_id)
    try:
        d = cutover.revert_pilot(db, domain_id, actor_of(identity), body.reason)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return cutover.domain_view(db, d)


# --------------------------------------------------------------------------- audit (§19 item 2)

@router.get("/records/{uid}/audit")
def record_audit(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Everything the ledger recorded about one record, oldest first."""
    from app.ledger.audit import record_trail
    record = db.get(Asset, uid)
    if record is None or not asset_visible_in(record, workspace_id):
        raise HTTPException(status_code=404, detail="Record not found")
    hidden = {f"attr:{k}" for k in hidden_fields(db, record)}
    return [e for e in record_trail(db, uid) if e.get("predicate") not in hidden]


@router.get("/audit/digests")
def audit_digests(limit: int = Query(30, ge=1, le=366), workspace_id: str = Depends(require_permission("read")),
                  db: Session = Depends(get_db)):
    from app.models.ledger import AuditDigest
    return [{"day": d.day, "digest": d.digest, "prev_digest": d.prev_digest, "counts": d.counts,
             "sealed_at": d.sealed_at}
            for d in db.scalars(select(AuditDigest).order_by(AuditDigest.day.desc()).limit(limit))]


@router.post("/audit/seal")
def audit_seal(workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """Seal yesterday (and any unsealed day before it). Normally a daily job:
    `python -m app.ledger audit-digest`."""
    from app.ledger.audit import seal_day
    try:
        row = seal_day(db)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    return {"day": row.day, "digest": row.digest}


@router.get("/audit/verify")
def audit_verify(workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger.audit import verify
    return verify(db)
