"""Where a workspace's AI features point, and whether they work.

The endpoint is configured here rather than in the deployment because
different workspaces are entitled to different gateways, and because a
key typed into a form and encrypted at rest never has to travel through a
values file or a chat window to get there.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.llm_config import LLMConfig
from app.schemas.ai import AIStatus, LLMCheckResult, LLMConfigIn, LLMConfigOut
from app.services.crypto import decrypt_secret, encrypt_secret
from app.services.llm import Endpoint, check

router = APIRouter(prefix="/v1/ai", tags=["ai"])


def endpoint_for(config: LLMConfig) -> Endpoint:
    return Endpoint(
        base_url=config.base_url,
        model=config.model,
        embedding_model=config.embedding_model,
        api_key=decrypt_secret(config.encrypted_secret) if config.encrypted_secret else None,
    )


def _out(config: LLMConfig) -> LLMConfigOut:
    return LLMConfigOut(
        workspace_id=config.workspace_id,
        base_url=config.base_url,
        model=config.model,
        embedding_model=config.embedding_model,
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
            reason="AI features are switched off for this workspace.",
        )
    if not config.last_check_ok:
        return AIStatus(
            configured=True,
            enabled=True,
            validated=False,
            model=config.model,
            has_embeddings=bool(config.embedding_model),
            reason=config.last_check_error
            or "The AI endpoint has not been checked since it was last changed.",
        )
    return AIStatus(
        configured=True,
        enabled=True,
        validated=True,
        model=config.model,
        has_embeddings=bool(config.embedding_model),
    )
