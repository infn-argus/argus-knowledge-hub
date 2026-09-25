"""Jira retirement (asset-model-revision §19 item 14, §17 T5).

Jira is retired once, for the whole instance, when every condition below
holds. What ARGUS can observe it checks itself: the domains' stages and
signed exits, the retention decision (U1), a recent signed access review
for every workspace with a domain, the audit chain, the rehearsal of every
workflow of a ticket domain, a recent restore rehearsal, a recent run of
the performance probe meeting every target, and the Jira host redirect.
What it cannot observe, people attest when they sign.

Signing records one decision and moves every domain from T4 to T5. A
domain reaches T5 in no other way.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.models.access_review import AccessReview
from app.models.ledger import Decision, JobRun, LedgerDomain
from app.services import legacy_hosts

INSTANCE = "_instance"          # the scope of instance-wide decisions and job runs
REVIEW_MAX_AGE = timedelta(days=365)
REHEARSAL_MAX_AGE = timedelta(days=92)   # quarterly (§19 item 10)

ATTESTATIONS = {
    "dr_drill": "A disaster-recovery drill has been held (§19 item 10)",
    "targets_signed_off": "The domain owners signed off the performance and recovery targets (U10)",
    "owners_accepted": "The domain owners accept items 1–13 of §19 as met for their domains",
}


class RetirementError(ValueError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def _latest(db: Session, kind: str) -> Optional[Decision]:
    return db.scalar(select(Decision).where(Decision.workspace_id == INSTANCE, Decision.kind == kind)
                     .order_by(Decision.seq.desc()).limit(1))


def record_job(db: Session, stage: str, report: dict, ok: bool) -> JobRun:
    """Keep an operations run (restore rehearsal, probe) as evidence."""
    run = JobRun(stage=stage, stage_version=f"{stage}/1", scope=INSTANCE, status="ran" if ok else "failed",
                 counts=report, at=now())
    db.add(run)
    db.flush()
    return run


def _recent_job(db: Session, stage: str) -> Optional[JobRun]:
    return db.scalar(select(JobRun).where(JobRun.stage == stage, JobRun.scope == INSTANCE)
                     .order_by(JobRun.id.desc()).limit(1))


def record_retention(db: Session, actor: str, *, reference: str, jira_archive_until: date,
                     exports_until: Optional[date], audit_until: Optional[date], note: Optional[str]) -> Decision:
    """U1: how long the Jira archive, the immutable exports and the audit data
    are kept, and the records-policy reference that sets it."""
    if not reference.strip():
        raise RetirementError("name the records policy or legal basis the retention comes from")
    value = {"reference": reference, "jira_archive_until": jira_archive_until.isoformat(),
             "exports_until": exports_until.isoformat() if exports_until else None,
             "audit_until": audit_until.isoformat() if audit_until else None, "note": note}
    previous = _latest(db, "retention_policy")
    return engine._record_decision(db, "retention_policy", actor, INSTANCE, value=value,
                                   supersedes=[previous.decision_id] if previous else [])


def _domains(db: Session, scope: Optional[list[str]]) -> list[LedgerDomain]:
    q = select(LedgerDomain).order_by(LedgerDomain.id)
    if scope is not None:           # a subset, for rehearsing the retirement of some domains
        q = q.where(LedgerDomain.id.in_(scope))
    return list(db.scalars(q))


def conditions(db: Session, attestations: Optional[dict] = None, scope: Optional[list[str]] = None) -> list[dict]:
    from app.ledger import audit
    from app.models.workflow import Workflow
    from app.services import workflows
    attestations = attestations or {}
    domains = _domains(db, scope)
    out: list[dict] = []

    behind = [d.id for d in domains if d.stage not in ("T4", "T5") or d.exited_at is None]
    out.append({"id": "domains", "item": "17", "text": "Every domain is past its exit and archived (T4)",
                "ok": bool(domains) and not behind, "detail": {"domains": len(domains), "behind": behind}})

    unverified = []
    for d in domains:
        exit_ = db.scalar(select(Decision).where(Decision.decision_id == d.exit_decision_id)) \
            if d.exit_decision_id else None
        if not ((exit_.value or {}).get("attestations", {}).get("export_verified") if exit_ else False):
            unverified.append(d.id)
    out.append({"id": "exports", "item": "9", "text": "Every domain's immutable export was verified at its exit",
                "ok": bool(domains) and not unverified, "detail": {"unverified": unverified}})

    retention = _latest(db, "retention_policy")
    out.append({"id": "retention", "item": "U1", "text": "The retention of the archive, exports and audit data is decided",
                "ok": retention is not None, "detail": retention.value if retention else None})

    stale = []
    for ws in sorted({d.workspace_id for d in domains}):
        review = db.scalar(select(AccessReview).where(AccessReview.workspace_id == ws,
                                                      AccessReview.completed_at.isnot(None))
                           .order_by(AccessReview.completed_at.desc()).limit(1))
        if review is None or now() - review.completed_at > REVIEW_MAX_AGE:
            stale.append(ws)
    out.append({"id": "access_review", "item": "1",
                "text": "Every workspace with a domain has an access review signed in the last year",
                "ok": bool(domains) and not stale, "detail": {"missing": stale}})

    chain = audit.verify(db)
    out.append({"id": "audit_chain", "item": "2", "text": "The audit chain verifies from its first sealed day",
                "ok": bool(chain["ok"] and chain.get("days")), "detail": chain})

    failing = []
    for ws in sorted({d.workspace_id for d in domains if d.resource == "tickets"}):
        # The workflows that came from Jira; one designed in ARGUS has no history to replay.
        for wf in db.scalars(select(Workflow).where(Workflow.workspace_id == ws, Workflow.source.isnot(None))):
            if not workflows.rehearse(db, wf, ws)["ok"]:
                failing.append(wf.uid)
    out.append({"id": "workflows", "item": "3", "text": "Every Jira workflow of a ticket domain passes its rehearsal",
                "ok": not failing, "detail": {"failing": failing}})

    for stage, item, text in (("restore-rehearsal", "10", "A restore was rehearsed in the last quarter and checked out"),
                              ("probe", "13", "The performance probe met every target in the last quarter")):
        run = _recent_job(db, stage)
        fresh = run is not None and now() - run.at <= REHEARSAL_MAX_AGE
        out.append({"id": stage, "item": item, "text": text, "ok": fresh and run.status == "ran",
                    "detail": {"at": run.at.isoformat() if run else None, "status": run.status if run else None}})

    hosts = sorted(legacy_hosts.legacy_hosts())
    out.append({"id": "redirect", "item": "11", "text": "The Jira host redirects to ARGUS",
                "ok": bool(hosts and legacy_hosts.web_url()),
                "detail": {"hosts": hosts, "web_url": legacy_hosts.web_url() or None}})

    for key, text in ATTESTATIONS.items():
        out.append({"id": key, "item": "attested", "text": text, "ok": bool(attestations.get(key)), "attested": True})
    return out


def status(db: Session) -> dict:
    signed = _latest(db, "retire_jira")
    return {"retired": signed is not None,
            "retired_at": signed.at if signed else None, "signed_by": signed.actor if signed else None,
            "conditions": conditions(db)}


def sign(db: Session, actor: str, attestations: dict, reason: Optional[str] = None,
         scope: Optional[list[str]] = None) -> Decision:
    if _latest(db, "retire_jira") is not None:
        raise RetirementError("Jira is already retired")
    report = conditions(db, attestations, scope)
    unmet = [c for c in report if not c["ok"]]
    if unmet:
        raise RetirementError("retirement conditions not met: " + "; ".join(c["text"] for c in unmet))
    decision = engine._record_decision(db, "retire_jira", actor, INSTANCE, reason=reason,
                                       value={"attestations": attestations,
                                              "conditions": [{"id": c["id"], "ok": c["ok"]} for c in report]})
    for d in [d for d in _domains(db, scope) if d.stage == "T4"]:
        engine._record_decision(db, "advance_domain", actor, d.workspace_id, batch_id=decision.batch_id,
                                target={"domain": d.id, "from": "T4", "to": "T5"})
        d.stage = "T5"
    db.flush()
    return decision
