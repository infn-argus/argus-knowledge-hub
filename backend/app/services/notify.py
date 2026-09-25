"""Watchers, notifications and escalation timers (asset-model-revision §19 item 3).

* The reporter and each assignee watch a ticket automatically; anyone can
  watch or stop watching it; a person @mentioned in a comment is notified
  and starts watching.
* A notification goes to the watchers and the assignee — never to the
  person who acted, and never to someone who may not see the ticket
  (a restricted ticket, I-ACL-1).
* A state with `sla_hours` escalates a ticket that stays in it too long:
  once per stay, to the state's `escalate_to`, the assignee and the
  watchers. `python -m app.ledger escalate` runs it; so does delivery of
  e-mail when `SMTP_HOST` is set.
"""
from __future__ import annotations

import os
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.models.user import User
from app.models.workflow import Notification, TicketEscalation, TicketWatcher
from app.services import workflows
from app.services.visibility import restricted_class

MENTION = re.compile(r"@([\w.+-]+@[\w-]+\.[\w.-]+|[\w-]{3,})")


def now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- watchers

def watch(db: Session, issue: Issue, user: Optional[str], reason: str = "manual") -> None:
    if not user:
        return
    if db.scalar(select(TicketWatcher).where(TicketWatcher.issue_uid == issue.uid, TicketWatcher.user == user)):
        return
    db.add(TicketWatcher(issue_uid=issue.uid, user=user, reason=reason, created_at=now()))
    db.flush()


def unwatch(db: Session, issue: Issue, user: str) -> None:
    row = db.scalar(select(TicketWatcher).where(TicketWatcher.issue_uid == issue.uid, TicketWatcher.user == user))
    if row is not None:
        db.delete(row)
        db.flush()


def watchers(db: Session, issue: Issue) -> list[str]:
    return list(db.scalars(select(TicketWatcher.user).where(TicketWatcher.issue_uid == issue.uid)
                           .order_by(TicketWatcher.id)))


# --------------------------------------------------------------------------- notifications

def _user(db: Session, who: str) -> Optional[User]:
    return db.get(User, who) or db.scalar(select(User).where(User.email == who))


def may_see(db: Session, issue: Issue, who: str) -> bool:
    """A recipient is told only about what they may read (I-ACL-1)."""
    cls = restricted_class(issue)
    if cls is None:
        return True
    user = _user(db, who)
    if user is None:
        return False
    from app.auth import OidcIdentity, grants_of
    return grants_of(db, OidcIdentity(user=user), issue.workspace_id).allows(cls)


def notify(db: Session, issue: Issue, kind: str, title: str, actor: Optional[str],
           recipients: Iterable[Optional[str]], detail: Optional[dict] = None) -> list[Notification]:
    out = []
    actor_ids = {actor}
    if actor:
        u = _user(db, actor)
        if u is not None:
            actor_ids |= {u.id, u.email}
    for who in dict.fromkeys(r for r in recipients if r):
        if who in actor_ids or not may_see(db, issue, who):
            continue
        n = Notification(workspace_id=issue.workspace_id, recipient=who, issue_uid=issue.uid, kind=kind, title=title,
                         detail=detail or {}, actor=actor, created_at=now())
        db.add(n)
        out.append(n)
    db.flush()
    return out


def audience(db: Session, issue: Issue) -> list[str]:
    return [*watchers(db, issue), *([issue.assignee] if issue.assignee else [])]


def on_created(db: Session, issue: Issue, actor: Optional[str]) -> None:
    watch(db, issue, issue.created_by or actor, "reporter")
    if issue.assignee:
        watch(db, issue, issue.assignee, "assignee")
        notify(db, issue, "assigned", f"Assigned to you: {issue.title}", actor, [issue.assignee])


def on_assigned(db: Session, issue: Issue, actor: Optional[str], previous: Optional[str]) -> None:
    if not issue.assignee or issue.assignee == previous:
        return
    watch(db, issue, issue.assignee, "assignee")
    notify(db, issue, "assigned", f"Assigned to you: {issue.title}", actor, [issue.assignee],
           {"previous": previous})


def on_transition(db: Session, issue: Issue, actor: Optional[str], before: str, after: str) -> None:
    if before == after:
        return
    notify(db, issue, "transitioned", f"{issue.title}: {before} → {after}", actor, audience(db, issue),
           {"from": before, "to": after})


def on_comment(db: Session, issue: Issue, actor: Optional[str], body: str) -> None:
    mentioned = []
    for m in MENTION.findall(body or ""):
        user = _user(db, m)
        if user is not None:
            mentioned.append(user.email or user.id)
    for who in mentioned:
        watch(db, issue, who, "mentioned")
    notify(db, issue, "mentioned", f"You were mentioned on {issue.title}", actor, mentioned,
           {"excerpt": (body or "")[:200]})
    others = [w for w in audience(db, issue) if w not in mentioned]
    notify(db, issue, "commented", f"New comment on {issue.title}", actor, others, {"excerpt": (body or "")[:200]})


# --------------------------------------------------------------------------- escalation

def _entered(issue: Issue) -> datetime:
    raw = (issue.attributes or {}).get("argus_state_entered_at")
    if raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return issue.updated_at or issue.created_at


def escalate_overdue(db: Session, at: Optional[datetime] = None, workspace_id: Optional[str] = None) -> int:
    """Escalate every open ticket that has outstayed its state's SLA, once
    per stay in that state."""
    at = at or now()
    q = select(Issue).where(Issue.deleted_at.is_(None), Issue.closed_at.is_(None))
    if workspace_id:
        q = q.where(Issue.workspace_id == workspace_id)
    n = 0
    for issue in db.scalars(q):
        wf = workflows.workflow_for(db, issue.workspace_id, issue.schema_uid)
        state = workflows.state_of(wf, issue.state) or {}
        hours = state.get("sla_hours")
        if not hours or state.get("category") == "done":
            continue
        entered = _entered(issue)
        due = entered + timedelta(hours=float(hours))
        if at < due:
            continue
        exists = db.scalar(select(TicketEscalation).where(TicketEscalation.issue_uid == issue.uid,
                                                          TicketEscalation.state == issue.state,
                                                          TicketEscalation.entered_at == entered))
        if exists is not None:
            continue
        targets = [t for t in [state.get("escalate_to"), *audience(db, issue)] if t]
        db.add(TicketEscalation(issue_uid=issue.uid, state=issue.state, entered_at=entered, due_at=due,
                                escalated_at=at, escalated_to=list(dict.fromkeys(targets))))
        notify(db, issue, "escalated",
               f"Overdue: {issue.title} has been {state.get('name', issue.state)} for more than {hours} h", None,
               targets, {"state": issue.state, "entered_at": entered.isoformat(), "due_at": due.isoformat()})
        n += 1
    db.flush()
    return n


def deliver_pending(db: Session) -> int:
    """Send undelivered notifications by e-mail when SMTP is configured.
    Recipients that are not e-mail addresses stay in-app only."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        return 0
    sender = os.environ.get("SMTP_FROM", "argus@localhost")
    sent = 0
    pending = list(db.scalars(select(Notification).where(Notification.delivered_at.is_(None)).limit(500)))
    with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "25"))) as smtp:
        for n in pending:
            address = n.recipient if "@" in n.recipient else ((_user(db, n.recipient) or User()).email or "")
            if "@" not in address:
                n.delivered_at = now()
                continue
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = sender, address, f"[ARGUS] {n.title}"
            msg.set_content(f"{n.title}\n\n{os.environ.get('ARGUS_URL', '')}/tickets/{n.issue_uid}\n")
            smtp.send_message(msg)
            n.delivered_at = now()
            sent += 1
    db.flush()
    return sent

