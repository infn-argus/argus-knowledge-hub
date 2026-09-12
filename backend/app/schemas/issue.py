from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IssueCreate(BaseModel):
    uid: str
    asset_uid: Optional[str] = None
    schema_uid: Optional[str] = None
    attributes: dict = {}
    title: str
    description: Optional[str] = None
    state: str = "new"
    priority: Optional[str] = None
    assignee: Optional[str] = None
    labels: list[str] = []
    due_date: Optional[datetime] = None
    created_by: Optional[str] = None


class IssueUpdate(BaseModel):
    asset_uid: Optional[str] = None
    schema_uid: Optional[str] = None
    attributes: Optional[dict] = None
    title: Optional[str] = None
    description: Optional[str] = None
    state: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    labels: Optional[list[str]] = None
    due_date: Optional[datetime] = None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    asset_uid: Optional[str]
    schema_uid: Optional[str]
    attributes: dict
    title: str
    description: Optional[str]
    state: str
    priority: Optional[str]
    assignee: Optional[str]
    labels: list[str]
    due_date: Optional[datetime]
    closed_at: Optional[datetime]
    created_by: Optional[str]
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]


class IssueCommentCreate(BaseModel):
    uid: str
    author: str
    body: str


class IssueCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    issue_uid: str
    author: str
    body: str
    created_at: datetime
    updated_at: datetime
