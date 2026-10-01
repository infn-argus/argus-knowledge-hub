"""Bringing imported hardware models into a catalogue as Product Models.

A mapping reads records of one workspace (an Insight import, typically its
"… Models" object types) and proposes, row by row, the Product Model and
Vendor each becomes in a catalogue workspace. Nothing is written to the
catalogue until a person accepts rows and applies them; the source is never
changed. A skipped row stays open, and its record can be mapped by a later
mapping.
"""
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class CatalogueMapping(Base):
    __tablename__ = "catalogue_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    target_workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    actor: Mapped[str] = mapped_column(String)
    # catalogue: hardware models into Product Models and Vendors (services/catalogue_mapping.py);
    # records: any records into the target's types, following a plan per source type (services/record_mapping.py).
    kind: Mapped[str] = mapped_column(String, default="catalogue")
    # records only: {source type uid: {"target_type", "fields", "relations", ...}}
    plan: Mapped[dict] = mapped_column(JSONB, default=dict)
    # analysing | ready | failed
    state: Mapped[str] = mapped_column(String, default="analysing")
    use_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    # The source types it was asked for, by uid.
    source_type_uids: Mapped[list] = mapped_column(JSONB, default=list)
    total: Mapped[int] = mapped_column(Integer, default=0)
    analysed: Mapped[int] = mapped_column(Integer, default=0)
    # Which endpoint answered, the intake runs that audit each call, and why the AI was not used when it was not.
    ai: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CatalogueMappingItem(Base):
    """One source record and what it is proposed to become."""

    __tablename__ = "catalogue_mapping_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    mapping_id: Mapped[str] = mapped_column(
        String, ForeignKey("catalogue_mappings.id", ondelete="CASCADE"), index=True)
    source_uid: Mapped[str] = mapped_column(String, index=True)
    source_key: Mapped[str] = mapped_column(String)
    source_name: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    # The source fields the proposal was made from, as read: evidence for the reviewer.
    source: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {"action", "fields": {name: {value, source, confidence, evidence}}, "vendor": {...},
    #  "merge_into": {...} | None, "duplicate_of": item id | None, "warnings": [...]}
    proposal: Mapped[dict] = mapped_column(JSONB, default=dict)
    # proposed | accepted | skipped | applied | undone
    status: Mapped[str] = mapped_column(String, default="proposed", index=True)
    # The Product Model (or Vendor) it became or was merged into, and what applying it created or added.
    result_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_uids: Mapped[list] = mapped_column(JSONB, default=list)
    label_uids: Mapped[list] = mapped_column(JSONB, default=list)
    # What applying copied or linked onto the result, so undo removes exactly that:
    # {"attachments": [uid], "history": [uid], "comments": [uid], "asset_tickets": [uid],
    #  "ticket_links": [id], "avatar": {"asset": uid, "previous": uid | None}}
    carried: Mapped[dict] = mapped_column(JSONB, default=dict)
    decided_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decided_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
