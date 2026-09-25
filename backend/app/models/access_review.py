from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class AccessReview(Base):
    """A signed snapshot of who may do what in a workspace (§19 item 1):
    every user, group and token, their permissions and restricted classes,
    and what changed since the last review. Owners sign it; it is complete
    when `required_signers` distinct people have."""
    __tablename__ = "access_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String)
    changes: Mapped[dict] = mapped_column(JSONB, default=dict)
    signatures: Mapped[list] = mapped_column(JSONB, default=list)
    required_signers: Mapped[int] = mapped_column(Integer, default=2)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
