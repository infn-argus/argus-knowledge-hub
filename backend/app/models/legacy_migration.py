"""Plans for converting ARGUS's own legacy records (asset-model-revision §12)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LegacyMigrationPlan(Base):
    __tablename__ = "legacy_migration_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    # Where Equipment that matches no inventory record is created.
    inventory_workspace_id: Mapped[str] = mapped_column(String)
    # planned | applied | verified | needs_attention | rolled_back | finalized
    status: Mapped[str] = mapped_column(String, default="planned")
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    report_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invariants: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class LegacyMigrationItem(Base):
    __tablename__ = "legacy_migration_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String, ForeignKey("legacy_migration_plans.id", ondelete="CASCADE"),
                                         index=True)
    legacy_uid: Mapped[str] = mapped_column(String, index=True)
    legacy_key: Mapped[str] = mapped_column(String)
    legacy_type: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)          # M-BLOCK | M-FUNC | M-POS | M-PHYS | M-MIXED | M-RETIRE
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    override: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pre_image: Mapped[dict] = mapped_column(JSONB, default=dict)
    pre_image_hash: Mapped[str] = mapped_column(String)
    # planned | applied | failed | stale | rolled_back
    status: Mapped[str] = mapped_column(String, default="planned")
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    applied: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GoldenIncident(Base):
    """A past incident with the causes the teams know were behind it
    (§12.6 I-MIG-7). Symptoms and causes are held by uid, so they survive
    re-keying; the root-cause walk must keep finding the causes, or more
    precisely resolved ones, across a migration."""
    __tablename__ = "golden_incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String)
    symptoms: Mapped[list] = mapped_column(JSONB, default=list)
    symptom_kind: Mapped[dict] = mapped_column(JSONB, default=dict)
    healthy: Mapped[list] = mapped_column(JSONB, default=list)
    expected_causes: Mapped[list] = mapped_column(JSONB, default=list)
    ticket_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
