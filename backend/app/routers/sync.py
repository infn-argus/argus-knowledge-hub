from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.asset import Asset, Relation
from app.models.issue import Issue
from app.models.schema import Schema
from app.schemas.asset import AssetOut, RelationOut
from app.schemas.issue import IssueOut
from app.schemas.schema import SchemaOut

router = APIRouter(prefix="/v1/sync", tags=["sync"])


@router.get("")
def sync(
    since: datetime = Query(...),
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    schemas = db.scalars(
        select(Schema).where(Schema.workspace_id == workspace_id, Schema.updated_at > since)
    ).all()
    assets = db.scalars(
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.updated_at > since)
    ).all()
    issues = db.scalars(
        select(Issue).where(Issue.workspace_id == workspace_id, Issue.updated_at > since)
    ).all()
    relations = db.scalars(
        select(Relation).where(
            Relation.workspace_id == workspace_id, Relation.created_at > since
        )
    ).all()

    return {
        "schemas": [SchemaOut.model_validate(s).model_dump(mode="json", by_alias=True) for s in schemas],
        "assets": [AssetOut.model_validate(a).model_dump(mode="json") for a in assets],
        "issues": [IssueOut.model_validate(i).model_dump(mode="json") for i in issues],
        "relations": [RelationOut.model_validate(r).model_dump(mode="json") for r in relations],
    }
