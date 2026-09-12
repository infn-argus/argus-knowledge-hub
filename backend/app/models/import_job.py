from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import WorkspaceScopedMixin, utcnow


class ImportJob(Base, WorkspaceScopedMixin):
    __tablename__ = "import_jobs"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String)  # "jira" | "git"
    status: Mapped[str] = mapped_column(String, default="pending")
    progress: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Non-fatal per-object schema-constraint violations (unique/cardinality/
    # regex) found while importing — the import still proceeds; these are
    # just surfaced for review afterward.
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
