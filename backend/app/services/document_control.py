"""Controlled documents (asset-model-revision §19 item 4).

* **Retention.** A released document is kept for its retention class,
  counted from its last publication or its retirement, whichever is later.
  Until then it cannot be deleted — only retired. A document never released
  (drafts only) holds nothing that needs keeping.
* **Separation of duties.** The author of a revision cannot approve it.
* **Supersession.** A document replaced by another is retired, points to
  its successor, and the successor records that it supersedes it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentRelation, DocumentRevision

RETENTION_YEARS = {"permanent": None, "10y": 10, "5y": 5, "2y": 2, "none": 0}


class ControlError(ValueError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def released_at(db: Session, doc: Document) -> Optional[datetime]:
    """The last moment the document was in force: its latest publication,
    or its retirement if later. None if it was never released."""
    published = db.scalar(select(func.max(DocumentRevision.published_at)).where(
        DocumentRevision.document_uid == doc.uid))
    moments = [m for m in (published, doc.retired_at) if m is not None]
    return max(moments) if moments else None


def retain_until(db: Session, doc: Document) -> Optional[datetime]:
    """None when there is nothing to keep; datetime.max for permanent."""
    base = released_at(db, doc)
    if base is None:
        return None
    years = RETENTION_YEARS.get(doc.retention_class or "5y", 5)
    if years is None:
        return datetime.max.replace(tzinfo=timezone.utc)
    return base + timedelta(days=round(365.25 * years))


def retention_view(db: Session, doc: Document) -> dict:
    until = retain_until(db, doc)
    permanent = until is not None and until.year == 9999
    return {"class": doc.retention_class, "released_at": released_at(db, doc),
            "retain_until": None if until is None or permanent else until, "permanent": permanent,
            "deletable": until is None or (not permanent and now() >= until),
            "retired_at": doc.retired_at, "superseded_by": doc.superseded_by_uid}


def assert_deletable(db: Session, doc: Document) -> None:
    v = retention_view(db, doc)
    if not v["deletable"]:
        when = "permanently" if v["permanent"] else f"until {v['retain_until']:%Y-%m-%d}"
        raise ControlError(f"{doc.code} is under retention ({doc.retention_class}) {when}; retire it instead")


def set_retention(db: Session, doc: Document, retention_class: str) -> None:
    if retention_class not in RETENTION_YEARS:
        raise ControlError(f"retention class must be one of {', '.join(RETENTION_YEARS)}")
    current = RETENTION_YEARS.get(doc.retention_class or "5y", 5)
    new = RETENTION_YEARS[retention_class]
    # Shortening the retention of a released document would release it early.
    shorter = current is None and new is not None or (current is not None and new is not None and new < current)
    if shorter and released_at(db, doc) is not None:
        raise ControlError("the retention of a released document can be lengthened, not shortened")
    doc.retention_class = retention_class


def assert_not_author(revision: DocumentRevision, approver: Optional[str]) -> None:
    if approver and revision.authored_by and approver == revision.authored_by:
        raise ControlError("the author of a revision cannot approve it; another approver must")


def supersede(db: Session, old: Document, new: Document, reason: str) -> None:
    """`new` replaces `old`: `old` retires and points to `new`."""
    if old.uid == new.uid:
        raise ControlError("a document cannot supersede itself")
    if old.superseded_by_uid:
        raise ControlError(f"{old.code} is already superseded")
    current = db.get(DocumentRevision, new.current_revision_uid) if new.current_revision_uid else None
    if current is None or current.state != "published":
        raise ControlError(f"{new.code} must have a published revision to supersede another document")
    if old.current_revision_uid:
        rev = db.get(DocumentRevision, old.current_revision_uid)
        if rev is not None and rev.state == "published":
            rev.state = "superseded"
            rev.review_comment = reason
    old.current_revision_uid = None
    old.retired_at = now()
    old.superseded_by_uid = new.uid
    db.add(DocumentRelation(workspace_id=new.workspace_id, from_document_uid=new.uid, to_type="document",
                            to_uid=old.uid, relation_type="supersedes"))
    db.flush()
