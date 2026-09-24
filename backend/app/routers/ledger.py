"""The fact ledger's API: sources, decisions, the review queue, provenance and
installation history (asset-model-revision §7, §8, §11, §13 step S1)."""
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import OidcIdentity, get_identity, require_permission
from app.db import get_db
from app.ledger import engine, service, temporal
from app.ledger.engine import LedgerError
from app.ledger.policy import PolicyError
from app.models.asset import Asset
from app.models.ledger import (Claim, ClaimEvent, Conflict, Decision, FactState, IdentityBinding, LedgerStream,
                               RevisionEvent, SourceRevision, StreamHead)

router = APIRouter(prefix="/v1/ledger", tags=["ledger"])
installations_router = APIRouter(prefix="/v1/installations", tags=["installations"])


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


@router.post("/records/{uid}/edit")
def edit(uid: str, body: EditIn, identity=Depends(get_identity),
         workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    actor = actor_of(identity)
    try:
        if body.present is not None:
            service.set_member(db, workspace_id, actor, uid, body.predicate, body.member, body.present, body.reason)
        else:
            service.edit_value(db, workspace_id, actor, uid, body.predicate, body.value, body.reason)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- review and provenance

def _record_brief(db: Session, uid: str) -> Optional[dict]:
    a = db.get(Asset, uid)
    return {"uid": a.uid, "key": a.key, "name": a.name, "type": a.type, "record_status": a.record_status} if a else None


@router.get("/review")
def review(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Everything waiting on a person, with its owner-facing context."""
    conflicts = [{"conflict_id": c.conflict_id, "type": c.conflict_type, "severity": c.severity,
                  "predicate": c.predicate, "member": c.member, "detail": c.detail,
                  "record": _record_brief(db, c.subject_uid)}
                 for c in db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id))]
    proposals = []
    ws_uids = set(db.scalars(select(Asset.uid).where(Asset.workspace_id == workspace_id)))
    for f in db.scalars(select(FactState).where(FactState.status == "proposed")):
        if f.subject_uid not in ws_uids or not f.contributor.startswith("claim:"):
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
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.record_status == "Provisional"))]
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


@router.get("/records/{uid}/facts")
def provenance(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Why each value is what it is: every contributing claim and decision."""
    record = db.get(Asset, uid)
    if record is None or not (record.workspace_id == workspace_id or record.is_global):
        raise HTTPException(status_code=404, detail="Record not found")
    facts: dict = {}
    for f in db.scalars(select(FactState).where(FactState.subject_uid == uid).order_by(FactState.id)):
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
