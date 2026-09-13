from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    permissions: dict
    is_system: bool
    rank: int


class RoleBindingCreate(BaseModel):
    subject_type: Literal["user", "group"]
    subject_id: str
    role_id: str


class RoleBindingOut(BaseModel):
    id: int
    workspace_id: str
    subject_type: str
    subject_id: str
    # Resolved for display, so a list of bindings doesn't need a second
    # round trip per row to say who it's about.
    subject_label: str
    subject_active: bool
    role_id: str
    role_name: str
    created_at: Optional[datetime] = None


class EffectivePermissionsOut(BaseModel):
    workspace_id: str
    is_admin: bool
    objects: list[str]
    tickets: list[str]
    documents: list[str]
    workspace: list[str]
