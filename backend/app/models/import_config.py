from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin


class ImportConfig(Base, WorkspaceScopedMixin, TimestampMixin):
    """A saved, named import setup — parameters plus a merge strategy — that
    can be re-run with one click instead of re-entering everything."""

    __tablename__ = "import_configs"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)  # "jira" | "git"
    merge_strategy: Mapped[str] = mapped_column(String, default="override")
    # Non-secret parameters (base_url/jira_schema_id, or provider/repo_url/branch).
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    # The source PAT, Fernet-encrypted — see app/services/crypto.py. Never
    # returned to the client once set.
    encrypted_secret: Mapped[str] = mapped_column(String)
    last_run_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_import_job_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
