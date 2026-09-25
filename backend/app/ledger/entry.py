"""Cutover entry criteria (asset-model-revision §17.4, §17.2, §18.2).

A domain is frozen for cutover only when these hold. ARGUS checks what it
can see: the stewards, the review queues and their ageing, the length and
the reconciliation record of shadow validation (T2), the legacy migration,
and recent restore and performance evidence. People attest the rest.

The governance group may waive a criterion for a domain with a reason (for
a rehearsal, or a domain decided at the T2 limit, §17.2); the waiver is
written into the freeze decision. Two criteria are never waived: the legacy
migration's blocked items and the blocking queues, which would leave the
cutover with data nobody can resolve afterwards.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.models.ledger import (Conflict, ConflictEvent, Decision, JobRun, LedgerDomain, ReconciliationReport,
                               SourceRevision)

T2_MIN_DAYS = 14
T2_MAX_DAYS = 56                   # 8 weeks: the governance group decides (§17.2)
CLEAN_RUNS = 10
RESTORE_MAX_AGE = timedelta(days=30)
PROBE_MAX_AGE = timedelta(days=92)
NOT_WAIVABLE = {"legacy", "queues_blocking"}

ATTESTATIONS = {
    "readiness": "The domain's §19 readiness items and tests A33–A41 pass for its data",
    "users_trained": "The domain's users are trained",
    "jira_readonly_scheduled": "The Jira administrators approved and scheduled the read-only change",
}

# §18.2, in working days: when an open item is overdue.
DUE_DAYS = {"port_confirmation_required": 5, "port_mapping_unresolved": 5, "port_map_invalid": 5,
            "identity_candidate": 10, "retirement_blocked": 10}
NON_BLOCKING_DUE = 30


def now() -> datetime:
    return datetime.now(timezone.utc)


def working_days(start: datetime, end: datetime) -> int:
    """Monday to Friday between two instants, not counting the first day."""
    a, b = start.date(), end.date()
    if b <= a:
        return 0
    days = (b - a).days
    weeks, rest = divmod(days, 7)
    count = weeks * 5
    for i in range(1, rest + 1):
        if (a + timedelta(days=weeks * 7 + i)).weekday() < 5:
            count += 1
    return count


def _due(c: Conflict) -> int:
    if c.conflict_type == "port_confirmation_required" and (c.detail or {}).get("safety_class", "none") != "none":
        return 0                  # before the equipment returns to operation: never left open at a cutover
    return DUE_DAYS.get(c.conflict_type, NON_BLOCKING_DUE)


def overdue(db: Session, workspace_id: str, at: Optional[datetime] = None) -> list[dict]:
    at = at or now()
    out = []
    # Blocking conflicts are a criterion of their own: none may be open at all.
    for c in db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id,
                                               Conflict.severity != "blocking")):
        opened = db.scalar(select(func.max(ConflictEvent.at)).where(ConflictEvent.conflict_id == c.conflict_id,
                                                                    ConflictEvent.kind == "opened"))
        age = working_days(opened, at) if opened else 0
        if age > _due(c) or _due(c) == 0:
            out.append({"conflict_id": c.conflict_id, "type": c.conflict_type, "age_working_days": age,
                        "due": _due(c)})
    return out


def t2_started(db: Session, d: LedgerDomain) -> Optional[datetime]:
    """When the domain last entered T2 (moving on, or back after an abort)."""
    return db.scalar(select(func.max(Decision.at)).where(
        Decision.workspace_id == d.workspace_id, Decision.kind.in_(("advance_domain", "abort_cutover")),
        Decision.target["domain"].astext == d.id, Decision.target["to"].astext == "T2"))


def clean_runs(db: Session, d: LedgerDomain, since: Optional[datetime]) -> int:
    """Consecutive passing reconciliation runs, newest first, since T2 began."""
    q = select(ReconciliationReport).where(ReconciliationReport.domain_id == d.id)
    if since is not None:
        q = q.where(ReconciliationReport.created_at >= since)
    n = 0
    for r in db.scalars(q.order_by(ReconciliationReport.created_at.desc())):
        if not r.passed:
            break
        n += 1
    return n


def _job(db: Session, stage: str) -> Optional[JobRun]:
    return db.scalar(select(JobRun).where(JobRun.stage == stage, JobRun.status == "ran")
                     .order_by(JobRun.id.desc()).limit(1))


def criteria(db: Session, d: LedgerDomain, attestations: Optional[dict] = None,
             waivers: Optional[dict] = None) -> list[dict]:
    from app.ledger import legacy
    attestations, waivers = attestations or {}, waivers or {}
    out: list[dict] = []

    def add(cid: str, point: str, text: str, ok: bool, detail=None, attested: bool = False):
        waiver = waivers.get(cid) if cid not in NOT_WAIVABLE else None
        out.append({"id": cid, "criterion": point, "text": text, "ok": ok or bool(waiver), "met": ok,
                    "waived": bool(waiver) and not ok, "waiver": waiver if not ok else None,
                    "waivable": cid not in NOT_WAIVABLE, "attested": attested, "detail": detail})

    add("readiness", "1", ATTESTATIONS["readiness"], bool(attestations.get("readiness")), attested=True)
    add("stewards", "2", "A primary steward and a backup are named, and they are different people",
        bool(d.steward and d.backup_steward and d.steward != d.backup_steward),
        {"steward": d.steward, "backup": d.backup_steward})
    blocking = db.scalar(select(func.count()).select_from(Conflict).where(
        Conflict.workspace_id == d.workspace_id, Conflict.severity == "blocking")) or 0
    held = sum(1 for sid in d.stream_ids for r in db.scalars(select(SourceRevision).where(SourceRevision.stream_id == sid))
               if engine.revision_state(db, r.id) == "held")
    add("queues_blocking", "2", "No blocking conflict or held revision is open", blocking == 0 and held == 0,
        {"blocking": blocking, "held": held})
    late = overdue(db, d.workspace_id)
    add("queues_ageing", "2", "The other review queues are within their ageing targets (§18.2)", not late,
        {"overdue": len(late), "examples": late[:5]})

    started = t2_started(db, d)
    days = (now() - started).days if started else 0
    runs = clean_runs(db, d, started)
    add("t2", "3", f"Shadow validation lasted at least {T2_MIN_DAYS // 7} weeks, with {CLEAN_RUNS} consecutive "
                   "clean reconciliation runs",
        d.stage == "T2" and days >= T2_MIN_DAYS and runs >= CLEAN_RUNS,
        {"stage": d.stage, "t2_since": started.isoformat() if started else None, "days": days, "clean_runs": runs,
         "over_limit": days > T2_MAX_DAYS})

    g = legacy.gate(db, d.workspace_id)
    add("legacy", "4", "No legacy record is M-BLOCK, every M-MIXED one is accepted, none is unplanned (§12)",
        g["ok"], {"blocked": len(g["blocked"]), "mixed_open": len(g["mixed_open"]), "unplanned": g["unplanned"]})

    restore = _job(db, "restore-rehearsal")
    add("restore", "5", "A point-in-time restore was rehearsed in the last 30 days",
        restore is not None and now() - restore.at <= RESTORE_MAX_AGE,
        {"at": restore.at.isoformat() if restore else None})
    add("users_trained", "6", ATTESTATIONS["users_trained"], bool(attestations.get("users_trained")), attested=True)
    add("jira_readonly_scheduled", "6", ATTESTATIONS["jira_readonly_scheduled"],
        bool(attestations.get("jira_readonly_scheduled")), attested=True)
    probe = _job(db, "probe")
    add("performance", "7", "The performance probe met every target at production scale (§19 item 13)",
        probe is not None and now() - probe.at <= PROBE_MAX_AGE, {"at": probe.at.isoformat() if probe else None})
    return out


def check(db: Session, d: LedgerDomain, attestations: Optional[dict], waivers: Optional[dict]) -> list[dict]:
    """The criteria, refusing a waiver without a reason or of what cannot be waived."""
    for cid, reason in (waivers or {}).items():
        if cid in NOT_WAIVABLE:
            raise engine.LedgerError(f"{cid} cannot be waived")
        if not str(reason or "").strip():
            raise engine.LedgerError(f"the waiver of {cid} needs a reason")
    return criteria(db, d, attestations, waivers)
