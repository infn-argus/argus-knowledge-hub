import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import get_current_user_id, require_permission
from app.db import get_db
from app.models.attachment import Attachment
from app.models.issue import Issue, IssueComment, IssueHistory
from app.models.schema import Schema
from app.schemas.attachment import AttachmentOut
from app.schemas.issue import (
    IssueCommentCreate,
    IssueCommentOut,
    IssueCreate,
    IssueHistoryOut,
    IssueOut,
    IssueUpdate,
)
from app.services.issue_history import (
    TRACKED_FIELDS,
    record_issue_changes,
    record_issue_created,
)
from app.services.attribute_validation import validate_attributes
from app.services.current_user_attrs import stamp_current_user_attributes

router = APIRouter(prefix="/v1/issues", tags=["issues"])

ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "/data/attachments")


def _get_owned_issue(uid: str, workspace_id: str, db: Session) -> Issue:
    issue = db.get(Issue, uid)
    if issue is None or issue.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.get("", response_model=list[IssueOut])
def list_issues(
    schema_uid: Optional[str] = None,
    workspace_id: str = Depends(require_permission("read", resource="tickets")),
    db: Session = Depends(get_db),
):
    stmt = select(Issue).where(Issue.workspace_id == workspace_id)
    if schema_uid:
        stmt = stmt.where(Issue.schema_uid == schema_uid)
    return db.scalars(stmt).all()


@router.post("", response_model=IssueOut, status_code=201)
def create_issue(
    body: IssueCreate,
    workspace_id: str = Depends(require_permission("create", resource="tickets")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if db.get(Issue, body.uid) is not None:
        raise HTTPException(status_code=409, detail="Issue uid already exists")
    schema = db.get(Schema, body.schema_uid) if body.schema_uid else None
    stamp_current_user_attributes(db, schema, body.attributes, current_user_id)
    validate_attributes(db, schema, body.attributes, workspace_id, Issue)
    issue = Issue(workspace_id=workspace_id, **body.model_dump())
    db.add(issue)
    db.flush()
    record_issue_created(db, issue, current_user_id)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("/{uid}", response_model=IssueOut)
def get_issue(
    uid: str, workspace_id: str = Depends(require_permission("read", resource="tickets")), db: Session = Depends(get_db)
):
    return _get_owned_issue(uid, workspace_id, db)


def _apply_state(issue: Issue, new_state: str) -> None:
    issue.state = new_state
    issue.closed_at = datetime.now(timezone.utc) if new_state == "closed" else None


@router.put("/{uid}", response_model=IssueOut)
def update_issue(
    uid: str,
    body: IssueUpdate,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    issue = _get_owned_issue(uid, workspace_id, db)
    patch = body.model_dump(exclude_unset=True)
    # Captured before anything is written, so the entry says what actually
    # changed rather than comparing a value with itself.
    before = {field: getattr(issue, field, None) for field in TRACKED_FIELDS}

    if "state" in patch:
        _apply_state(issue, patch.pop("state"))
    for field, value in patch.items():
        setattr(issue, field, value)

    record_issue_changes(db, issue, before, current_user_id)

    schema = db.get(Schema, issue.schema_uid) if issue.schema_uid else None
    stamp_current_user_attributes(db, schema, issue.attributes, current_user_id)
    flag_modified(issue, "attributes")

    if "attributes" in patch or "schema_uid" in patch:
        validate_attributes(db, schema, issue.attributes, workspace_id, Issue, exclude_uid=uid)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("/{uid}/history", response_model=list[IssueHistoryOut])
def list_issue_history(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="tickets")),
    db: Session = Depends(get_db),
):
    _get_owned_issue(uid, workspace_id, db)
    return db.scalars(
        select(IssueHistory)
        .where(IssueHistory.issue_uid == uid)
        .order_by(IssueHistory.timestamp.desc())
    ).all()


@router.get("/{uid}/attachments", response_model=list[AttachmentOut])
def list_issue_attachments(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="tickets")),
    db: Session = Depends(get_db),
):
    _get_owned_issue(uid, workspace_id, db)
    return db.scalars(select(Attachment).where(Attachment.issue_uid == uid)).all()


@router.post("/{uid}/attachments", response_model=AttachmentOut, status_code=201)
async def upload_issue_attachment(
    uid: str,
    file: UploadFile,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    issue = _get_owned_issue(uid, workspace_id, db)

    attachment_uid = str(uuid.uuid4())
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    storage_path = os.path.join(ATTACHMENTS_DIR, attachment_uid)
    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    attachment = Attachment(
        uid=attachment_uid,
        workspace_id=workspace_id,
        issue_uid=uid,
        filename=file.filename or attachment_uid,
        mime_type=file.content_type,
        file_size=len(contents),
        storage_path=storage_path,
        author=current_user_id,
    )
    db.add(attachment)
    db.add(IssueHistory(
        uid=str(uuid.uuid4()),
        issue_uid=issue.uid,
        type="updated",
        author=current_user_id or "api",
        field="Attachment",
        to_value=attachment.filename,
        timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(attachment)
    return attachment


@router.delete("/{uid}", status_code=204)
def delete_issue(
    uid: str, workspace_id: str = Depends(require_permission("delete", resource="tickets")), db: Session = Depends(get_db)
):
    issue = _get_owned_issue(uid, workspace_id, db)
    db.delete(issue)
    db.commit()


@router.post("/{uid}/close", response_model=IssueOut)
def close_issue(
    uid: str, workspace_id: str = Depends(require_permission("modify", resource="tickets")), db: Session = Depends(get_db)
):
    issue = _get_owned_issue(uid, workspace_id, db)
    _apply_state(issue, "closed")
    db.commit()
    db.refresh(issue)
    return issue


@router.post("/{uid}/reopen", response_model=IssueOut)
def reopen_issue(
    uid: str, workspace_id: str = Depends(require_permission("modify", resource="tickets")), db: Session = Depends(get_db)
):
    issue = _get_owned_issue(uid, workspace_id, db)
    _apply_state(issue, "new")
    db.commit()
    db.refresh(issue)
    return issue


@router.get("/{uid}/comments", response_model=list[IssueCommentOut])
def list_issue_comments(
    uid: str, workspace_id: str = Depends(require_permission("read", resource="tickets")), db: Session = Depends(get_db)
):
    _get_owned_issue(uid, workspace_id, db)
    return db.scalars(
        select(IssueComment).where(IssueComment.issue_uid == uid)
    ).all()


@router.post("/{uid}/comments", response_model=IssueCommentOut, status_code=201)
def create_issue_comment(
    uid: str,
    body: IssueCommentCreate,
    workspace_id: str = Depends(require_permission("create", resource="tickets")),
    db: Session = Depends(get_db),
):
    _get_owned_issue(uid, workspace_id, db)
    comment = IssueComment(issue_uid=uid, **body.model_dump())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
