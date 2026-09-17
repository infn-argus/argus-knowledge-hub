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
    # True: also pull in every descendant of each selected type (and, if
    # include_instances is set, their instances too). Ancestors are always
    # included regardless of this flag — a child type needs its parent.
    include_descendant_types: bool = False
    asset_uids: list[str] = []
    document_uids: list[str] = []
    issue_uids: list[str] = []
    # Copy only: when a type already exists at the same level in the target
    # workspace, merge into it (and match instances by key/code) instead of
    # refusing. Move never merges, regardless of this flag.
    force: bool = False


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
