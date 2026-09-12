from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin, utcnow

# Draft -> InReview -> Approved -> Published -> Superseded | Retired.
# Published revisions are immutable — no API path edits one; a change means
# a new revision starting again at Draft. See SPEC-DOC-0001 §5.
DOCUMENT_STATES = ("draft", "in_review", "approved", "published", "superseded", "retired")


class Document(Base, WorkspaceScopedMixin, TimestampMixin):
    """The stable, logical identity of a document. Never holds the body
    itself — that lives on the current DocumentRevision."""

    __tablename__ = "documents"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    document_type_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("schemas.uid", ondelete="CASCADE"), nullable=True, index=True
    )
    owner_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )
    responsible_service_asset_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("assets.uid", ondelete="SET NULL"), nullable=True
    )
    # ufficiale | informativo | bozza_interna
    authority_level: Mapped[str] = mapped_column(String, default="informativo")
    # pubblico | interno | riservato
    confidentiality: Mapped[str] = mapped_column(String, default="interno")
    # manual | jira | git | confluence
    source: Mapped[str] = mapped_column(String, default="manual")
    current_revision_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("document_revisions.uid", ondelete="SET NULL"), nullable=True
    )


class DocumentRevision(Base, TimestampMixin):
    __tablename__ = "document_revisions"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    document_uid: Mapped[str] = mapped_column(
        String, ForeignKey("documents.uid", ondelete="CASCADE"), index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String, default="draft")
    body_markdown: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    steps: Mapped[list] = mapped_column(JSONB, default=list)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_review_due: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    authored_by: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )
    approved_by: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    superseded_by_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("document_revisions.uid"), nullable=True
    )


class DocumentRelation(Base, WorkspaceScopedMixin):
    """Polymorphic: to_type is one of asset | schema | document | issue. No
    FK on to_uid since it spans multiple tables — validated at the API layer."""

    __tablename__ = "document_relations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_document_uid: Mapped[str] = mapped_column(
        String, ForeignKey("documents.uid", ondelete="CASCADE"), index=True
    )
    to_type: Mapped[str] = mapped_column(String)
    to_uid: Mapped[str] = mapped_column(String, index=True)
    relation_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
