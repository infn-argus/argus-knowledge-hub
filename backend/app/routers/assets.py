import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import get_current_user_id, require_permission
from app.db import get_db
from app.models.asset import Asset, Relation
from app.models.attachment import Attachment
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.schemas.asset import (
    AssetCreate,
    AssetOut,
    AssetUpdate,
    BulkDeleteRequest,
    BulkDeleteResult,
    RelationCreate,
    RelationOut,
)
from app.services.attribute_validation import validate_attributes
from app.services.current_user_attrs import stamp_current_user_attributes
from app.services.relations import rebuild_asset_relations, rebuild_asset_relations_with_neighbors
from app.services.visibility import asset_visible_in, visible_assets_clause

router = APIRouter(prefix="/v1/assets", tags=["assets"])

ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "/data/attachments")


@router.get("", response_model=list[AssetOut])
def list_assets(
    schema_uid: Optional[str] = None,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    # This workspace's own objects, and any other workspace's that are flagged
    # global. Being of a global *type* is not enough (see services/visibility).
    stmt = select(Asset).where(visible_assets_clause(workspace_id))
    if schema_uid:
        stmt = stmt.where(Asset.schema_uid == schema_uid)
    return db.scalars(stmt).all()


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(
    body: AssetCreate,
    workspace_id: str = Depends(require_permission("create")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    if db.get(Asset, body.uid) is not None:
        raise HTTPException(status_code=409, detail="Asset uid already exists")
    schema = db.get(Schema, body.schema_uid)
    # A type is usable here if this workspace owns it or it is shared. Without
    # this check a token could attach objects to another workspace's private
    # type (asset-model-revision §4.3).
    if schema is None or (schema.workspace_id != workspace_id and not schema.is_global):
        raise HTTPException(status_code=422, detail="Unknown object type for this workspace")
    stamp_current_user_attributes(db, schema, body.attributes, current_user_id)
    validate_attributes(db, schema, body.attributes, workspace_id, Asset)
    data = body.model_dump()
    # Made in a global workspace, an object is global unless it says otherwise —
    # as its types and documents already are.
    workspace = db.get(Workspace, workspace_id)
    if "is_global" not in body.model_fields_set and workspace is not None and workspace.is_global:
        data["is_global"] = True
    asset = Asset(workspace_id=workspace_id, **data)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def _get_owned_asset(uid: str, workspace_id: str, db: Session) -> Asset:
    """Strict same-workspace lookup — used by every write endpoint. A global
    asset owned by another workspace is visible (see _get_visible_asset) but
    still can't be edited except by its owning workspace."""
    asset = db.get(Asset, uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _get_visible_asset(uid: str, workspace_id: str, db: Session) -> Asset:
    asset = db.get(Asset, uid)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset_visible_in(asset, workspace_id):
        return asset
    raise HTTPException(status_code=404, detail="Asset not found")


@router.get("/{uid}", response_model=AssetOut)
def get_asset(
    uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    asset = _get_visible_asset(uid, workspace_id, db)
    # Keep the denormalized relation cache honest every time an object is
    # actually looked at, independent of whatever else may have changed it
    # (relations are also resynced at the point of change, but this catches
    # anything that slips through, e.g. cross-workspace visibility shifts).
    rebuild_asset_relations(db, uid)
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/{uid}", response_model=AssetOut)
def update_asset(
    uid: str,
    body: AssetUpdate,
    workspace_id: str = Depends(require_permission("modify")),
    current_user_id: Optional[str] = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    asset = _get_owned_asset(uid, workspace_id, db)
    patch = body.model_dump(exclude_unset=True)
    global_changed = "is_global" in patch and patch["is_global"] != asset.is_global
    for field, value in patch.items():
        setattr(asset, field, value)

    schema = db.get(Schema, asset.schema_uid) if asset.schema_uid else None
    stamp_current_user_attributes(db, schema, asset.attributes, current_user_id)
    flag_modified(asset, "attributes")

    if "attributes" in patch or "schema_uid" in patch:
        validate_attributes(db, schema, asset.attributes, workspace_id, Asset, exclude_uid=uid)
    db.commit()
    if global_changed:
        # Cross-workspace visibility just changed — this asset's neighbors
        # may now (or no longer) be able to see it, so their cached relation
        # lists need to reflect that too.
        rebuild_asset_relations_with_neighbors(db, uid)
        db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{uid}", status_code=204)
def delete_asset(
    uid: str, workspace_id: str = Depends(require_permission("delete")), db: Session = Depends(get_db)
):
    asset = _get_owned_asset(uid, workspace_id, db)
    db.delete(asset)
    db.commit()


@router.post("/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_assets(
    body: BulkDeleteRequest,
    workspace_id: str = Depends(require_permission("delete")),
    db: Session = Depends(get_db),
):
    deleted = 0
    missing: list[str] = []
    for uid in body.uids:
        asset = db.get(Asset, uid)
        if asset is None or asset.workspace_id != workspace_id:
            missing.append(uid)
            continue
        db.delete(asset)
        deleted += 1
    db.commit()
    return BulkDeleteResult(deleted=deleted, not_found=missing)


@router.post("/{uid}/avatar", response_model=AssetOut)
async def upload_asset_avatar(
    uid: str,
    file: UploadFile,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    """Upload a picture and make it this object's avatar. The file is stored
    as a normal attachment of the object, so replacing the avatar doesn't
    destroy the previous picture — it simply reappears among the
    attachments, where it can be deleted or promoted back."""
    asset = _get_owned_asset(uid, workspace_id, db)

    attachment_uid = str(uuid.uuid4())
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    storage_path = os.path.join(ATTACHMENTS_DIR, attachment_uid)
    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    db.add(Attachment(
        uid=attachment_uid,
        workspace_id=workspace_id,
        asset_uid=uid,
        filename=file.filename or attachment_uid,
        mime_type=file.content_type,
        file_size=len(contents),
        storage_path=storage_path,
    ))
    asset.avatar_icon_uid = attachment_uid
    db.commit()
    db.refresh(asset)
    return asset


@router.put("/{uid}/avatar/{attachment_uid}", response_model=AssetOut)
def set_asset_avatar_from_attachment(
    uid: str,
    attachment_uid: str,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    """Promote a picture already attached to this object to be its avatar —
    the common case for imported objects, whose pictures arrive as
    attachments."""
    asset = _get_owned_asset(uid, workspace_id, db)
    attachment = db.get(Attachment, attachment_uid)
    if attachment is None or attachment.asset_uid != uid:
        raise HTTPException(status_code=404, detail="Attachment not found on this object")
    asset.avatar_icon_uid = attachment_uid
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/{uid}/avatar", response_model=AssetOut)
def clear_asset_avatar(
    uid: str,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    """Clear the avatar. The picture itself stays as an attachment."""
    asset = _get_owned_asset(uid, workspace_id, db)
    asset.avatar_icon_uid = None
    db.commit()
    db.refresh(asset)
    return asset


relations_router = APIRouter(prefix="/v1/relations", tags=["relations"])


@relations_router.get("", response_model=list[RelationOut])
def list_relations(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    return db.scalars(
        select(Relation).where(Relation.workspace_id == workspace_id)
    ).all()


@relations_router.post("", response_model=RelationOut, status_code=201)
def create_relation(
    body: RelationCreate,
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    # from_asset_uid must belong to the acting workspace (it's what this relation
    # is attached to); to_asset_uid may point at another workspace's asset only if
    # that asset is global.
    _get_owned_asset(body.from_asset_uid, workspace_id, db)
    _get_visible_asset(body.to_asset_uid, workspace_id, db)

    relation = Relation(workspace_id=workspace_id, **body.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)
    rebuild_asset_relations(db, body.from_asset_uid)
    rebuild_asset_relations(db, body.to_asset_uid)
    db.commit()
    return relation


@relations_router.delete("/{relation_id}", status_code=204)
def delete_relation(
    relation_id: int,
    workspace_id: str = Depends(require_permission("delete")),
    db: Session = Depends(get_db),
):
    relation = db.get(Relation, relation_id)
    if relation is None or relation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Relation not found")
    if relation.derivation is not None:
        # Only the ledger writes these (I-PROJ-2): change the source, the
        # installation or the decision behind the edge instead.
        raise HTTPException(status_code=409, detail="This relation is maintained by the fact ledger "
                                                    "and cannot be removed directly")
    from_uid, to_uid = relation.from_asset_uid, relation.to_asset_uid
    db.delete(relation)
    db.commit()
    rebuild_asset_relations(db, from_uid)
    rebuild_asset_relations(db, to_uid)
    db.commit()
