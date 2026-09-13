from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    dn: Optional[str] = None
    name: str
    description: Optional[str] = None
    email: Optional[str] = None
    source: str
    active: bool
    member_count: int = 0


class GroupMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str
    name: Optional[str] = None
    username: Optional[str] = None
    active: bool
    source: str


class DirectoryStatusOut(BaseModel):
    provider: str
    is_test_data: bool
    groups: int
    active_groups: int
    users: int
    last_synced_at: Optional[datetime] = None
