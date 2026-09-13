import uuid
from typing import Annotated, Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.import_job import ImportJob
from app.schemas.import_job import (
    GitImportRequest,
    ImportJobOut,
    JiraImportRequest,
    JiraIssueImportRequest,
    ConfluenceImportRequest,
)
from app.services.git_import import run_git_import
from app.services.jira_import import run_jira_import
from app.services.jira_issue_import import run_jira_issue_import
from app.services.confluence_import import run_confluence_import

router = APIRouter(prefix="/v1/imports", tags=["imports"])

ImportRequest = Annotated[
    Union[
        JiraImportRequest, JiraIssueImportRequest, ConfluenceImportRequest, GitImportRequest
    ],
    Field(discriminator="source"),
]


@router.get("", response_model=list[ImportJobOut])
def list_imports(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    stmt = (
        select(ImportJob)
        .where(ImportJob.workspace_id == workspace_id)
        .order_by(ImportJob.created_at.desc())
    )
    return db.scalars(stmt).all()


@router.get("/{uid}", response_model=ImportJobOut)
def get_import(
    uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    job = db.get(ImportJob, uid)
    if job is None or job.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Import job not found")
    return job


@router.post("", response_model=ImportJobOut, status_code=201)
def create_import(
    body: ImportRequest,
    background_tasks: BackgroundTasks,
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    job = ImportJob(uid=str(uuid.uuid4()), workspace_id=workspace_id, source=body.source)
    db.add(job)
    db.commit()

    if isinstance(body, JiraImportRequest):
        background_tasks.add_task(
            run_jira_import,
            job.uid, workspace_id, body.base_url, body.pat, body.jira_schema_id, body.merge_strategy,
        )
    elif isinstance(body, JiraIssueImportRequest):
        background_tasks.add_task(
            run_jira_issue_import,
            job.uid, workspace_id, body.base_url, body.pat, body.jql, body.merge_strategy,
            body.schema_uid, body.link_assets,
        )
    elif isinstance(body, ConfluenceImportRequest):
        background_tasks.add_task(
            run_confluence_import,
            job.uid, workspace_id, body.base_url, body.pat, body.space_key, body.cql,
            body.merge_strategy, body.link_assets,
        )
    else:
        background_tasks.add_task(
            run_git_import,
            job.uid, workspace_id, body.provider, body.repo_url, body.pat, body.branch, body.merge_strategy,
        )

    db.refresh(job)
    return job
