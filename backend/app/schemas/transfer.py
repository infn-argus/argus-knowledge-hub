from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

TransferMode = Literal["copy", "move"]


class TransferRequest(BaseModel):
    target_workspace_id: str
    mode: TransferMode
    # Schema (type) uids to transfer — covers asset types, ticket types and
    # document types alike, since all three are just Schema rows.
    type_uids: list[str] = []
    # False: transfer the selected types only, none of their instances.
    include_instances: bool = True
    asset_uids: list[str] = []
    document_uids: list[str] = []
    issue_uids: list[str] = []


class TransferJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    target_workspace_id: str
    mode: str
    status: str
    progress: Optional[str]
    counts: dict
    warnings: list[str]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
