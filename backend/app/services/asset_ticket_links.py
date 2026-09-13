"""Keeping an object's ticket list and a ticket's subject in step.

A ticket names the object it is about in Issue.asset_uid; the object's own
ticket list is asset_tickets rows. Those are two facts about one
relationship, and if only the first is written, a ticket raised on a
camera never appears on that camera.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.asset_subresources import AssetTicket
from app.models.issue import Issue


def ticket_key_for(issue: Issue) -> str:
    """What the object's ticket list calls this ticket. The source key when
    it has one, so a row the asset import already created for "LNFDCS-563"
    is the same row rather than a second one."""
    return (issue.attributes or {}).get("argus_source_key") or issue.uid


def ensure_asset_link(db: Session, issue: Issue, asset_uid: str, relation: str = "affects") -> bool:
    """Make sure the object lists this ticket. Returns whether a row was
    added."""
    asset = db.get(Asset, asset_uid)
    if asset is None or asset.workspace_id != issue.workspace_id:
        return False

    ticket_key = ticket_key_for(issue)
    existing = db.scalar(
        select(AssetTicket).where(
            AssetTicket.asset_uid == asset_uid, AssetTicket.ticket_key == ticket_key
        )
    )
    now = datetime.now(timezone.utc)
    if existing is not None:
        # Keep the denormalised copy honest — it is what the object's list
        # shows, and a stale title or state there is worse than none.
        existing.summary = issue.title
        existing.status = issue.state
        existing.updated = now
        return False

    db.add(AssetTicket(
        uid=str(uuid.uuid4()),
        asset_uid=asset_uid,
        ticket_key=ticket_key,
        summary=issue.title,
        type=relation,
        status=issue.state,
        created=now,
        updated=now,
        backend_url=(issue.attributes or {}).get("argus_source_url"),
    ))
    return True


def sync_subject_link(db: Session, issue: Issue, previous_asset_uid: Optional[str]) -> None:
    """Follow a change of subject: the new object gains the ticket, and the
    old one loses it — but only the row that was there *because* it was the
    subject, so a link added deliberately isn't swept away."""
    if previous_asset_uid == issue.asset_uid:
        if issue.asset_uid:
            ensure_asset_link(db, issue, issue.asset_uid, relation="subject")
        return

    if previous_asset_uid:
        stale = db.scalar(
            select(AssetTicket).where(
                AssetTicket.asset_uid == previous_asset_uid,
                AssetTicket.ticket_key == ticket_key_for(issue),
                AssetTicket.type == "subject",
            )
        )
        if stale is not None:
            db.delete(stale)

    if issue.asset_uid:
        ensure_asset_link(db, issue, issue.asset_uid, relation="subject")


def issue_uid_by_ticket_key(db: Session, workspace_id: str) -> dict[str, str]:
    """ticket_key -> local ticket uid, so an object's list can link to the
    ticket rather than only naming it."""
    out: dict[str, str] = {}
    for issue in db.scalars(select(Issue).where(Issue.workspace_id == workspace_id)):
        out[ticket_key_for(issue)] = issue.uid
        out.setdefault(issue.uid, issue.uid)
    return out
