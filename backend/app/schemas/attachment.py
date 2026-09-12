from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    asset_uid: Optional[str]
    filename: str
    mime_type: Optional[str]
    file_size: Optional[int]
    author: Optional[str]
    backend_id: Optional[str] = None
    backend_url: Optional[str] = None
    created_at: datetime
