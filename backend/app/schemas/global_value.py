from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GlobalValueCreate(BaseModel):
    uid: str
    name: str
    key: str
    type: str
    applies_to: str = "objects"
    options: Optional[list] = None
    default_value: Optional[str] = None
    constraints: Optional[dict] = None
    required: bool = False
    unique: bool = False
    indexed: bool = False
    multi_value: bool = False
    min_cardinality: Optional[int] = None
    max_cardinality: Optional[int] = None
    reference_type: Optional[str] = None
    egu: Optional[str] = None
    allowed_egu_list: Optional[list[str]] = None
    read_only: bool = False
    visible: bool = True
    enabled: bool = True
    is_system_default: bool = False


class GlobalValueUpdate(BaseModel):
    name: Optional[str] = None
    key: Optional[str] = None
    type: Optional[str] = None
    applies_to: Optional[str] = None
    options: Optional[list] = None
    default_value: Optional[str] = None
    constraints: Optional[dict] = None
    required: Optional[bool] = None
    unique: Optional[bool] = None
    indexed: Optional[bool] = None
    multi_value: Optional[bool] = None
    min_cardinality: Optional[int] = None
    max_cardinality: Optional[int] = None
    reference_type: Optional[str] = None
    egu: Optional[str] = None
    allowed_egu_list: Optional[list[str]] = None
    read_only: Optional[bool] = None
    visible: Optional[bool] = None
    enabled: Optional[bool] = None
    is_system_default: Optional[bool] = None


class GlobalValueOut(GlobalValueCreate):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: str
    created_at: datetime
    updated_at: datetime
