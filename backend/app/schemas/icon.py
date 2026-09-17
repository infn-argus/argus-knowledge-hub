from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IconUpdate(BaseModel):
    name: Optional[str] = None
    is_global: Optional[bool] = None


class IconOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    name: str
    filename: str
    mime_type: Optional[str]
    file_size: Optional[int]
    is_global: bool
    created_at: datetime
    updated_at: datetime
