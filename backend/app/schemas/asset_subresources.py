from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AssetTicketCreate(BaseModel):
    uid: str
    ticket_key: str
    summary: str
    type: str
    status: str
    created: datetime
    updated: datetime
    backend_id: Optional[str] = None
    backend_url: Optional[str] = None


class AssetTicketOut(AssetTicketCreate):
    model_config = ConfigDict(from_attributes=True)

    asset_uid: str


class AssetCommentCreate(BaseModel):
    uid: str
    author: str
    text: str
    created: datetime
    updated: datetime
    backend_id: Optional[str] = None
    backend_url: Optional[str] = None


class AssetCommentOut(AssetCommentCreate):
    model_config = ConfigDict(from_attributes=True)

    asset_uid: str


class AssetHistoryCreate(BaseModel):
    uid: str
    type: str
    author: str
    details: str
    timestamp: datetime
    backend_id: Optional[str] = None


class AssetHistoryOut(AssetHistoryCreate):
    model_config = ConfigDict(from_attributes=True)

    asset_uid: str


class AssetLabelCreate(BaseModel):
    uid: str
    type: str
    value: str
    namespace: Optional[str] = None
    issuer: str
    verified: bool = False
    confidence: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    metadata_json: Optional[dict] = None


class AssetLabelOut(AssetLabelCreate):
    model_config = ConfigDict(from_attributes=True)

    asset_uid: str


class AssetLabelSearchOut(BaseModel):
    uid: str
    type: str
    value: str
    namespace: Optional[str] = None
    issuer: str
    verified: bool
    asset_uid: str
    asset_name: str
    asset_key: str
