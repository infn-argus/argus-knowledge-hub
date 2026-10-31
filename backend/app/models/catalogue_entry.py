"""Which ARGUS record each catalogue entry is, and which collection releases a workspace has installed
(docs/catalogue-collections.md §2-§3).

`catalogue_entries` is the link from a catalogue id (`moxa/nport-5450`) to a record. Both sides are unique in
the database (the id within its catalogue workspace), so no path that writes them — an install, an adoption, a second install racing the first — can
give one id two records, or one record two ids: the second writer fails and its transaction rolls back.
"""
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class CatalogueEntry(Base):
    __tablename__ = "catalogue_entries"
    # One record per id in the catalogue workspace, and one id per record.
    __table_args__ = (UniqueConstraint("workspace_id", "catalogue_id", name="uq_catalogue_entries_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalogue_id: Mapped[str] = mapped_column(String)
    record_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), unique=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String)                       # vendor | model
    # The release that last stated it: which collection holds it now, at which version and checksum.
    collection_id: Mapped[str] = mapped_column(String, index=True)
    collection_version: Mapped[str] = mapped_column(String)
    collection_checksum: Mapped[str] = mapped_column(String)
    # What that release stated, field by field, as written on the record ({"name": …, "model_code": …}).
    stated: Mapped[dict] = mapped_column(JSONB, default=dict)
    # The fields a release may change on this record. The others are the workspace's (local overrides).
    managed_fields: Mapped[list] = mapped_column(JSONB, default=list)
    # Local values proposed back to Git: {field: {value, by, at, reason}}. Closed when a release carries them.
    corrections: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Release values not applied because the field is local or was edited here: {field: {release, record,
    # version}}. The review queue's items; the record kept its value.
    conflicts: Mapped[dict] = mapped_column(JSONB, default=dict)
    # active | retired | transferring
    status: Mapped[str] = mapped_column(String, default="active")
    retired: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Set for a record that existed before its entry and was adopted.
    adopted_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    adopted_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CatalogueInstallation(Base):
    """One release of one collection, installed in a workspace: what it did, by whom. The latest row per
    collection is the version the workspace has."""
    __tablename__ = "catalogue_installations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[str] = mapped_column(String, index=True)
    from_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    version: Mapped[str] = mapped_column(String)
    checksum: Mapped[str] = mapped_column(String)
    # {"add": n, "change": n, …} and the items that need a person (conflicts, flagged retirements)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    # the packages whose workspaces its models are offered to; null (installed before C4): every workspace
    domains: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    installed_by: Mapped[str] = mapped_column(String)
    installed_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
