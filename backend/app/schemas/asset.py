from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AssetCreate(BaseModel):
    uid: str
    schema_uid: str
    key: str
    name: str
    type: str
    avatar_icon_uid: Optional[str] = None
    attributes: dict = {}
    inbound_relations: list[str] = []
    outbound_relations: list[str] = []
    is_global: bool = False


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    avatar_icon_uid: Optional[str] = None
    attributes: Optional[dict] = None
    inbound_relations: Optional[list[str]] = None
    outbound_relations: Optional[list[str]] = None
    deleted_at: Optional[datetime] = None
    is_global: Optional[bool] = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    schema_uid: str
    key: str
    name: str
    type: str
    avatar_icon_uid: Optional[str]
    attributes: dict
    inbound_relations: list[str]
    outbound_relations: list[str]
    is_global: bool
    # Provisional, Active, Retired or Merged: projected by the fact ledger.
    record_status: str = "Active"
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class BulkDeleteRequest(BaseModel):
    uids: list[str]


class BulkDeleteResult(BaseModel):
    deleted: int
    not_found: list[str]


class RelationCreate(BaseModel):
    from_asset_uid: str
    to_asset_uid: str
    relation_type: str


class RelationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: str
    from_asset_uid: str
    to_asset_uid: str
    relation_type: str
    created_at: datetime
    # None for hand-made and legacy edges; "ledger" or "derived" for edges the
    # fact ledger maintains, which are not edited directly.
    derivation: Optional[str] = None
