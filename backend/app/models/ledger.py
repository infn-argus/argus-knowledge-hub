"""The fact ledger (docs/asset-model-revision.md §7).

Two kinds of table live here, and the difference matters:

* **audit** tables are append-only. Nothing updates or deletes a row in
  them: `LedgerStream` (the vocabulary of sources), `SourceRevision`,
  `Claim`, `ClaimEvent`, `RevisionEvent`, `Decision`, `StatusEvent`,
  `IdentityEvent`, `ConflictEvent`, `RecordEvent`, `LedgerPolicy`, `JobRun`.
* **projection** tables are current state computed from the audit tables,
  and can be dropped and rebuilt at any time: `StreamHead`,
  `IdentityBinding`, `FactState`, `Conflict`.

Projected values also land on the ordinary records (`assets.attributes`,
`assets.record_status`, `relations` rows with `derivation` set), which is
what the rest of the application reads.
"""
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


# --------------------------------------------------------------------------- audit

class LedgerStream(Base):
    """A source instance read repeatedly. Registering one changes the policy
    vocabulary, so the active policy must be validated again (§7.7)."""
    __tablename__ = "ledger_streams"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String)            # epik8s | insight | person | resolver | pbs …
    facility: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    may_create: Mapped[list] = mapped_column(JSONB, default=list)  # record types this stream may create
    frozen_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceRevision(Base):
    __tablename__ = "ledger_source_revisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(String, ForeignKey("ledger_streams.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)          # order within the stream's head chain
    revision: Mapped[str] = mapped_column(String)         # commit SHA, file hash, export timestamp
    content_hash: Mapped[str] = mapped_column(String, index=True)
    parser_version: Mapped[str] = mapped_column(String)
    observed_at: Mapped[object] = mapped_column(DateTime(timezone=True))   # record time
    retrieved_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    parent_revision_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ordering: Mapped[str] = mapped_column(String, default="head")          # head | historical
    parse_skipped: Mapped[bool] = mapped_column(Boolean, default=False)


class Claim(Base):
    """One stream's statement of one fact value. Content-addressed, written once."""
    __tablename__ = "ledger_claims"

    claim_id: Mapped[str] = mapped_column(String, primary_key=True)
    stream_id: Mapped[str] = mapped_column(String, index=True)
    source_ref: Mapped[str] = mapped_column(String, index=True)
    predicate: Mapped[str] = mapped_column(String)
    member: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    polarity: Mapped[str] = mapped_column(String, default="present")
    value: Mapped[Optional[object]] = mapped_column(JSONB, nullable=True)
    method: Mapped[str] = mapped_column(String)           # stated | resolved | inferred | manual
    rule_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    derived_from: Mapped[list] = mapped_column(JSONB, default=list)


class ClaimEvent(Base):
    __tablename__ = "ledger_claim_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String, index=True)
    stream_id: Mapped[str] = mapped_column(String, index=True)
    revision_id: Mapped[str] = mapped_column(String, index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String)             # appeared | disappeared | evidence_changed
    impl_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class RevisionEvent(Base):
    __tablename__ = "ledger_revision_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    revision_id: Mapped[str] = mapped_column(String, index=True)
    stream_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)   # parsed | held | published | rejected | superseded | rewound_to
    cause: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(Base):
    """A judgement by a person or a declared policy. Never edited: a
    correction is a new decision that names the old one."""
    __tablename__ = "ledger_decisions"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    batch_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    subject_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    predicate: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    member: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    value: Mapped[Optional[object]] = mapped_column(JSONB, nullable=True)
    target: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    supersedes: Mapped[list] = mapped_column(JSONB, default=list)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effective_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class StatusEvent(Base):
    __tablename__ = "ledger_status_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject_uid: Mapped[str] = mapped_column(String, index=True)
    predicate: Mapped[str] = mapped_column(String)
    member: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    contributor: Mapped[str] = mapped_column(String)       # claim:<id> | decision:<id>
    from_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    to_status: Mapped[str] = mapped_column(String)
    cause: Mapped[str] = mapped_column(String)
    projector_version: Mapped[str] = mapped_column(String)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdentityEvent(Base):
    __tablename__ = "ledger_identity_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_ref: Mapped[str] = mapped_column(String, index=True)
    uid: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)   # bound | unbound | rebound
    cause: Mapped[str] = mapped_column(String)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecordEvent(Base):
    __tablename__ = "ledger_record_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)   # created | status
    before: Mapped[Optional[object]] = mapped_column(JSONB, nullable=True)
    after: Mapped[Optional[object]] = mapped_column(JSONB, nullable=True)
    cause: Mapped[str] = mapped_column(String)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConflictEvent(Base):
    __tablename__ = "ledger_conflict_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conflict_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)   # opened | resolved
    conflict_type: Mapped[str] = mapped_column(String)
    subject_uid: Mapped[str] = mapped_column(String, index=True)
    predicate: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    member: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cause: Mapped[str] = mapped_column(String)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerPolicy(Base):
    """An activated authority policy with the vocabulary it was validated against."""
    __tablename__ = "ledger_policies"

    version: Mapped[str] = mapped_column(String, primary_key=True)
    body: Mapped[dict] = mapped_column(JSONB)
    vocabulary: Mapped[dict] = mapped_column(JSONB)   # {"streams": [...], "rules": [...]}
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    activated_by: Mapped[str] = mapped_column(String)
    activated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    __tablename__ = "ledger_job_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage: Mapped[str] = mapped_column(String, index=True)
    stage_version: Mapped[str] = mapped_column(String)
    scope: Mapped[str] = mapped_column(String, index=True)
    input_digest: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)     # ran | skipped | failed
    counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------- projections

class StreamHead(Base):
    __tablename__ = "ledger_stream_heads"

    stream_id: Mapped[str] = mapped_column(String, primary_key=True)
    parsed_head: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parsed_number: Mapped[int] = mapped_column(Integer, default=0)
    published_head: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    published_number: Mapped[int] = mapped_column(Integer, default=0)


class IdentityBinding(Base):
    __tablename__ = "ledger_identity_bindings"

    source_ref: Mapped[str] = mapped_column(String, primary_key=True)
    uid: Mapped[str] = mapped_column(String, index=True)


class FactState(Base):
    __tablename__ = "ledger_fact_state"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject_uid: Mapped[str] = mapped_column(String, index=True)
    predicate: Mapped[str] = mapped_column(String)
    member: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    contributor: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    rank: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    effective: Mapped[bool] = mapped_column(Boolean, default=False)


class Conflict(Base):
    __tablename__ = "ledger_conflicts"

    conflict_id: Mapped[str] = mapped_column(String, primary_key=True)
    conflict_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)       # blocking | non-blocking
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    subject_uid: Mapped[str] = mapped_column(String, index=True)
    predicate: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    member: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    opened_seq: Mapped[int] = mapped_column(BigInteger)
