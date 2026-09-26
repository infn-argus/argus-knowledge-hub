"""Guided and AI-assisted entry (asset-model-revision §23).

`/guide/{kind}` checks a draft and says what to do next; it needs no model
and works everywhere. `/assist/{kind}` fills a draft from a description or
a photograph and records the run; it needs a working AI endpoint, and when
there is none the form still works (§23.13). `/runs/{id}/outcome` records,
after the save, which suggestions the person kept.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_grants, get_identity, require_permission
from app.db import get_db
from app.intake import assist, guide, outcome
from app.routers.ai import _usable_config, endpoint_for
from app.routers.ledger import actor_of
from app.services.asset_vision import MAX_IMAGE_BYTES
from app.services.llm import LLMError

router = APIRouter(prefix="/v1/intake", tags=["intake"])

RESOURCE = {"asset": "objects", "ticket": "tickets", "document": "documents"}


class GuideIn(BaseModel):
    draft: dict = {}


class AssistIn(BaseModel):
    text: str = ""
    draft: dict = {}


class OutcomeIn(BaseModel):
    record_uid: str
    final: dict = {}


@router.post("/guide/asset")
def guide_asset(body: GuideIn, workspace_id: str = Depends(require_permission("read")),
                grants=Depends(get_grants), db: Session = Depends(get_db)):
    """What is missing or wrong in this asset draft, and the next question."""
    out = guide.guide_asset(db, workspace_id, body.draft, grants)
    db.rollback()                                   # checking writes nothing
    return out


@router.post("/guide/ticket")
def guide_ticket(body: GuideIn, workspace_id: str = Depends(require_permission("read", resource="tickets")),
                 grants=Depends(get_grants), db: Session = Depends(get_db)):
    out = guide.guide_ticket(db, workspace_id, body.draft, grants)
    db.rollback()
    return out


@router.post("/guide/document")
def guide_document(body: GuideIn, workspace_id: str = Depends(require_permission("read", resource="documents")),
                   grants=Depends(get_grants), db: Session = Depends(get_db)):
    out = guide.guide_document(db, workspace_id, body.draft, grants)
    db.rollback()
    return out


def _run(db: Session, fn):
    try:
        out = fn()
    except LLMError as exc:
        db.commit()                                 # the failed run is recorded; nothing else was written
        raise HTTPException(status_code=502, detail=f"The assistant is unavailable: {exc}. Fill in the form "
                                                    "by hand; nothing is lost.")
    db.commit()
    return out


@router.post("/assist/asset")
def assist_asset(body: AssistIn, identity=Depends(get_identity), workspace_id: str = Depends(require_permission("create")),
                 grants=Depends(get_grants), db: Session = Depends(get_db)):
    """Fill an asset draft from a description. Saves nothing but the run's audit row."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Describe the equipment first.")
    config = _usable_config(db, workspace_id)
    return _run(db, lambda: assist.assist_asset(db, workspace_id, actor_of(identity), endpoint_for(config),
                                                text=body.text, draft=body.draft, grants=grants))


@router.post("/assist/asset/photo")
async def assist_asset_photo(file: UploadFile = File(...), text: str = Form(""), draft: str = Form("{}"),
                             identity=Depends(get_identity), workspace_id: str = Depends(require_permission("create")),
                             grants=Depends(get_grants), db: Session = Depends(get_db)):
    """Fill an asset draft from a photograph (a nameplate, a label), with any words the person adds."""
    config = _usable_config(db, workspace_id)
    if not config.vision_model:
        raise HTTPException(status_code=409, detail="No vision model is configured for this workspace's AI endpoint.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="The photograph was empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"That photograph is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    try:
        parsed = json.loads(draft or "{}")
    except ValueError:
        parsed = {}
    return _run(db, lambda: assist.assist_asset(
        db, workspace_id, actor_of(identity), endpoint_for(config), text=text, image=content,
        mime_type=file.content_type or "image/jpeg", draft=parsed if isinstance(parsed, dict) else {}, grants=grants))


@router.post("/assist/ticket")
def assist_ticket(body: AssistIn, identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("create", resource="tickets")),
                  grants=Depends(get_grants), db: Session = Depends(get_db)):
    """Turn a report, in the person's own words, into a ticket draft."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Say what happened first.")
    config = _usable_config(db, workspace_id)
    return _run(db, lambda: assist.assist_ticket(db, workspace_id, actor_of(identity), endpoint_for(config),
                                                 text=body.text, draft=body.draft, grants=grants))


@router.post("/assist/document")
def assist_document(body: AssistIn, identity=Depends(get_identity),
                    workspace_id: str = Depends(require_permission("create", resource="documents")),
                    grants=Depends(get_grants), db: Session = Depends(get_db)):
    """Title, type, summary and keywords from a description or the document's text."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Describe the document, or paste its text, first.")
    config = _usable_config(db, workspace_id)
    return _run(db, lambda: assist.assist_document(db, workspace_id, actor_of(identity), endpoint_for(config),
                                                   text=body.text, draft=body.draft, grants=grants))


@router.post("/runs/{run_id}/outcome", status_code=201)
def record_outcome(run_id: str, body: OutcomeIn, identity=Depends(get_identity),
                   workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """After the save: which suggestions the person kept, corrected or left out."""
    from app.models.intake import IntakeRun
    run = db.get(IntakeRun, run_id)
    if run is None or run.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="No such intake run")
    # Recording the outcome needs the right to create what the run was for.
    from app.auth import PatIdentity, resolve_permission
    if not isinstance(identity, PatIdentity) and not resolve_permission(
            db, identity.user, workspace_id, "create", RESOURCE[run.kind]):
        raise HTTPException(status_code=403, detail="Not permitted")
    try:
        out = outcome.record(db, workspace_id, actor_of(identity), run_id, body.record_uid, body.final)
    except outcome.OutcomeError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error": str(exc)})
    db.commit()
    return out


@router.get("/provenance/{record_uid}")
def provenance(record_uid: str, workspace_id: str = Depends(require_permission("read")),
               db: Session = Depends(get_db)):
    """Which of a record's values a model suggested, and what the person did with them."""
    return outcome.provenance(db, workspace_id, record_uid)
