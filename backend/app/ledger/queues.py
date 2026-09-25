"""Review queues, their ageing and escalation (asset-model-revision §18.2).

Every open review item belongs to one queue, which sets three thresholds in
working days: when it is due, when it goes to the domain's backup steward,
and when it goes to the governance group. An item is escalated once per
level; the notification names the queue, the workspace and the age, never
the record, so a restricted record is not disclosed to someone who may not
see it.

    ARGUS_GOVERNANCE=gov-lead@example.org,platform-lead@example.org
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.models.asset import Asset
from app.models.ledger import (ClaimEvent, Conflict, ConflictEvent, FactState, LedgerDomain, LedgerStream,
                               ReviewEscalation, RevisionEvent, SourceRevision)
from app.services.visibility import can_see

# queue: (label, due, to backup, to governance), in working days (§18.2).
QUEUES = {
    "blocking": ("Blocking conflicts and held revisions", 2, 3, 5),
    "port_safety": ("Port confirmations, safety-relevant", 0, 0, 1),
    "port": ("Port confirmations and mappings", 5, 7, 10),
    "identity_candidate": ("Identity candidates (duplicates)", 10, 15, 30),
    "proposal": ("Proposals (inferred facts)", 20, 30, 60),
    "non_blocking": ("Non-blocking conflicts and possible overlaps", 30, 45, 90),
    "retirement_flag": ("Retirement flags", 10, 15, 30),
}
PORT_CONFLICTS = ("port_mapping_unresolved", "port_confirmation_required", "port_map_invalid")
BUCKETS = ((0, 2, "0–2"), (3, 5, "3–5"), (6, 10, "6–10"), (11, 30, "11–30"), (31, 10 ** 6, "31+"))


def now() -> datetime:
    return datetime.now(timezone.utc)


def working_days(start: datetime, end: datetime) -> int:
    """Monday to Friday between two instants, not counting the first day."""
    from datetime import timedelta
    a, b = start.date(), end.date()
    if b <= a:
        return 0
    weeks, rest = divmod((b - a).days, 7)
    return weeks * 5 + sum(1 for i in range(1, rest + 1) if (a + timedelta(days=weeks * 7 + i)).weekday() < 5)


def queue_of(c: Conflict) -> str:
    if c.severity == "blocking":
        return "blocking"
    if c.conflict_type == "port_confirmation_required" and (c.detail or {}).get("safety_class", "none") != "none":
        return "port_safety"
    if c.conflict_type in PORT_CONFLICTS:
        return "port"
    if c.conflict_type == "identity_candidate":
        return "identity_candidate"
    if c.conflict_type == "retirement_blocked":
        return "retirement_flag"
    return "non_blocking"


def _level(queue: str, age: int) -> int:
    """0 on time, 1 due for the backup, 2 due for the governance group."""
    _label, _due, backup, governance = QUEUES[queue]
    if age >= governance:
        return 2
    if age >= backup:
        return 1
    return 0


def _visible(db: Session, uid: Optional[str]) -> bool:
    a = db.get(Asset, uid) if uid else None
    return a is None or can_see(a)


def items(db: Session, workspace_id: str, at: Optional[datetime] = None, visible_only: bool = True) -> list[dict]:
    """Every open review item of a workspace, with its queue and age."""
    at = at or now()
    out = []

    def add(key: str, queue: str, subject: Optional[str], opened: Optional[datetime], kind: str):
        if visible_only and not _visible(db, subject):
            return
        opened = opened or at
        age = working_days(opened, at)
        _label, due, _b, _g = QUEUES[queue]
        out.append({"key": key, "queue": queue, "kind": kind, "subject_uid": subject, "workspace_id": workspace_id,
                    "opened_at": opened, "age": age, "overdue": age > due or due == 0, "level_due": _level(queue, age)})

    for c in db.scalars(select(Conflict).where(Conflict.workspace_id == workspace_id)):
        opened = db.scalar(select(func.max(ConflictEvent.at)).where(ConflictEvent.conflict_id == c.conflict_id,
                                                                    ConflictEvent.kind == "opened"))
        add(f"conflict:{c.conflict_id}", queue_of(c), c.subject_uid, opened, c.conflict_type)

    for s in db.scalars(select(LedgerStream).where(LedgerStream.workspace_id == workspace_id)):
        for r in db.scalars(select(SourceRevision).where(SourceRevision.stream_id == s.id)):
            if engine.revision_state(db, r.id) == "held":
                held = db.scalar(select(func.max(RevisionEvent.at)).where(RevisionEvent.revision_id == r.id,
                                                                         RevisionEvent.kind == "held"))
                add(f"revision:{r.id}", "blocking", None, held, "held_revision")

    uids = select(Asset.uid).where(Asset.workspace_id == workspace_id)
    for f in db.scalars(select(FactState).where(FactState.status == "proposed", FactState.subject_uid.in_(uids),
                                                FactState.contributor.like("claim:%"))):
        claim_id = f.contributor[6:]
        appeared = db.scalar(select(func.max(ClaimEvent.at)).where(ClaimEvent.claim_id == claim_id,
                                                                  ClaimEvent.kind == "appeared"))
        add(f"proposal:{claim_id}:{f.subject_uid}:{f.predicate}", "proposal", f.subject_uid, appeared, "proposal")
    return out


def dashboard(db: Session, workspace_id: str, at: Optional[datetime] = None) -> dict:
    """Each queue's size and age distribution (§18.2), and who it goes to."""
    all_items = items(db, workspace_id, at)
    escalated = {e.item_key: e.level for e in db.scalars(
        select(ReviewEscalation).where(ReviewEscalation.workspace_id == workspace_id))}
    queues = []
    for q, (label, due, backup, governance) in QUEUES.items():
        mine = [i for i in all_items if i["queue"] == q]
        queues.append({
            "queue": q, "label": label, "targets": {"due": due, "backup": backup, "governance": governance},
            "size": len(mine), "overdue": sum(i["overdue"] for i in mine),
            "at_backup": sum(1 for i in mine if escalated.get(i["key"], 0) == 1),
            "at_governance": sum(1 for i in mine if escalated.get(i["key"], 0) >= 2),
            "oldest": max((i["age"] for i in mine), default=None),
            "buckets": [{"label": b, "count": sum(1 for i in mine if lo <= i["age"] <= hi)} for lo, hi, b in BUCKETS],
        })
    d = owner_domain(db, workspace_id)
    return {"workspace_id": workspace_id, "queues": queues, "total": len(all_items),
            "steward": d.steward if d else None, "backup_steward": d.backup_steward if d else None,
            "domain": d.id if d else None, "governance": governance_group()}


def owner_domain(db: Session, workspace_id: str) -> Optional[LedgerDomain]:
    """The domain whose stewards own the workspace's queues: the object
    domain not yet retired, the pilot first."""
    ds = [d for d in db.scalars(select(LedgerDomain).where(LedgerDomain.workspace_id == workspace_id))
          if d.stage != "T5"]
    ds.sort(key=lambda d: (d.resource != "objects", not d.pilot, d.id))
    return ds[0] if ds else None


def governance_group() -> list[str]:
    return [x.strip() for x in os.environ.get("ARGUS_GOVERNANCE", "").split(",") if x.strip()]


def escalate(db: Session, at: Optional[datetime] = None, workspace_id: Optional[str] = None) -> dict:
    """Notify each item's next level once: the backup steward (with the
    steward), then the governance group."""
    from app.models.workflow import Notification
    at = at or now()
    workspaces = [workspace_id] if workspace_id else sorted(
        {w for w in db.scalars(select(Conflict.workspace_id).distinct())}
        | {w for w in db.scalars(select(LedgerStream.workspace_id).distinct())})
    sent = {"backup": 0, "governance": 0, "without_recipient": 0}
    for ws in workspaces:
        d = owner_domain(db, ws)
        for item in items(db, ws, at, visible_only=False):
            row = db.get(ReviewEscalation, item["key"])
            done = row.level if row else 0
            if item["level_due"] <= done:
                continue
            level = item["level_due"]
            if level == 1:
                targets = [t for t in ((d.backup_steward, d.steward) if d else ()) if t]
            else:
                targets = governance_group() + [t for t in ((d.backup_steward,) if d else ()) if t]
            targets = list(dict.fromkeys(targets))
            label = QUEUES[item["queue"]][0]
            title = (f"{label}: an item in {ws} is {item['age']} working day(s) old, past its target "
                     f"— {'escalated to the backup steward' if level == 1 else 'escalated to the governance group'}")
            for who in targets:
                db.add(Notification(workspace_id=ws, recipient=who, kind="review_escalated", title=title,
                                    detail={"queue": item["queue"], "item": item["key"], "level": level,
                                            "age_working_days": item["age"], "path": "/review"}, created_at=at))
            if row is None:
                row = ReviewEscalation(item_key=item["key"], workspace_id=ws, queue=item["queue"],
                                       opened_at=item["opened_at"])
                db.add(row)
            row.level, row.escalated_at, row.targets = level, at, targets
            sent["backup" if level == 1 else "governance"] += 1
            if not targets:
                sent["without_recipient"] += 1
    db.flush()
    return sent
