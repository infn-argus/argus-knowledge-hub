from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import Identity, OidcIdentity, PatIdentity, get_identity, require_permission
from app.db import get_db
from app.services.permissions import has_permission
from app.models.document import Document, DocumentRelation, DocumentRevision
from app.models.schema import Schema
from app.schemas.document import (
    ApproveAction,
    DocumentCreate,
    DocumentOut,
    DocumentRelationCreate,
    DocumentRelationOut,
    DocumentRevisionCreate,
    DocumentRevisionOut,
    DocumentRevisionUpdate,
    DocumentUpdate,
    RejectAction,
    RetireAction,
)
from app.services.attribute_validation import check_attributes
from app.services.current_user_attrs import stamp_current_user_attributes

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _get_owned_document(uid: str, workspace_id: str, db: Session) -> Document:
    doc = db.get(Document, uid)
    if doc is None or doc.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _actor_user_id(identity: Identity) -> Optional[str]:
    return identity.user.id if isinstance(identity, OidcIdentity) else None


def _can_approve(workspace_id: str, identity: Identity, db: Session) -> bool:
    """Approval authority, resolved the same way as everything else — so the
    Approver role grants it, not only a legacy membership flag."""
    if isinstance(identity, PatIdentity):
        return True
    return has_permission(db, identity.user, workspace_id, "approve", "documents")


def _check_confidentiality(doc: Document, workspace_id: str, identity: Identity, db: Session) -> None:
    if doc.confidentiality != "riservato":
        return
    if isinstance(identity, PatIdentity):
        return
    if identity.user.is_admin or identity.user.id == doc.owner_user_id:
        return
    if _can_approve(workspace_id, identity, db):
        return
    raise HTTPException(status_code=404, detail="Document not found")


def _get_visible_document(
    uid: str, workspace_id: str, identity: Identity, db: Session
) -> Document:
    doc = db.get(Document, uid)
    if doc is None or doc.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Document not found")
    _check_confidentiality(doc, workspace_id, identity, db)
    return doc


def _get_revision(document_uid: str, revision_uid: str, db: Session) -> DocumentRevision:
    rev = db.get(DocumentRevision, revision_uid)
    if rev is None or rev.document_uid != document_uid:
        raise HTTPException(status_code=404, detail="Revision not found")
    return rev


def _validate_revision_attributes(
    db: Session, doc: Document, attributes: dict, workspace_id: str, exclude_uid: Optional[str]
) -> None:
    schema = db.get(Schema, doc.document_type_uid) if doc.document_type_uid else None
    violations = check_attributes(
        db, schema, attributes, workspace_id, Document, exclude_uid=exclude_uid,
        schema_uid_attr="document_type_uid", skip_unique=True,
    )
    if violations:
        raise HTTPException(status_code=422, detail=violations[0])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    document_type_uid: Optional[str] = None,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    db: Session = Depends(get_db),
):
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    if document_type_uid:
        stmt = stmt.where(Document.document_type_uid == document_type_uid)
    return db.scalars(stmt).all()


@router.post("", response_model=DocumentOut, status_code=201)
def create_document(
    body: DocumentCreate,
    workspace_id: str = Depends(require_permission("create", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    if db.get(Document, body.uid) is not None:
        raise HTTPException(status_code=409, detail="Document uid already exists")
    if db.scalar(select(Document).where(Document.code == body.code)) is not None:
        raise HTTPException(status_code=409, detail="Document code already exists")

    doc = Document(
        uid=body.uid, workspace_id=workspace_id, code=body.code, title=body.title,
        document_type_uid=body.document_type_uid, owner_user_id=body.owner_user_id,
        responsible_service_asset_uid=body.responsible_service_asset_uid,
        authority_level=body.authority_level, confidentiality=body.confidentiality,
        source=body.source,
    )
    doc_schema = db.get(Schema, doc.document_type_uid) if doc.document_type_uid else None
    stamp_current_user_attributes(db, doc_schema, body.attributes, _actor_user_id(identity))
    _validate_revision_attributes(db, doc, body.attributes, workspace_id, exclude_uid=None)
    db.add(doc)
    db.flush()

    revision = DocumentRevision(
        uid=f"{body.uid}-r1", document_uid=doc.uid, revision_number=1, state="draft",
        body_markdown=body.body_markdown, steps=body.steps, attributes=body.attributes,
        valid_from=body.valid_from, valid_until=body.valid_until,
        next_review_due=body.next_review_due, authored_by=_actor_user_id(identity),
    )
    db.add(revision)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{uid}", response_model=DocumentOut)
def get_document(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    return _get_visible_document(uid, workspace_id, identity, db)


@router.put("/{uid}", response_model=DocumentOut)
def update_document(
    uid: str,
    body: DocumentUpdate,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(uid, workspace_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{uid}", status_code=204)
def delete_document(
    uid: str,
    workspace_id: str = Depends(require_permission("delete", resource="documents")),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(uid, workspace_id, db)
    db.delete(doc)
    db.commit()


@router.post("/{uid}/retire", response_model=DocumentOut)
def retire_document(
    uid: str,
    body: RetireAction,
    workspace_id: str = Depends(require_permission("delete", resource="documents")),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(uid, workspace_id, db)
    if doc.current_revision_uid:
        current = db.get(DocumentRevision, doc.current_revision_uid)
        if current and current.state == "published":
            current.state = "retired"
            current.review_comment = body.reason
    doc.current_revision_uid = None
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{uid}/current", response_model=DocumentRevisionOut)
def get_current_revision(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    """ARGUS-facing: the single currently-published, currently-visible
    revision, or 404 — never a draft, never anything the caller can't see."""
    doc = _get_visible_document(uid, workspace_id, identity, db)
    if not doc.current_revision_uid:
        raise HTTPException(status_code=404, detail="No published revision")
    return db.get(DocumentRevision, doc.current_revision_uid)


@router.get("/{uid}/revisions", response_model=list[DocumentRevisionOut])
def list_revisions(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _get_visible_document(uid, workspace_id, identity, db)
    return db.scalars(
        select(DocumentRevision)
        .where(DocumentRevision.document_uid == uid)
        .order_by(DocumentRevision.revision_number)
    ).all()


@router.post("/{uid}/revisions", response_model=DocumentRevisionOut, status_code=201)
def create_revision(
    uid: str,
    body: DocumentRevisionCreate,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(uid, workspace_id, db)
    open_revision = db.scalar(
        select(DocumentRevision).where(
            DocumentRevision.document_uid == uid,
            DocumentRevision.state.in_(("draft", "in_review", "approved")),
        )
    )
    if open_revision is not None:
        raise HTTPException(
            status_code=409, detail="A draft/review/approved revision is already open"
        )
    doc_schema = db.get(Schema, doc.document_type_uid) if doc.document_type_uid else None
    stamp_current_user_attributes(db, doc_schema, body.attributes, _actor_user_id(identity))
    _validate_revision_attributes(db, doc, body.attributes, workspace_id, exclude_uid=doc.uid)

    last_number = db.scalar(
        select(DocumentRevision.revision_number)
        .where(DocumentRevision.document_uid == uid)
        .order_by(DocumentRevision.revision_number.desc())
    ) or 0
    revision = DocumentRevision(
        uid=f"{uid}-r{last_number + 1}", document_uid=uid, revision_number=last_number + 1,
        state="draft", body_markdown=body.body_markdown, steps=body.steps,
        attributes=body.attributes, valid_from=body.valid_from, valid_until=body.valid_until,
        next_review_due=body.next_review_due, authored_by=_actor_user_id(identity),
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/{uid}/revisions/{rev_uid}", response_model=DocumentRevisionOut)
def get_revision(
    uid: str,
    rev_uid: str,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _get_visible_document(uid, workspace_id, identity, db)
    return _get_revision(uid, rev_uid, db)


@router.put("/{uid}/revisions/{rev_uid}", response_model=DocumentRevisionOut)
def update_revision(
    uid: str,
    rev_uid: str,
    body: DocumentRevisionUpdate,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(uid, workspace_id, db)
    revision = _get_revision(uid, rev_uid, db)
    if revision.state != "draft":
        raise HTTPException(status_code=409, detail="Only a draft revision can be edited")
    patch = body.model_dump(exclude_unset=True)
    for field, value in patch.items():
        setattr(revision, field, value)

    doc_schema = db.get(Schema, doc.document_type_uid) if doc.document_type_uid else None
    stamp_current_user_attributes(db, doc_schema, revision.attributes, _actor_user_id(identity))
    flag_modified(revision, "attributes")

    if "attributes" in patch:
        _validate_revision_attributes(db, doc, revision.attributes, workspace_id, exclude_uid=doc.uid)
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/{uid}/revisions/{rev_uid}/submit", response_model=DocumentRevisionOut)
def submit_revision(
    uid: str,
    rev_uid: str,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    _get_owned_document(uid, workspace_id, db)
    revision = _get_revision(uid, rev_uid, db)
    if revision.state != "draft":
        raise HTTPException(status_code=409, detail="Only a draft revision can be submitted")
    revision.state = "in_review"
    revision.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/{uid}/revisions/{rev_uid}/approve", response_model=DocumentRevisionOut)
def approve_revision(
    uid: str,
    rev_uid: str,
    body: ApproveAction,
    workspace_id: str = Depends(require_permission("approve", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _get_owned_document(uid, workspace_id, db)
    revision = _get_revision(uid, rev_uid, db)
    if revision.state != "in_review":
        raise HTTPException(status_code=409, detail="Only an in-review revision can be approved")
    revision.state = "approved"
    revision.approved_by = _actor_user_id(identity)
    revision.approved_at = datetime.now(timezone.utc)
    revision.review_comment = body.comment
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/{uid}/revisions/{rev_uid}/reject", response_model=DocumentRevisionOut)
def reject_revision(
    uid: str,
    rev_uid: str,
    body: RejectAction,
    workspace_id: str = Depends(require_permission("approve", resource="documents")),
    db: Session = Depends(get_db),
):
    _get_owned_document(uid, workspace_id, db)
    revision = _get_revision(uid, rev_uid, db)
    if revision.state != "in_review":
        raise HTTPException(status_code=409, detail="Only an in-review revision can be rejected")
    revision.state = "draft"
    revision.review_comment = body.comment
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/{uid}/revisions/{rev_uid}/publish", response_model=DocumentRevisionOut)
def publish_revision(
    uid: str,
    rev_uid: str,
    workspace_id: str = Depends(require_permission("approve", resource="documents")),
    db: Session = Depends(get_db),
):
    doc = _get_owned_document(uid, workspace_id, db)
    revision = _get_revision(uid, rev_uid, db)
    if revision.state != "approved":
        raise HTTPException(status_code=409, detail="Only an approved revision can be published")

    if doc.current_revision_uid:
        previous = db.get(DocumentRevision, doc.current_revision_uid)
        if previous is not None:
            previous.state = "superseded"
            previous.superseded_by_uid = revision.uid

    revision.state = "published"
    revision.published_at = datetime.now(timezone.utc)
    doc.current_revision_uid = revision.uid
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/{uid}/relations", response_model=list[DocumentRelationOut])
def list_relations(
    uid: str,
    workspace_id: str = Depends(require_permission("read", resource="documents")),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _get_visible_document(uid, workspace_id, identity, db)
    return db.scalars(
        select(DocumentRelation).where(DocumentRelation.from_document_uid == uid)
    ).all()


@router.post("/{uid}/relations", response_model=DocumentRelationOut, status_code=201)
def create_relation(
    uid: str,
    body: DocumentRelationCreate,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    _get_owned_document(uid, workspace_id, db)
    relation = DocumentRelation(
        workspace_id=workspace_id, from_document_uid=uid,
        to_type=body.to_type, to_uid=body.to_uid, relation_type=body.relation_type,
    )
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.delete("/{uid}/relations/{relation_id}", status_code=204)
def delete_relation(
    uid: str,
    relation_id: int,
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    _get_owned_document(uid, workspace_id, db)
    relation = db.get(DocumentRelation, relation_id)
    if relation is None or relation.from_document_uid != uid or relation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Relation not found")
    db.delete(relation)
    db.commit()
