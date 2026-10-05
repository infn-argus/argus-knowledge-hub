from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
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
    # Separate from `model` because they are usually different models: the
    # chat model INFN serves by default answers "not a multimodal model"
    # when shown a picture.
    vision_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Speech, for the voice assistant the beamline dashboards already carry.
    # Separate names again: an endpoint serving a chat model and a Whisper
    # transcriber lists them as two different models, and picking the wrong
    # one fails at the microphone rather than at configuration time.
    asr_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Orders the passages written-knowledge search found by how well they answer the question (a cross-encoder,
    # served at the endpoint's /rerank). Optional: without it the search's own ranking stands.
    rerank_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tts_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Fernet-encrypted, never returned to the client — the same handling the
    # import configurations give a source PAT. Nullable: some endpoints on
    # the internal network take no key at all.
    encrypted_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Whether documents marked "riservato" may be sent. Off unless somebody
    # decides otherwise: it is a property of where the text is going, so it
    # belongs beside the endpoint.
    allow_confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    # How long a reply may be, for every AI call of this workspace. Empty: no limit, which is what a
    # reasoning model needs (it thinks before answering, and a budget sized for the answer is spent
    # thinking). A number caps every reply, for a gateway that bills or throttles by token.
    max_output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_check_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    last_check_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
