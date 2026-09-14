from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class LLMConfig(Base, TimestampMixin):
    """Where this workspace's AI features send their requests.

    One per workspace rather than one per installation: the beamlines
    already point at different gateways, so a single endpoint for everything
    would be wrong for somebody.

    Nothing is enabled until it has been checked. An endpoint that was
    reachable in March and has since had its key rotated must show as
    unavailable, not as a batch of silently failed suggestions — so the
    result of the last check is stored, not just the settings.
    """

    __tablename__ = "llm_configs"

    workspace_id: Mapped[str] = mapped_column(String, primary_key=True)
    base_url: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    # Classification and linking work on embeddings rather than a chat call
    # per record; optional, since not every endpoint serves one.
    embedding_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Fernet-encrypted, never returned to the client — the same handling the
    # import configurations give a source PAT. Nullable: some endpoints on
    # the internal network take no key at all.
    encrypted_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Whether documents marked "riservato" may be sent. Off unless somebody
    # decides otherwise: it is a property of where the text is going, so it
    # belongs beside the endpoint.
    allow_confidential: Mapped[bool] = mapped_column(Boolean, default=False)

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_check_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_check_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
