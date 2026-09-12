from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.import_job import MergeStrategy
from app.services.import_merge import MERGE_STRATEGIES


class JiraImportConfigParams(BaseModel):
    source: Literal["jira"]
    base_url: str
    jira_schema_id: str
    pat: Optional[str] = None  # omit on update to keep the stored secret


class GitImportConfigParams(BaseModel):
    source: Literal["git"]
    provider: Literal["github", "gitlab"]
    repo_url: str
    branch: str = "main"
    pat: Optional[str] = None  # omit on update to keep the stored secret


ImportConfigParams = Union[JiraImportConfigParams, GitImportConfigParams]


class ImportConfigCreate(BaseModel):
    name: str
    merge_strategy: MergeStrategy = "override"
    config: ImportConfigParams = Field(discriminator="source")


class ImportConfigUpdate(BaseModel):
    name: Optional[str] = None
    merge_strategy: Optional[MergeStrategy] = None
    config: Optional[ImportConfigParams] = Field(default=None, discriminator="source")


class ImportConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str
    workspace_id: str
    name: str
    source: str
    merge_strategy: str
    params: dict
    last_run_at: Optional[datetime]
    last_import_job_uid: Optional[str]
    created_at: datetime
    updated_at: datetime


assert set(MergeStrategy.__args__) == set(MERGE_STRATEGIES)
