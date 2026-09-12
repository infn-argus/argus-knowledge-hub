from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.asset import Asset
from app.models.asset_subresources import AssetLabel
from app.schemas.asset_subresources import AssetLabelSearchOut

router = APIRouter(prefix="/v1", tags=["labels"])


@router.get("/labels", response_model=list[AssetLabelSearchOut])
def search_labels(
    search: Optional[str] = None,
    type: Optional[str] = None,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    stmt = (
        select(AssetLabel, Asset)
        .join(Asset, AssetLabel.asset_uid == Asset.uid)
        .where(Asset.workspace_id == workspace_id)
    )
    if search:
        stmt = stmt.where(AssetLabel.value.ilike(f"%{search}%"))
    if type:
        stmt = stmt.where(AssetLabel.type == type)

    rows = db.execute(stmt).all()
    return [
        AssetLabelSearchOut(
            uid=label.uid,
            type=label.type,
            value=label.value,
            namespace=label.namespace,
            issuer=label.issuer,
            verified=label.verified,
            asset_uid=asset.uid,
            asset_name=asset.name,
            asset_key=asset.key,
        )
        for label, asset in rows
    ]


@router.delete("/assets/{asset_uid}/labels/{label_uid}", status_code=204)
def delete_label(
    asset_uid: str,
    label_uid: str,
    workspace_id: str = Depends(require_permission("delete")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    label = db.get(AssetLabel, label_uid)
    if label is None or label.asset_uid != asset_uid:
        raise HTTPException(status_code=404, detail="Label not found")

    db.delete(label)
    db.commit()
