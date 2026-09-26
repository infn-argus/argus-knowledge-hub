"""The audit trail of AI-assisted entry (asset-model-revision §23.8).

One `IntakeRun` per call to a model: who asked, which model and prompt,
what went in (as hashes and references, after redaction), what came out
after validation, and how it ended. One `IntakeOutcome` when the person
saves: for each suggested field, whether they kept it, corrected it or
left it out. Both are append-only; neither holds a transcript or the
model's reasoning.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IntakeRun(Base):
    __tablename__ = "intake_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    requested_by: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)                 # asset | ticket | document
    operation: Mapped[str] = mapped_column(String)            # e.g. asset.describe
    rule_id: Mapped[str] = mapped_column(String)              # semantic rule, e.g. ai.asset.describe/1
    provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # the endpoint's host
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String)
    profile_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # the activated model profile, if any
    input_refs: Mapped[list] = mapped_column(JSONB, default=list)
    input_hashes: Mapped[list] = mapped_column(JSONB, default=list)
    redactions: Mapped[dict] = mapped_column(JSONB, default=dict)
    output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    validations: Mapped[list] = mapped_column(JSONB, default=list)
    # proposed | draft_only | failed | refused
    outcome: Mapped[str] = mapped_column(String)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntakeOutcome(Base):
    __tablename__ = "intake_outcomes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    record_kind: Mapped[str] = mapped_column(String)
    record_uid: Mapped[str] = mapped_column(String, index=True)
    # field -> {"proposed": ..., "final": ..., "verdict": kept | corrected | left_out}
    fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    decided_by: Mapped[str] = mapped_column(String)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntakeProfile(Base):
    """One operation bound to a model and a prompt version (§23.8). A
    candidate is evaluated on the golden dataset; it is used only once an
    `activate_ai_profile` decision, referencing that evaluation, makes it
    active (§23.12)."""
    __tablename__ = "intake_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)                 # asset | ticket | document
    model: Mapped[str] = mapped_column(String)
    vision_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="candidate")   # candidate | active | retired
    evaluation: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    exception_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
