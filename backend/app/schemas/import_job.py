from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

MergeStrategy = Literal["override", "no_override", "update_if_newer", "remove_all_before"]


class JiraImportRequest(BaseModel):
    source: Literal["jira"]
    base_url: str
    pat: str
    jira_schema_id: str
    merge_strategy: MergeStrategy = "override"


class GitImportRequest(BaseModel):
    source: Literal["git"]
    provider: Literal["github", "gitlab"]
    repo_url: str
    pat: str
    branch: str = "main"
    merge_strategy: MergeStrategy = "override"


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    source: str
    status: str
    progress: Optional[str]
    counts: dict
    warnings: list[str]
    error: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
