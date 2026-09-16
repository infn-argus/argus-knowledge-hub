from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import WorkspaceScopedMixin, utcnow


class TransferJob(Base, WorkspaceScopedMixin):
    """A background copy/move of types and objects from this job's
    workspace_id (the source) into target_workspace_id."""

    __tablename__ = "transfer_jobs"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    target_workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String)  # "copy" | "move"
    status: Mapped[str] = mapped_column(String, default="pending")
    progress: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Non-fatal notices about what was left behind — a relation to an object
    # outside the transfer, a link that couldn't be carried over — the
    # transfer still proceeds; these are surfaced for review afterward.
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
