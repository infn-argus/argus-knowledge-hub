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


class JiraIssueImportRequest(BaseModel):
    """Import from a Jira issue tracker (work), as opposed to Insight
    objects (equipment) — a different API and a different destination."""

    source: Literal["jira-issues"]
    base_url: str
    pat: str
    # Any JQL the account can run; a project filter is the usual case.
    jql: str
    # Optional ticket type, giving the imported tickets configurable
    # attributes the same way object types do.
    schema_uid: Optional[str] = None
    # Link a ticket to any asset whose key it mentions.
    link_assets: bool = True
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
