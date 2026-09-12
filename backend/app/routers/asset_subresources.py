from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.asset import Asset
from app.models.asset_subresources import (
    AssetComment,
    AssetHistory,
    AssetLabel,
    AssetTicket,
)
from app.schemas.asset_subresources import (
    AssetCommentCreate,
    AssetCommentOut,
    AssetHistoryCreate,
    AssetHistoryOut,
    AssetLabelCreate,
    AssetLabelOut,
    AssetTicketCreate,
    AssetTicketOut,
)

router = APIRouter(prefix="/v1/assets/{asset_uid}", tags=["asset-subresources"])


def _check_asset(asset_uid: str, workspace_id: str, db: Session) -> None:
    asset = db.get(Asset, asset_uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")


def _make_subresource_routes(
    path: str, model, create_schema, out_schema, id_field: str = "uid"
):
    @router.get(f"/{path}", response_model=list[out_schema], name=f"list_{path}")
    def list_items(
        asset_uid: str,
        workspace_id: str = Depends(require_permission("read")),
        db: Session = Depends(get_db),
    ):
        _check_asset(asset_uid, workspace_id, db)
        return db.scalars(select(model).where(model.asset_uid == asset_uid)).all()

    @router.post(f"/{path}", response_model=out_schema, status_code=201, name=f"create_{path}")
    def create_item(
        asset_uid: str,
        body: create_schema,
        workspace_id: str = Depends(require_permission("create")),
        db: Session = Depends(get_db),
    ):
        _check_asset(asset_uid, workspace_id, db)
        item = model(asset_uid=asset_uid, **body.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return item


_make_subresource_routes("tickets", AssetTicket, AssetTicketCreate, AssetTicketOut)
_make_subresource_routes("comments", AssetComment, AssetCommentCreate, AssetCommentOut)
_make_subresource_routes("history", AssetHistory, AssetHistoryCreate, AssetHistoryOut)
_make_subresource_routes("labels", AssetLabel, AssetLabelCreate, AssetLabelOut)
