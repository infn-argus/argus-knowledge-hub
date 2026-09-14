from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import WorkspaceScopedMixin, utcnow


class AISuggestion(Base, WorkspaceScopedMixin):
    """Something a model proposed, which nobody has accepted yet.

    Kept apart from the records it is about, deliberately. A knowledge
    graph whose edges might be a guess is worth less than one with fewer
    edges that are all trustworthy — so a suggestion is never a value until
    a person makes it one, and what it was and who accepted it stays on the
    record afterwards.
    """

    __tablename__ = "ai_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # "document" | "ticket" | "asset"
    target_type: Mapped[str] = mapped_column(String, index=True)
    target_uid: Mapped[str] = mapped_column(String, index=True)
    # Which field this is about, e.g. "document_type_uid".
    field: Mapped[str] = mapped_column(String)
    suggested_value: Mapped[str] = mapped_column(String)
    # What to show a person: the type's name rather than its uid.
    suggested_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # What it was before, so accepting can be undone by reading the record.
    previous_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Provenance. In a system holding controlled documentation, "who said
    # this" is the point.
    model: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # "proposed" | "accepted" | "rejected"
    status: Mapped[str] = mapped_column(String, default="proposed", index=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
