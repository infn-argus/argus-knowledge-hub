"""AI proposals on records that already exist (§23.5, §23.11).

A person with a datasheet, a nameplate photo or a note about an asset asks
the assistant what it says about the record. Every value that differs from
the record becomes an AI claim in the ledger and waits in the review queue.
Nothing on the record changes until the owner decides:

* confirm: the value becomes the owner's own confirmed statement, and the
  AI claim is accepted;
* edit: the owner's corrected value is confirmed, and the AI claim is
  rejected as `corrected`;
* reject: the AI claim is rejected, with the owner's reason.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intake import assist
from app.intake.outcome import _predicate
from app.ledger import engine, service
from app.ledger.engine import LedgerError, ParsedClaim
from app.models.asset import Asset
from app.models.ledger import Claim, ClaimEvent, LedgerStream

AI_METHODS = ("ai_extracted", "ai_resolved", "ai_classified", "ai_inferred")


class ProposalError(LedgerError):
    pass


def _current(asset: Asset, field: str):
    if field == "schema_uid":
        return asset.schema_uid
    if field == "name":
        return asset.name
    if field.startswith("attributes."):
        return (asset.attributes or {}).get(field.split(".", 1)[1])
    return None


def propose_asset(db: Session, workspace_id: str, actor: str, endpoint, uid: str, *, text: str = "",
                  image: Optional[bytes] = None, mime_type: str = "image/jpeg", file_refs: Optional[list] = None,
                  profile_id: Optional[str] = None, grants=None) -> dict:
    asset = db.get(Asset, uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise ProposalError("not a record of this workspace")
    draft = {"uid": uid, "schema_uid": asset.schema_uid, "name": asset.name, "key": asset.key,
             "attributes": dict(asset.attributes or {})}
    out = assist.assist_asset(db, workspace_id, actor, endpoint, text=text, image=image, mime_type=mime_type,
                              draft=draft, grants=grants, profile_id=profile_id, file_refs=file_refs)
    from app.models.intake import IntakeRun
    rule_id = db.get(IntakeRun, out["run_id"]).rule_id           # carries the model profile (§23.8)
    stream = engine.register_stream(db, f"ai:{workspace_id}:asset.describe", workspace_id, "ai")
    claims, proposed, same = [], [], []
    for field, suggestion in out["fields"].items():
        if field == "key":
            continue                              # a record's key is its identity, not a proposal
        pv = _predicate(field, suggestion)
        if pv is None or pv[1] in (None, "", []):
            continue
        if str(_current(asset, field) or "").strip().lower() == str(suggestion["value"]).strip().lower():
            same.append(field)
            continue
        predicate, value = pv
        claims.append(ParsedClaim(f"uid:{uid}", predicate, value, method=suggestion.get("method") or "ai_extracted",
                                  rule_id=rule_id,
                                  confidence=suggestion.get("confidence"),
                                  evidence={"intake_run": out["run_id"], "quote": suggestion.get("evidence"),
                                            "grounded": suggestion.get("grounded"),
                                            "current": _current(asset, field) if field != "schema_uid" else asset.type}))
        proposed.append({"field": field, "value": suggestion["value"], "label": suggestion.get("label"),
                         "current": _current(asset, field) if field != "schema_uid" else asset.type,
                         "confidence": suggestion.get("confidence"), "evidence": suggestion.get("evidence")})
    if claims:
        # Proposed, not accepted: AI methods are advisory and never auto-accepted (§23.9).
        engine.add_manual_claims(db, stream, claims, cause=f"intake run {out['run_id']}")
        engine.project_subject(db, uid, f"intake run {out['run_id']}")     # so the queue shows them now
    return {"run_id": out["run_id"], "profile_id": out.get("profile_id"), "proposed": proposed,
            "unchanged": same, "dropped": out["dropped"], "message": out.get("message")}


def evidence_of(db: Session, claim_id: str) -> dict:
    ev = db.scalar(select(ClaimEvent).where(ClaimEvent.claim_id == claim_id).order_by(ClaimEvent.seq.desc()).limit(1))
    return {"evidence": (ev.evidence if ev else None) or {}, "confidence": ev.confidence if ev else None}


def decide(db: Session, workspace_id: str, actor: str, claim_id: str, action: str, *,
           value=None, reason: Optional[str] = None) -> dict:
    claim = db.get(Claim, claim_id)
    if claim is None or claim.method not in AI_METHODS:
        raise ProposalError("not an AI proposal")
    stream = db.get(LedgerStream, claim.stream_id)
    uid = engine.resolve_ref(db, claim.source_ref)
    asset = db.get(Asset, uid) if uid else None
    if asset is None or asset.workspace_id != workspace_id or stream is None or stream.workspace_id != workspace_id:
        raise ProposalError("the proposal is not about a record of this workspace")
    if action not in ("confirm", "edit", "reject"):
        raise ProposalError("action is confirm, edit or reject")
    if action == "reject":
        if not (reason or "").strip():
            raise ProposalError("say why it is wrong")
        engine.apply_decisions(db, workspace_id, actor, [
            {"kind": "reject", "target": {"claim_id": claim_id}, "reason": reason.strip()}])
        return {"claim_id": claim_id, "action": "reject"}
    chosen = claim.value if action == "confirm" else value
    if chosen in (None, "", []):
        raise ProposalError("give the corrected value")
    why = (reason or "").strip() or ("confirmed from an AI proposal" if action == "confirm" else "corrected an AI proposal")
    if claim.predicate == "type":
        service.retype(db, workspace_id, actor, uid, str(chosen), reason=why)
    else:
        service.edit_values(db, workspace_id, actor, uid, {claim.predicate: chosen}, reason=why)
    kind = "accept" if action == "confirm" else "reject"
    engine.apply_decisions(db, workspace_id, actor, [
        {"kind": kind, "target": {"claim_id": claim_id},
         "reason": "kept" if action == "confirm" else "corrected"}])
    return {"claim_id": claim_id, "action": action, "value": chosen}
