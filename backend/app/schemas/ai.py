from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LLMConfigIn(BaseModel):
    base_url: str
    model: str
    embedding_model: Optional[str] = None
    # Left out on an update, the stored key is kept. Sent empty, it is
    # cleared — for an endpoint that takes none.
    api_key: Optional[str] = None
    enabled: bool = False
    allow_confidential: bool = False


class LLMConfigOut(BaseModel):
    """What the client may see. The key is never among it — only whether
    one is set, which is all a form needs to render honestly."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    workspace_id: str
    base_url: str
    model: str
    embedding_model: Optional[str]
    has_api_key: bool
    enabled: bool
    allow_confidential: bool
    last_checked_at: Optional[datetime]
    last_check_ok: Optional[bool]
    last_check_error: Optional[str]


class LLMCheckResult(BaseModel):
    ok: bool
    error: Optional[str] = None
    models: list[str] = []


class AIStatus(BaseModel):
    """What the application asks before offering an AI action, so a feature
    that cannot work is never presented as if it could."""

    model_config = ConfigDict(protected_namespaces=())

    configured: bool
    enabled: bool
    validated: bool
    model: Optional[str] = None
    has_embeddings: bool = False
    # Why it is unavailable, in words a person can act on.
    reason: Optional[str] = None


class SuggestRequest(BaseModel):
    # Only the ones an import had nothing to go on for, by default.
    only_untyped: bool = True
    limit: int = 25


class SuggestRunResult(BaseModel):
    considered: int
    proposed: int
    unchanged: int
    failed_batches: int


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    target_type: str
    target_uid: str
    field: str
    suggested_value: str
    suggested_label: Optional[str]
    previous_value: Optional[str]
    model: str
    status: str
    created_at: datetime
    # Filled in for display so a list does not need a second round of
    # lookups to be readable.
    target_label: Optional[str] = None
    previous_label: Optional[str] = None


class SuggestionDecision(BaseModel):
    ids: list[int]


class SuggestionDecisionResult(BaseModel):
    applied: int = 0
    rejected: int = 0
    skipped: list[int] = []
