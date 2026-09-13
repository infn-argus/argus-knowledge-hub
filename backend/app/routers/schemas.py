import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.attachment import Attachment
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.schemas.schema import SchemaCreate, SchemaOut, SchemaUpdate
from app.services.relations import rebuild_relations_for_schemas

router = APIRouter(prefix="/v1/schemas", tags=["schemas"])

ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "/data/attachments")


@router.get("", response_model=list[SchemaOut])
def list_schemas(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    return db.scalars(
        select(Schema).where(
            or_(Schema.workspace_id == workspace_id, Schema.is_global.is_(True))
        )
    ).all()


@router.post("", response_model=SchemaOut, status_code=201)
def create_schema(
    body: SchemaCreate,
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    if db.get(Schema, body.uid) is not None:
        raise HTTPException(status_code=409, detail="Schema uid already exists")
    schema = Schema(workspace_id=workspace_id, **body.model_dump())
    # A globally-shared workspace shares every type in it, including ones
    # created after the flag was set — otherwise the workspace-level flag
    # silently decays as new types appear.
    workspace = db.get(Workspace, workspace_id)
    if workspace is not None and workspace.is_global:
        schema.is_global = True
    db.add(schema)
    db.commit()
    db.refresh(schema)
    return schema


def _get_owned_schema(uid: str, workspace_id: str, db: Session) -> Schema:
    """Strict same-workspace lookup — used by every write endpoint. A global
    schema owned by another workspace is visible (see _get_visible_schema) but
    still can't be edited except by its owning workspace."""
    schema = db.get(Schema, uid)
    if schema is None or schema.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schema


def _get_visible_schema(uid: str, workspace_id: str, db: Session) -> Schema:
    schema = db.get(Schema, uid)
    if schema is None or (schema.workspace_id != workspace_id and not schema.is_global):
        raise HTTPException(status_code=404, detail="Schema not found")
    return schema


@router.get("/{uid}", response_model=SchemaOut)
def get_schema(
    uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    return _get_visible_schema(uid, workspace_id, db)


def _cascade_global_to_children(db: Session, schema: Schema) -> list[str]:
    """When a type becomes global, its whole subtree becomes global too —
    otherwise a child type's instances would stay invisible cross-workspace
    even though the parent type says "referenceable from anywhere"."""
    changed_uids = [schema.uid]
    stack = [schema.uid]
    while stack:
        parent_uid = stack.pop()
        children = db.scalars(select(Schema).where(Schema.parent_schema_uid == parent_uid)).all()
        for child in children:
            if not child.is_global:
                child.is_global = True
                changed_uids.append(child.uid)
            stack.append(child.uid)
    return changed_uids


@router.put("/{uid}", response_model=SchemaOut)
def update_schema(
    uid: str,
    body: SchemaUpdate,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    schema = _get_owned_schema(uid, workspace_id, db)
    patch = body.model_dump(exclude_unset=True)
    turning_global = patch.get("is_global") is True and not schema.is_global
    turning_non_global = patch.get("is_global") is False and schema.is_global
    for field, value in patch.items():
        setattr(schema, field, value)

    affected_schema_uids: list[str] = []
    if turning_global:
        affected_schema_uids = _cascade_global_to_children(db, schema)
    elif turning_non_global:
        affected_schema_uids = [schema.uid]

    db.commit()
    db.refresh(schema)

    if affected_schema_uids:
        rebuild_relations_for_schemas(db, affected_schema_uids)
        db.commit()

    return schema


@router.delete("/{uid}", status_code=204)
def delete_schema(
    uid: str, workspace_id: str = Depends(require_permission("delete")), db: Session = Depends(get_db)
):
    """Deleting a type cascades (at the DB level, via ON DELETE CASCADE) to its
    child types, and to every object/ticket of the type or any of its
    children — including ones owned by other workspaces if the type is
    global. A ticket merely *linked* to a deleted object keeps existing with
    that link cleared (asset_uid ON DELETE SET NULL)."""
    schema = _get_owned_schema(uid, workspace_id, db)
    db.delete(schema)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not delete this type — it is still referenced elsewhere",
        )


@router.post("/{uid}/icon", response_model=SchemaOut)
async def upload_schema_icon(
    uid: str,
    file: UploadFile,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    schema = _get_owned_schema(uid, workspace_id, db)
    previous_uid = schema.icon_attachment_uid

    attachment_uid = str(uuid.uuid4())
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    storage_path = os.path.join(ATTACHMENTS_DIR, attachment_uid)
    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    db.add(Attachment(
        uid=attachment_uid,
        workspace_id=workspace_id,
        asset_uid=None,
        filename=file.filename or attachment_uid,
        mime_type=file.content_type,
        file_size=len(contents),
        storage_path=storage_path,
    ))
    schema.icon_attachment_uid = attachment_uid
    _discard_icon_attachment(db, previous_uid, workspace_id)
    db.commit()
    db.refresh(schema)
    return schema


def _discard_icon_attachment(db: Session, attachment_uid: Optional[str], workspace_id: str) -> None:
    """A type icon isn't attached to any object, so once a type stops
    pointing at it nothing can reach it again — unlike an object's avatar,
    which stays visible among that object's attachments. Drop the row and
    the file instead of leaving an unreachable blob behind."""
    if not attachment_uid:
        return
    attachment = db.get(Attachment, attachment_uid)
    if attachment is None or attachment.workspace_id != workspace_id:
        return
    if attachment.asset_uid is not None:
        return
    if attachment.storage_path and os.path.exists(attachment.storage_path):
        os.remove(attachment.storage_path)
    db.delete(attachment)


@router.delete("/{uid}/icon", response_model=SchemaOut)
def clear_schema_icon(
    uid: str,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    schema = _get_owned_schema(uid, workspace_id, db)
    previous_uid = schema.icon_attachment_uid
    schema.icon_attachment_uid = None
    _discard_icon_attachment(db, previous_uid, workspace_id)
    db.commit()
    db.refresh(schema)
    return schema
