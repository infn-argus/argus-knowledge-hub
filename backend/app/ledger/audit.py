"""Audit integrity (asset-model-revision §19 item 2).

* **Append-only in the database.** A trigger refuses UPDATE and DELETE on
  every audit table, whatever the application does. The one sanctioned
  purge — deleting a whole workspace — sets `argus.audit_purge` for its
  own transaction.
* **A daily digest chain.** Each day's events are hashed together with the
  previous day's digest. The digests are meant to be copied out of ARGUS
  (the CLI prints them); `verify` recomputes the chain from the events and
  reports the first day that no longer matches.
* **An audit trail per record**: every event that concerns it, in order.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from sqlalchemy import DDL, event, select, text
from sqlalchemy.orm import Session

from app.ledger.engine import canonical, now
from app.models.ledger import (AuditDigest, ClaimEvent, ConflictEvent, Decision, IdentityBinding, IdentityEvent,
                               RecordEvent, RevisionEvent, StatusEvent)

APPEND_ONLY_TABLES = (
    "ledger_claims", "ledger_claim_events", "ledger_source_revisions", "ledger_revision_events",
    "ledger_decisions", "ledger_status_events", "ledger_identity_events", "ledger_record_events",
    "ledger_conflict_events", "ledger_job_runs", "ledger_rulesets", "ledger_migration_map",
    "ledger_reconciliation_reports", "ledger_audit_digests",
)

GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION ledger_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND coalesce(current_setting('argus.audit_purge', true), '') = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'the audit table % is append-only (% refused)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""


def guard_sql(table: str) -> str:
    return (f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}; "
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION ledger_append_only();")


def install_guards(bind) -> None:
    bind.execute(text(GUARD_FUNCTION))
    for table in APPEND_ONLY_TABLES:
        bind.execute(text(guard_sql(table)))


def _attach_ddl() -> None:
    """Databases built with `create_all` (tests, first start) get the guards
    too; alembic installs them for migrated databases."""
    from app.db import Base
    from app.ledger import writer
    writer._attach_ddl()                  # and the ledger-only guard (§13 S5)
    for table in APPEND_ONLY_TABLES:
        t = Base.metadata.tables.get(table)
        if t is not None:
            event.listen(t, "after_create", DDL(GUARD_FUNCTION))
            event.listen(t, "after_create", DDL(guard_sql(table)))


def allow_purge(db: Session) -> None:
    """For the current transaction only: deleting a workspace takes its audit
    history with it. Nothing else may delete audit rows."""
    db.execute(text("SET LOCAL argus.audit_purge = 'on'"))


# --------------------------------------------------------------------------- digests

EVENT_TABLES = (
    ("claim_events", ClaimEvent, ("seq", "claim_id", "stream_id", "revision_id", "kind", "impl_version", "evidence")),
    ("revision_events", RevisionEvent, ("seq", "revision_id", "stream_id", "kind", "cause", "detail")),
    ("decisions", Decision, ("seq", "decision_id", "batch_id", "kind", "actor", "workspace_id", "subject_uid",
                             "predicate", "member", "value", "target", "supersedes", "reason")),
    ("status_events", StatusEvent, ("seq", "subject_uid", "predicate", "member", "contributor", "from_status",
                                    "to_status", "cause")),
    ("identity_events", IdentityEvent, ("seq", "source_ref", "uid", "kind", "cause")),
    ("record_events", RecordEvent, ("seq", "uid", "kind", "before", "after", "cause")),
    ("conflict_events", ConflictEvent, ("seq", "conflict_id", "kind", "conflict_type", "subject_uid", "detail",
                                        "cause")),
)


def _bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def day_digest(db: Session, day: date, prev: Optional[str]) -> tuple[str, dict]:
    start, end = _bounds(day)
    h = hashlib.sha256((prev or "genesis").encode())
    counts = {}
    for name, model, cols in EVENT_TABLES:
        n = 0
        for row in db.scalars(select(model).where(model.at >= start, model.at < end).order_by(model.seq)):
            h.update(canonical([name, [getattr(row, c) for c in cols], row.at.isoformat()]).encode())
            n += 1
        counts[name] = n
    return h.hexdigest(), counts


MAX_GAP_DAYS = 400


def seal_day(db: Session, day: Optional[date] = None) -> AuditDigest:
    """Seal one day (default: yesterday, UTC). Days are sealed in order:
    unsealed days since the last sealed one (up to `MAX_GAP_DAYS`) are
    sealed first, so a daily job that missed a run leaves no gap."""
    day = day or (now().date() - timedelta(days=1))
    existing = db.get(AuditDigest, day)
    if existing is not None:
        return existing
    if db.scalar(select(AuditDigest.day).where(AuditDigest.day > day).limit(1)) is not None:
        raise ValueError(f"a later day than {day} is already sealed; days are sealed in order")
    last = db.scalar(select(AuditDigest).where(AuditDigest.day < day).order_by(AuditDigest.day.desc()).limit(1))
    start = day - timedelta(days=MAX_GAP_DAYS)
    cursor = max(last.day + timedelta(days=1), start) if last else day
    prev = last.digest if last else None
    row = None
    while cursor <= day:
        digest, counts = day_digest(db, cursor, prev)
        row = AuditDigest(day=cursor, prev_digest=prev, digest=digest, counts=counts, sealed_at=now())
        db.add(row)
        prev, cursor = digest, cursor + timedelta(days=1)
    db.flush()
    return row


def verify(db: Session) -> dict:
    """Recompute every sealed day from the events. The first mismatch is where
    the log was altered (or the chain broken)."""
    prev = None
    days = list(db.scalars(select(AuditDigest).order_by(AuditDigest.day)))
    for row in days:
        if row.prev_digest != prev:
            return {"ok": False, "day": row.day.isoformat(), "reason": "the chain link does not match"}
        digest, _counts = day_digest(db, row.day, prev)
        if digest != row.digest:
            return {"ok": False, "day": row.day.isoformat(), "reason": "the events of this day have changed"}
        prev = row.digest
    return {"ok": True, "days": len(days), "head": prev}


# --------------------------------------------------------------------------- per record

def record_trail(db: Session, uid: str, limit: int = 500) -> list[dict]:
    """Everything the ledger recorded about one record, oldest first."""
    refs = [b.source_ref for b in db.scalars(select(IdentityBinding).where(IdentityBinding.uid == uid))]
    out: list[dict] = []
    for e in db.scalars(select(RecordEvent).where(RecordEvent.uid == uid)):
        if e.kind == "merge_moved":
            continue
        out.append({"at": e.at, "type": "record", "kind": e.kind, "before": e.before, "after": e.after,
                    "cause": e.cause})
    for d in db.scalars(select(Decision).where(Decision.subject_uid == uid)):
        out.append({"at": d.at, "type": "decision", "kind": d.kind, "actor": d.actor, "predicate": d.predicate,
                    "value": d.value, "reason": d.reason, "decision_id": d.decision_id})
    for s in db.scalars(select(StatusEvent).where(StatusEvent.subject_uid == uid)):
        out.append({"at": s.at, "type": "fact", "kind": s.to_status, "predicate": s.predicate, "member": s.member,
                    "before": s.from_status, "cause": s.cause, "contributor": s.contributor})
    if refs:
        for i in db.scalars(select(IdentityEvent).where(IdentityEvent.source_ref.in_(refs))):
            out.append({"at": i.at, "type": "identity", "kind": i.kind, "source_ref": i.source_ref, "cause": i.cause})
    for c in db.scalars(select(ConflictEvent).where(ConflictEvent.subject_uid == uid)):
        out.append({"at": c.at, "type": "conflict", "kind": c.kind, "conflict_type": c.conflict_type,
                    "predicate": c.predicate, "cause": c.cause})
    out.sort(key=lambda x: x["at"])
    return out[-limit:]


_attach_ddl()
