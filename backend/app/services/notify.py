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


EDIT_FIELDS = {"title": "title", "description": "description", "priority": "priority", "due_date": "due date",
               "asset_uid": "equipment", "attributes": "fields"}


def on_edited(db: Session, issue: Issue, actor: Optional[str], before: dict, previous_assignee: Optional[str]) -> None:
    """A ticket's title, description, priority, due date, equipment or fields changed: told to its watchers.
    A new assignee is told on their own ("Assigned to you"), and a new state on its own."""
    changed = [label for field, label in EDIT_FIELDS.items() if before.get(field) != getattr(issue, field, None)]
    if not changed:
        return
    newly_assigned = issue.assignee if issue.assignee != previous_assignee else None
    notify(db, issue, "updated", f"{issue.title}: {', '.join(changed)} changed", actor,
           [w for w in audience(db, issue) if w != newly_assigned], {"changed": changed})


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



# --------------------------------------------------------------------------- subscriptions

SUBJECTS = {"tickets": "ticket", "documents": "document", "assets": "asset"}


def announce(db: Session, workspace_id: str, what: str, kind: str, title: str, actor: Optional[str], uid: str,
             issue: Optional[Issue] = None, record=None) -> list[Notification]:
    """Something new in a workspace, told to everyone who asked to hear about that kind of thing there
    (`what`: tickets, documents or assets) — never to the person who made it, and only to those who may
    read it: the resource's read permission, and a restricted record's class (I-ACL-1)."""
    from app.auth import OidcIdentity, grants_of
    from app.models.workflow import NotificationSubscription
    from app.services.permissions import resolve_permission
    from app.services.visibility import can_see
    column = getattr(NotificationSubscription, what)
    actor_user = _user(db, actor) if actor else None
    resource = {"tickets": "tickets", "documents": "documents", "assets": "objects"}[what]
    out = []
    for sub in db.scalars(select(NotificationSubscription).where(
            NotificationSubscription.workspace_id == workspace_id, column.is_(True))):
        user = db.get(User, sub.user_id)
        if user is None or (actor_user is not None and user.id == actor_user.id) or actor in (user.id, user.email):
            continue
        if not resolve_permission(db, user, workspace_id, "read", resource):
            continue
        if issue is not None and not may_see(db, issue, user.id):
            continue
        if record is not None and not can_see(record, grants_of(db, OidcIdentity(user=user), workspace_id)):
            continue
        n = Notification(workspace_id=workspace_id, recipient=user.id, issue_uid=issue.uid if issue else None,
                         kind=kind, title=title, detail={"subject": SUBJECTS[what], "uid": uid}, actor=actor,
                         created_at=now())
        db.add(n)
        out.append(n)
    db.flush()
    return out


# --------------------------------------------------------------------------- following equipment and documents

def follow(db: Session, subject: str, uid: str, user_id: Optional[str]) -> None:
    from app.models.workflow import RecordWatcher
    if not user_id or db.get(User, user_id) is None:
        return
    if db.scalar(select(RecordWatcher).where(RecordWatcher.subject == subject, RecordWatcher.subject_uid == uid,
                                             RecordWatcher.user_id == user_id)) is None:
        db.add(RecordWatcher(subject=subject, subject_uid=uid, user_id=user_id, created_at=now()))
        db.flush()


def unfollow(db: Session, subject: str, uid: str, user_id: str) -> None:
    from app.models.workflow import RecordWatcher
    row = db.scalar(select(RecordWatcher).where(RecordWatcher.subject == subject, RecordWatcher.subject_uid == uid,
                                                RecordWatcher.user_id == user_id))
    if row is not None:
        db.delete(row)
        db.flush()


def followers(db: Session, subject: str, uid: str) -> list[str]:
    from app.models.workflow import RecordWatcher
    return list(db.scalars(select(RecordWatcher.user_id).where(RecordWatcher.subject == subject,
                                                               RecordWatcher.subject_uid == uid)))


def may_read_record(db: Session, user: User, subject: str, record) -> bool:
    """Whether this person may read this piece of equipment or document: in its workspace, or anywhere when it
    is shared (global) — and a restricted one only with its class (I-ACL-1)."""
    from app.auth import OidcIdentity, grants_of
    from app.services.permissions import resolve_permission
    from app.services.visibility import can_see
    resource = "objects" if subject == "asset" else "documents"
    ws = record.workspace_id
    if not resolve_permission(db, user, ws, "read", resource):
        if not getattr(record, "is_global", False):
            return False
        if subject == "document" and getattr(record, "confidentiality", None) == "riservato":
            return False
    if subject == "asset":
        return can_see(record, grants_of(db, OidcIdentity(user=user), ws))
    return True


def tell_followers(db: Session, subject: str, record, kind: str, title: str, actor: Optional[str],
                   detail: Optional[dict] = None) -> list[Notification]:
    """A change to a piece of equipment or a document, told to the people following it — never to the person
    who made it, and only to those who may read it."""
    actor_user = _user(db, actor) if actor else None
    out = []
    for user_id in followers(db, subject, record.uid):
        user = db.get(User, user_id)
        if user is None or (actor_user is not None and user.id == actor_user.id) or actor in (user.id, user.email):
            continue
        if not may_read_record(db, user, subject, record):
            continue
        n = Notification(workspace_id=record.workspace_id, recipient=user.id, issue_uid=None, kind=kind, title=title,
                         detail={"subject": subject, "uid": record.uid, **(detail or {})}, actor=actor,
                         created_at=now())
        db.add(n)
        out.append(n)
    db.flush()
    return out


def asset_changed(db: Session, asset_uid: str, what: str, actor: Optional[str]) -> None:
    """A history line on a piece of equipment (an edit, a label, a file, a comment), told to its followers."""
    from app.models.asset import Asset
    asset = db.get(Asset, asset_uid)
    if asset is None:
        return
    tell_followers(db, "asset", asset, "asset_changed", f"{asset.name} ({asset.key}): {what}"[:300], actor)


def document_changed(db: Session, doc, what: str, actor: Optional[str]) -> None:
    """A step in a document's life (a new revision, a review, a publication, a retirement), told to its
    followers."""
    tell_followers(db, "document", doc, "document_changed", f"{doc.code} {doc.title}: {what}"[:300], actor)
