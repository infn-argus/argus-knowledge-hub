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

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String
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
    impl_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # code that parsed it (§7.9)
    # The bytes, kept so a ruleset change can re-run inference over what the
    # source last said without asking the source again.
    content: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)


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


class LedgerRuleset(Base):
    """Which semantic rule id runs for each rule family, and with which
    implementation (§7.9). The latest row for a workspace applies; a row with
    scope "*" applies where a workspace has none."""
    __tablename__ = "ledger_rulesets"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String, index=True)
    rules: Mapped[dict] = mapped_column(JSONB)          # family -> rule id
    impl: Mapped[dict] = mapped_column(JSONB, default=dict)   # rule id -> implementation version
    activated_by: Mapped[str] = mapped_column(String)
    activated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class MigrationMap(Base):
    """Permanent: every legacy uid resolves to all the records it became (§12.4)."""
    __tablename__ = "ledger_migration_map"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    legacy_uid: Mapped[str] = mapped_column(String, index=True)
    new_uid: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[str] = mapped_column(String)           # position | equipment | installation
    plan_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class LedgerDomain(Base):
    """A migration domain (§17): one scope moving from Jira or Insight to
    ARGUS, through the stages T0 Prepare … T5 Retire. ARGUS becomes the
    system of record for the scope when its exit is signed."""
    __tablename__ = "ledger_domains"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String)
    resource: Mapped[str] = mapped_column(String, default="objects")   # objects | tickets | documents
    stage: Mapped[str] = mapped_column(String, default="T0")
    stream_ids: Mapped[list] = mapped_column(JSONB, default=list)
    pilot: Mapped[bool] = mapped_column(Boolean, default=False)
    archive_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # the read-only Jira/Insight archive
    watermark: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    manifest_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    frozen_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    exited_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_decision_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReconciliationReport(Base):
    """One comparison of a source export with ARGUS (§17.6). Written once."""
    __tablename__ = "ledger_reconciliation_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain_id: Mapped[str] = mapped_column(String, index=True)
    manifest_hash: Mapped[str] = mapped_column(String)
    passed: Mapped[bool] = mapped_column(Boolean)
    body: Mapped[dict] = mapped_column(JSONB)
    body_hash: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeriveRequest(Base):
    """A derive run a user edit is waiting for (D10): until it is done the
    records of these workspaces show `deriving`."""
    __tablename__ = "ledger_derive_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_ids: Mapped[list] = mapped_column(JSONB)
    cause: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)   # pending | done | failed
    requested_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    done_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- projections

class TicketLink(Base):
    """A ticket's link to a record, with its role (§8.6). Subject links follow
    the ticket; involved links are derived from Installations and incident
    time and recomputed whenever either changes."""
    __tablename__ = "ledger_ticket_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    ticket_uid: Mapped[str] = mapped_column(String, ForeignKey("issues.uid", ondelete="CASCADE"), index=True)
    asset_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String)           # subject | related | involved_equipment | involved_position
    certainty: Mapped[str] = mapped_column(String, default="definite")    # definite | possible
    origin: Mapped[str] = mapped_column(String)         # ticket | derived | migration-split
    derivation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


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
