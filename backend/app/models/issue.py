from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin


class Issue(Base, WorkspaceScopedMixin, TimestampMixin):
    __tablename__ = "issues"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    # Deleting the linked asset just detaches the ticket from it (SET NULL) —
    # the ticket itself is independent and shouldn't be destroyed by that.
    asset_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("assets.uid", ondelete="SET NULL"), nullable=True, index=True
    )
    # Optional ticket type (a Schema with applies_to="tickets") giving this
    # issue configurable, searchable attributes — same mechanism as Asset
    # types, just scoped to tickets instead of objects. Deleting the type
    # deletes its tickets too (CASCADE), same as it does for object types.
    schema_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("schemas.uid", ondelete="CASCADE"), nullable=True, index=True
    )
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # "new" | "in_progress" | "pending" | "resolved" | "closed" — see the
    # workspace's ticket-scoped "status" Global Value for the responsible
    # party + meaning behind each one.
    state: Mapped[str] = mapped_column(String, default="new")
    priority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    labels: Mapped[list] = mapped_column(JSONB, default=list)
    due_date: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)


class IssueHistory(Base):
    """What happened to a ticket and when.

    Recorded for changes made here, and filled from Jira's changelog on
    import, so a ticket's past doesn't stop at the moment it was imported.
    """

    __tablename__ = "issue_history"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    issue_uid: Mapped[str] = mapped_column(
        String, ForeignKey("issues.uid", ondelete="CASCADE"), index=True
    )
    # "created" | "updated" | "imported" — coarse on purpose; the detail is
    # in field/from/to.
    type: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String)
    field: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    from_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True))
    # Jira's changelog item id, so a re-import doesn't duplicate entries.
    backend_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)


class IssueComment(Base, TimestampMixin):
    __tablename__ = "issue_comments"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    issue_uid: Mapped[str] = mapped_column(
        String, ForeignKey("issues.uid", ondelete="CASCADE"), index=True
    )
    author: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
