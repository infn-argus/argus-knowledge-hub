import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import get_current_user_id, require_permission
from app.db import get_db
from app.models.asset import Asset
from app.models.asset_subresources import AssetTicket
from app.models.attachment import Attachment
from app.models.document import Document, DocumentRelation
from app.models.issue import Issue, IssueComment, IssueHistory, IssueLink
from app.models.schema import Schema
from app.schemas.attachment import AttachmentOut
from app.schemas.issue import (
    BulkDeleteRequest,
    BulkDeleteResult,
    IssueCommentCreate,
    IssueCommentOut,
    IssueCreate,
    IssueAssetLinkCreate,
    IssueAssetLinkOut,
    IssueDocumentLinkCreate,
    IssueDocumentLinkOut,
    IssueHistoryOut,
    IssueLinksOut,
    IssueOut,
    IssueTicketLinkCreate,
    IssueTicketLinkOut,
    IssueUpdate,
)
from app.services.asset_ticket_links import ensure_asset_link, sync_subject_link
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
    # A ticket raised on an object has to appear on that object, or the
    # link only exists in one direction.
    if issue.asset_uid:
        sync_subject_link(db, issue, None)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("/labels", response_model=list[str])
def list_issue_labels(
    workspace_id: str = Depends(require_permission("read", resource="tickets")),
    db: Session = Depends(get_db),
):
    """Every label already in use in this workspace, so typing one offers
    what exists rather than inventing a near-duplicate ("BTF" vs "btf")."""
    rows = db.execute(
        text(
            "SELECT DISTINCT jsonb_array_elements_text(labels) AS label "
            "FROM issues WHERE workspace_id = :ws ORDER BY label"
        ),
        {"ws": workspace_id},
    ).scalars().all()
    return [r for r in rows if r]


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
    previous_asset_uid = issue.asset_uid

    if "state" in patch:
        _apply_state(issue, patch.pop("state"))
    for field, value in patch.items():
        setattr(issue, field, value)

    record_issue_changes(db, issue, before, current_user_id)
    sync_subject_link(db, issue, previous_asset_uid)

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


@router.get("/{uid}/links", response_model=IssueLinksOut)
def list_issue_links(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="tickets")),
    db: Session = Depends(get_db),
):
    """What this ticket is about: the objects it affects and the documents
    that explain or record it.

    Both come from link tables rather than attributes, because the
    knowledge graph has to walk them from either end — "what broke this
    magnet" is as much a question as "what does this ticket affect".
    """
    issue = _get_owned_issue(uid, workspace_id, db)
    source_key = (issue.attributes or {}).get("argus_source_key") or uid

    asset_rows = db.execute(
        select(AssetTicket, Asset)
        .join(Asset, Asset.uid == AssetTicket.asset_uid)
        .where(AssetTicket.ticket_key == source_key, Asset.workspace_id == workspace_id)
    ).all()
    assets = [
        IssueAssetLinkOut(asset_uid=a.uid, name=a.name, key=a.key, type=a.type,
                          relation=t.type or "affects")
        for t, a in asset_rows
    ]
    # The ticket's own subject, if it isn't already in the list.
    if issue.asset_uid and not any(a.asset_uid == issue.asset_uid for a in assets):
        primary = db.get(Asset, issue.asset_uid)
        if primary is not None:
            assets.insert(0, IssueAssetLinkOut(
                asset_uid=primary.uid, name=primary.name, key=primary.key,
                type=primary.type, relation="subject",
            ))

    doc_rows = db.execute(
        select(DocumentRelation, Document)
        .join(Document, Document.uid == DocumentRelation.from_document_uid)
        .where(
            DocumentRelation.to_type == "issue",
            DocumentRelation.to_uid == uid,
            DocumentRelation.workspace_id == workspace_id,
        )
    ).all()
    documents = [
        IssueDocumentLinkOut(
            document_uid=d.uid, code=d.code, title=d.title,
            relation=r.relation_type, relation_id=r.id,
        )
        for r, d in doc_rows
    ]
    tickets: list[IssueTicketLinkOut] = []
    for link, other, outgoing in _ticket_links(db, uid):
        tickets.append(IssueTicketLinkOut(
            link_id=link.id, issue_uid=other.uid, title=other.title, state=other.state,
            source_key=(other.attributes or {}).get("argus_source_key"),
            relation=link.relation_type, outgoing=outgoing,
        ))

    return IssueLinksOut(assets=assets, documents=documents, tickets=tickets)


def _ticket_links(db: Session, uid: str):
    """Both directions of every edge this ticket is on."""
    out = []
    for link in db.scalars(select(IssueLink).where(IssueLink.from_issue_uid == uid)):
        other = db.get(Issue, link.to_issue_uid)
        if other is not None:
            out.append((link, other, True))
    for link in db.scalars(select(IssueLink).where(IssueLink.to_issue_uid == uid)):
        other = db.get(Issue, link.from_issue_uid)
        if other is not None:
            out.append((link, other, False))
    return out


@router.post("/{uid}/links/tickets", response_model=IssueTicketLinkOut, status_code=201)
def link_issue_ticket(
    uid: str,
    body: IssueTicketLinkCreate,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    issue = _get_owned_issue(uid, workspace_id, db)
    other = _get_owned_issue(body.issue_uid, workspace_id, db)
    if other.uid == issue.uid:
        raise HTTPException(status_code=422, detail="A ticket can't link to itself")

    existing = db.scalar(
        select(IssueLink).where(
            IssueLink.from_issue_uid == issue.uid,
            IssueLink.to_issue_uid == other.uid,
            IssueLink.relation_type == body.relation,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Those tickets are already linked that way")

    now = datetime.now(timezone.utc)
    link = IssueLink(
        from_issue_uid=issue.uid, to_issue_uid=other.uid,
        relation_type=body.relation, created_at=now,
    )
    db.add(link)
    db.add(IssueHistory(
        uid=str(uuid.uuid4()), issue_uid=issue.uid, type="updated",
        author=current_user_id or "api", field="Linked ticket",
        to_value=f"{body.relation} {(other.attributes or {}).get('argus_source_key') or other.title}",
        timestamp=now,
    ))
    db.commit()
    db.refresh(link)
    return IssueTicketLinkOut(
        link_id=link.id, issue_uid=other.uid, title=other.title, state=other.state,
        source_key=(other.attributes or {}).get("argus_source_key"),
        relation=link.relation_type, outgoing=True,
    )


@router.delete("/{uid}/links/tickets/{link_id}", status_code=204)
def unlink_issue_ticket(
    uid: str,
    link_id: int,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    db: Session = Depends(get_db),
):
    _get_owned_issue(uid, workspace_id, db)
    link = db.get(IssueLink, link_id)
    # Either end may remove the edge; it is one relationship, not two.
    if link is None or uid not in (link.from_issue_uid, link.to_issue_uid):
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()


@router.post("/{uid}/links/assets", response_model=IssueAssetLinkOut, status_code=201)
def link_issue_asset(
    uid: str,
    body: IssueAssetLinkCreate,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    issue = _get_owned_issue(uid, workspace_id, db)
    asset = db.get(Asset, body.asset_uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Object not found")

    source_key = (issue.attributes or {}).get("argus_source_key") or uid
    existing = db.scalar(
        select(AssetTicket).where(
            AssetTicket.asset_uid == asset.uid, AssetTicket.ticket_key == source_key
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already linked to that object")

    now = datetime.now(timezone.utc)
    ensure_asset_link(db, issue, asset.uid, relation=body.relation)
    db.add(IssueHistory(
        uid=str(uuid.uuid4()), issue_uid=issue.uid, type="updated",
        author=current_user_id or "api", field="Linked object",
        to_value=asset.name, timestamp=now,
    ))
    db.commit()
    return IssueAssetLinkOut(
        asset_uid=asset.uid, name=asset.name, key=asset.key, type=asset.type,
        relation=body.relation,
    )


@router.delete("/{uid}/links/assets/{asset_uid}", status_code=204)
def unlink_issue_asset(
    uid: str,
    asset_uid: str,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    db: Session = Depends(get_db),
):
    issue = _get_owned_issue(uid, workspace_id, db)
    source_key = (issue.attributes or {}).get("argus_source_key") or uid
    link = db.scalar(
        select(AssetTicket).where(
            AssetTicket.asset_uid == asset_uid, AssetTicket.ticket_key == source_key
        )
    )
    if link is not None:
        db.delete(link)
    # The subject is a column on the ticket, not a link row.
    if issue.asset_uid == asset_uid:
        issue.asset_uid = None
    db.commit()


@router.post("/{uid}/links/documents", response_model=IssueDocumentLinkOut, status_code=201)
def link_issue_document(
    uid: str,
    body: IssueDocumentLinkCreate,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    issue = _get_owned_issue(uid, workspace_id, db)
    document = db.get(Document, body.document_uid)
    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")

    existing = db.scalar(
        select(DocumentRelation).where(
            DocumentRelation.from_document_uid == document.uid,
            DocumentRelation.to_type == "issue",
            DocumentRelation.to_uid == uid,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already linked to that document")

    relation = DocumentRelation(
        workspace_id=workspace_id,
        from_document_uid=document.uid,
        to_type="issue",
        to_uid=uid,
        relation_type=body.relation,
    )
    db.add(relation)
    db.add(IssueHistory(
        uid=str(uuid.uuid4()), issue_uid=issue.uid, type="updated",
        author=current_user_id or "api", field="Linked document",
        to_value=document.code, timestamp=datetime.now(timezone.utc),
    ))
    db.commit()
    db.refresh(relation)
    return IssueDocumentLinkOut(
        document_uid=document.uid, code=document.code, title=document.title,
        relation=relation.relation_type, relation_id=relation.id,
    )


@router.delete("/{uid}/links/documents/{relation_id}", status_code=204)
def unlink_issue_document(
    uid: str,
    relation_id: int,
    workspace_id: str = Depends(require_permission("modify", resource="tickets")),
    db: Session = Depends(get_db),
):
    _get_owned_issue(uid, workspace_id, db)
    relation = db.get(DocumentRelation, relation_id)
    if relation is None or relation.to_uid != uid or relation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(relation)
    db.commit()


@router.delete("/{uid}", status_code=204)
def delete_issue(
    uid: str, workspace_id: str = Depends(require_permission("delete", resource="tickets")), db: Session = Depends(get_db)
):
    issue = _get_owned_issue(uid, workspace_id, db)
    db.delete(issue)
    db.commit()


@router.post("/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_issues(
    body: BulkDeleteRequest,
    workspace_id: str = Depends(require_permission("delete", resource="tickets")),
    db: Session = Depends(get_db),
):
    deleted = 0
    missing: list[str] = []
    for uid in body.uids:
        issue = db.get(Issue, uid)
        if issue is None or issue.workspace_id != workspace_id:
            missing.append(uid)
            continue
        db.delete(issue)
        deleted += 1
    db.commit()
    return BulkDeleteResult(deleted=deleted, not_found=missing)


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
