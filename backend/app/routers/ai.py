"""Where a workspace's AI features point, and whether they work.

The endpoint is configured here rather than in the deployment because
different workspaces are entitled to different gateways, and because a
key typed into a form and encrypted at rest never has to travel through a
values file or a chat window to get there.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.llm_config import LLMConfig
from app.models.ai_suggestion import AISuggestion
from app.models.document import Document
from app.models.schema import Schema
from app.schemas.ai import (
    AIStatus,
    AskIn,
    AskOut,
    LLMCheckResult,
    LLMConfigIn,
    LLMConfigOut,
    SuggestionDecision,
    SuggestionDecisionResult,
    DraftDocumentIn,
    DraftDocumentOut,
    DraftTicketIn,
    DraftTicketOut,
    PhotoIdentification,
    ReviewDocumentIn,
    ReviewDocumentOut,
    SuggestionOut,
    SuggestRequest,
    SuggestRunResult,
)
from app.services.ai_authoring import draft_document, draft_ticket_fields, review_document
from app.services.ask import ask as run_ask
from app.services.asset_vision import MAX_IMAGE_BYTES, identify
from app.services.text_links import objects_mentioned
from app.services.ai_suggestions import suggest_document_types
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.llm import Endpoint, LLMError, check

router = APIRouter(prefix="/v1/ai", tags=["ai"])


def endpoint_for(config: LLMConfig) -> Endpoint:
    return Endpoint(
        base_url=config.base_url,
        model=config.model,
        embedding_model=config.embedding_model,
        vision_model=config.vision_model,
        api_key=decrypt_secret(config.encrypted_secret) if config.encrypted_secret else None,
    )


def _out(config: LLMConfig) -> LLMConfigOut:
    return LLMConfigOut(
        workspace_id=config.workspace_id,
        base_url=config.base_url,
        model=config.model,
        embedding_model=config.embedding_model,
        vision_model=config.vision_model,
        has_api_key=bool(config.encrypted_secret),
        enabled=config.enabled,
        allow_confidential=config.allow_confidential,
        last_checked_at=config.last_checked_at,
        last_check_ok=config.last_check_ok,
        last_check_error=config.last_check_error,
    )


def _get(db: Session, workspace_id: str) -> Optional[LLMConfig]:
    return db.get(LLMConfig, workspace_id)


@router.get("/config", response_model=Optional[LLMConfigOut])
def get_config(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    config = _get(db, workspace_id)
    return _out(config) if config else None


@router.put("/config", response_model=LLMConfigOut)
def put_config(
    body: LLMConfigIn,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    config = _get(db, workspace_id)
    if config is None:
        config = LLMConfig(workspace_id=workspace_id, base_url="", model="")
        db.add(config)

    config.base_url = body.base_url.strip()
    config.model = body.model.strip()
    config.embedding_model = (body.embedding_model or "").strip() or None
    config.vision_model = (body.vision_model or "").strip() or None
    config.enabled = body.enabled
    config.allow_confidential = body.allow_confidential

    if body.api_key is not None:
        # An empty string clears it; omitting the field keeps what is stored.
        config.encrypted_secret = encrypt_secret(body.api_key) if body.api_key else None

    # Settings changed, so whatever the last check proved is no longer about
    # this configuration.
    config.last_checked_at = None
    config.last_check_ok = None
    config.last_check_error = None

    db.commit()
    db.refresh(config)
    return _out(config)


@router.delete("/config", status_code=204)
def delete_config(
    workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)
):
    config = _get(db, workspace_id)
    if config is not None:
        db.delete(config)
        db.commit()


@router.post("/config/check", response_model=LLMCheckResult)
def check_config(
    workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)
):
    """Ask the endpoint whether it can do what it has been configured for."""
    config = _get(db, workspace_id)
    if config is None:
        raise HTTPException(status_code=404, detail="No AI endpoint is configured")

    ok, error, models = check(endpoint_for(config))
    config.last_checked_at = datetime.now(timezone.utc)
    config.last_check_ok = ok
    config.last_check_error = error
    db.commit()
    return LLMCheckResult(ok=ok, error=error, models=models)


@router.get("/status", response_model=AIStatus)
def status(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    """What the application asks before offering an AI action.

    A feature that cannot work should not be presented as if it could, and
    the reason belongs here rather than in a failed request later.
    """
    config = _get(db, workspace_id)
    if config is None:
        return AIStatus(
            configured=False,
            enabled=False,
            validated=False,
            reason="No AI endpoint is configured for this workspace.",
        )
    if not config.enabled:
        return AIStatus(
            configured=True,
            enabled=False,
            validated=bool(config.last_check_ok),
            model=config.model,
            has_embeddings=bool(config.embedding_model),
            has_vision=bool(config.vision_model),
            reason="AI features are switched off for this workspace.",
        )
    if not config.last_check_ok:
        return AIStatus(
            configured=True,
            enabled=True,
            validated=False,
            model=config.model,
            has_embeddings=bool(config.embedding_model),
            has_vision=bool(config.vision_model),
            reason=config.last_check_error
            or "The AI endpoint has not been checked since it was last changed.",
        )
    return AIStatus(
        configured=True,
        enabled=True,
        validated=True,
        model=config.model,
        has_embeddings=bool(config.embedding_model),
        has_vision=bool(config.vision_model),
    )


def _usable_config(db: Session, workspace_id: str) -> LLMConfig:
    """The endpoint, if it is actually usable. The same gate the status
    endpoint reports, enforced rather than trusted."""
    config = _get(db, workspace_id)
    if config is None:
        raise HTTPException(status_code=409, detail="No AI endpoint is configured")
    if not config.enabled:
        raise HTTPException(status_code=409, detail="AI features are switched off for this workspace")
    if not config.last_check_ok:
        raise HTTPException(
            status_code=409,
            detail=config.last_check_error
            or "The AI endpoint has not been checked since it was last changed.",
        )
    return config


@router.post("/suggest/document-types", response_model=SuggestRunResult)
def suggest_types(
    body: SuggestRequest,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    """Propose a type for documents that have none worth the name.

    Writes proposals, never a document. Applying one is a separate,
    deliberate act.
    """
    config = _usable_config(db, workspace_id)
    result = suggest_document_types(
        db,
        workspace_id,
        endpoint_for(config),
        config,
        only_untyped=body.only_untyped,
        # Bounded so one request stays well inside an ingress read timeout;
        # a caller with a backlog asks repeatedly rather than waiting on one
        # long request that a proxy will cut off at sixty seconds.
        limit=max(1, min(body.limit, 40)),
    )
    return SuggestRunResult(**result)


@router.get("/suggestions", response_model=list[SuggestionOut])
def list_suggestions(
    status: str = "proposed",
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    db: Session = Depends(get_db),
):
    rows = list(db.scalars(
        select(AISuggestion)
        .where(AISuggestion.workspace_id == workspace_id, AISuggestion.status == status)
        .order_by(AISuggestion.created_at.desc())
    ))
    # Names rather than uids, so the list reads without a second lookup.
    titles = {
        d.uid: d.title
        for d in db.scalars(select(Document).where(Document.workspace_id == workspace_id))
    }
    schema_names = {
        s.uid: s.name
        for s in db.scalars(select(Schema).where(Schema.workspace_id == workspace_id))
    }
    out = []
    for row in rows:
        item = SuggestionOut.model_validate(row)
        item.target_label = titles.get(row.target_uid)
        item.previous_label = schema_names.get(row.previous_value or "")
        out.append(item)
    return out


@router.post("/suggestions/accept", response_model=SuggestionDecisionResult)
def accept_suggestions(
    body: SuggestionDecision,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    """Apply proposals. This is the only path by which a model's answer
    becomes a value on a record."""
    applied, skipped = 0, []
    for suggestion_id in body.ids:
        row = db.get(AISuggestion, suggestion_id)
        if row is None or row.workspace_id != workspace_id or row.status != "proposed":
            skipped.append(suggestion_id)
            continue
        document = db.get(Document, row.target_uid)
        if document is None or document.workspace_id != workspace_id:
            skipped.append(suggestion_id)
            continue
        if row.field != "document_type_uid":
            skipped.append(suggestion_id)
            continue
        document.document_type_uid = row.suggested_value
        row.status = "accepted"
        row.decided_at = datetime.now(timezone.utc)
        applied += 1
    db.commit()
    return SuggestionDecisionResult(applied=applied, skipped=skipped)


@router.post("/suggestions/reject", response_model=SuggestionDecisionResult)
def reject_suggestions(
    body: SuggestionDecision,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    rejected, skipped = 0, []
    for suggestion_id in body.ids:
        row = db.get(AISuggestion, suggestion_id)
        if row is None or row.workspace_id != workspace_id or row.status != "proposed":
            skipped.append(suggestion_id)
            continue
        row.status = "rejected"
        row.decided_at = datetime.now(timezone.utc)
        rejected += 1
    db.commit()
    return SuggestionDecisionResult(rejected=rejected, skipped=skipped)


@router.post("/identify-object", response_model=PhotoIdentification)
async def identify_object(
    file: UploadFile = File(description="A photograph of the equipment"),
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    """What is in this photograph, as a draft for the new-object form.

    Proposes; does not create. The object types offered are this
    workspace's own, and any key read off a label is checked against the
    inventory rather than believed.
    """
    config = _usable_config(db, workspace_id)
    if not config.vision_model:
        raise HTTPException(
            status_code=409,
            detail="No vision model is configured for this workspace's AI endpoint.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="The photograph was empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That photograph is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )

    try:
        return identify(
            db, workspace_id, endpoint_for(config), content,
            file.content_type or "image/jpeg",
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/draft-document", response_model=DraftDocumentOut)
def draft_a_document(
    body: DraftDocumentIn,
    workspace_id: str = Depends(require_permission("create", resource="documents")),
    db: Session = Depends(get_db),
):
    """A first draft for the editor. Saves nothing."""
    config = _usable_config(db, workspace_id)
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="Give the document a title first.")
    try:
        markdown = draft_document(
            db, endpoint_for(config), body.title.strip(),
            body.document_type_uid, body.notes,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return DraftDocumentOut(
        body_markdown=markdown,
        mentioned_objects=objects_mentioned(db, workspace_id, body.title, markdown),
    )


@router.post("/review-document", response_model=ReviewDocumentOut)
def review_a_document(
    body: ReviewDocumentIn,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    db: Session = Depends(get_db),
):
    """Remarks about a draft, and the objects it names. Changes nothing."""
    config = _usable_config(db, workspace_id)
    if not body.body_markdown.strip():
        raise HTTPException(status_code=422, detail="There is nothing written yet to review.")
    try:
        findings = review_document(
            db, endpoint_for(config), body.title, body.document_type_uid, body.body_markdown
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ReviewDocumentOut(
        findings=findings,
        mentioned_objects=objects_mentioned(
            db, workspace_id, body.title, body.body_markdown
        ),
    )


@router.post("/draft-ticket", response_model=DraftTicketOut)
def draft_a_ticket(
    body: DraftTicketIn,
    workspace_id: str = Depends(require_permission("create", resource="tickets")),
    db: Session = Depends(get_db),
):
    """The structured fields a fault report implies, plus the objects it
    names. Fills a form; creates nothing."""
    config = _usable_config(db, workspace_id)
    if not body.title.strip() and not body.description.strip():
        raise HTTPException(status_code=422, detail="Write the report first.")
    try:
        fields = draft_ticket_fields(endpoint_for(config), body.title, body.description)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return DraftTicketOut(
        **fields,
        mentioned_objects=objects_mentioned(db, workspace_id, body.title, body.description),
    )


@router.post("/ask", response_model=AskOut)
def ask_the_knowledge(
    body: AskIn,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """A question answered from this workspace's records, showing its working.

    Read-only, and deliberately so: the tools behind it only retrieve. It
    needs no more permission than reading the same records by hand would.
    """
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Ask something.")
    config = _usable_config(db, workspace_id)
    try:
        return AskOut(**run_ask(db, workspace_id, endpoint_for(config), question))
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
