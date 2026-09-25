"""Ticket workflows and notifications (asset-model-revision §19 item 3)."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import OidcIdentity, get_identity, require_permission
from app.db import get_db
from app.models.workflow import Notification, Workflow
from app.services import notify, workflows

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])
notifications_router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


def _fail(exc: Exception):
    raise HTTPException(status_code=422, detail={"error": str(exc)})


@router.get("")
def list_workflows(workspace_id: str = Depends(require_permission("read", resource="tickets")),
                   db: Session = Depends(get_db)):
    rows = [workflows.as_dict(w) for w in db.scalars(select(Workflow).where(Workflow.workspace_id == workspace_id)
                                                      .order_by(Workflow.name))]
    return {"workflows": rows, "builtin": workflows.BUILTIN,
            "default": next((w["uid"] for w in rows if w["is_default"]), None)}


class WorkflowIn(BaseModel):
    name: str
    states: list[dict[str, Any]]
    transitions: list[dict[str, Any]] = []
    initial: str
    is_default: bool = False


@router.post("", status_code=201)
def create_workflow(body: WorkflowIn, workspace_id: str = Depends(require_permission("approve", resource="tickets")),
                    db: Session = Depends(get_db)):
    try:
        wf = workflows.save(db, workspace_id, body.model_dump())
    except workflows.WorkflowError as exc:
        _fail(exc)
    db.commit()
    return workflows.as_dict(wf)


@router.put("/{uid}")
def update_workflow(uid: str, body: WorkflowIn,
                    workspace_id: str = Depends(require_permission("approve", resource="tickets")),
                    db: Session = Depends(get_db)):
    if db.get(Workflow, uid) is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    try:
        wf = workflows.save(db, workspace_id, body.model_dump(), uid)
    except workflows.WorkflowError as exc:
        _fail(exc)
    db.commit()
    return workflows.as_dict(wf)


class JiraWorkflowIn(BaseModel):
    definition: dict[str, Any]
    is_default: bool = False


@router.post("/import-jira", status_code=201)
def import_jira_workflow(body: JiraWorkflowIn,
                         workspace_id: str = Depends(require_permission("approve", resource="tickets")),
                         db: Session = Depends(get_db)):
    """A Jira workflow, as it is: its statuses (with their category) and its
    transitions. The status map it records is what the rehearsal uses."""
    try:
        wf = workflows.save(db, workspace_id, {**workflows.from_jira(body.definition), "is_default": body.is_default})
    except (workflows.WorkflowError, KeyError) as exc:
        _fail(exc)
    db.commit()
    return workflows.as_dict(wf)


class BindIn(BaseModel):
    schema_uid: str


@router.post("/{uid}/bind")
def bind_workflow(uid: str, body: BindIn, workspace_id: str = Depends(require_permission("approve", resource="tickets")),
                  db: Session = Depends(get_db)):
    try:
        workflows.bind(db, workspace_id, body.schema_uid, uid)
    except workflows.WorkflowError as exc:
        _fail(exc)
    db.commit()
    return {"ok": True}


@router.get("/{uid}/rehearsal")
def rehearse(uid: str, workspace_id: str = Depends(require_permission("read", resource="tickets")),
             db: Session = Depends(get_db)):
    """Replay the migrated tickets' Jira status history against this workflow."""
    wf = db.get(Workflow, uid)
    if wf is None or wf.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflows.rehearse(db, wf, workspace_id)


@router.post("/escalate")
def escalate(workspace_id: str = Depends(require_permission("approve", resource="tickets")),
             db: Session = Depends(get_db)):
    """Run the escalation timers now (normally `python -m app.ledger escalate`)."""
    n = notify.escalate_overdue(db, workspace_id=workspace_id)
    db.commit()
    return {"escalated": n}


# --------------------------------------------------------------------------- notifications

def _me(db: Session, identity, recipient: Optional[str]) -> list[str]:
    if isinstance(identity, OidcIdentity):
        return [x for x in (identity.user.id, identity.user.email) if x]
    if not recipient:
        raise HTTPException(status_code=422, detail="an API token names the recipient (?recipient=)")
    return [recipient]


@notifications_router.get("")
def my_notifications(unread: bool = False, recipient: Optional[str] = Query(None), identity=Depends(get_identity),
                     workspace_id: str = Depends(require_permission("read", resource="tickets")),
                     db: Session = Depends(get_db)):
    q = select(Notification).where(Notification.workspace_id == workspace_id,
                                   Notification.recipient.in_(_me(db, identity, recipient)))
    if unread:
        q = q.where(Notification.read_at.is_(None))
    rows = list(db.scalars(q.order_by(Notification.id.desc()).limit(100)))
    return [{"id": n.id, "kind": n.kind, "title": n.title, "issue_uid": n.issue_uid, "detail": n.detail,
             "actor": n.actor, "created_at": n.created_at, "read": n.read_at is not None} for n in rows]


@notifications_router.post("/{nid}/read")
def mark_read(nid: int, recipient: Optional[str] = Query(None), identity=Depends(get_identity),
              workspace_id: str = Depends(require_permission("read", resource="tickets")),
              db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.workspace_id != workspace_id or n.recipient not in _me(db, identity, recipient):
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read_at = n.read_at or notify.now()
    db.commit()
    return {"ok": True}


@notifications_router.post("/read-all")
def mark_all_read(recipient: Optional[str] = Query(None), identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("read", resource="tickets")),
                  db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.workspace_id == workspace_id,
                                                   Notification.recipient.in_(_me(db, identity, recipient)),
                                                   Notification.read_at.is_(None))):
        n.read_at = notify.now()
    db.commit()
    return {"ok": True}
