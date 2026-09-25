"""The unified knowledge layer's API: context, search and the operations cockpit.

Every endpoint here answers across assets, tickets and documents, so none of
them can use a single `require_permission`: the caller needs read access to
*some* section to be in the workspace, and each section is filled only if they
may read it (services/knowledge_hub.Access).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import OidcIdentity, PatIdentity, get_identity
from app.db import get_db
from app.models.asset import Asset
from app.models.document import Document
from app.models.issue import Issue
from app.services import knowledge_hub as hub
from app.services.permissions import resolve_permission
from app.services.visibility import asset_visible_in, can_see

router = APIRouter(prefix="/v1/hub", tags=["hub"])


class _Scope:
    def __init__(self, workspace_id: str, access: hub.Access, user_id: Optional[str]):
        self.workspace_id = workspace_id
        self.access = access
        self.user_id = user_id


def scope(
    identity=Depends(get_identity),
    db: Session = Depends(get_db),
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
) -> _Scope:
    if isinstance(identity, PatIdentity):
        return _Scope(identity.workspace_id, hub.Access(True, True, True), None)
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="Missing X-Workspace-Id header")
    user = identity.user

    def can(resource: str) -> bool:
        return resolve_permission(db, user, x_workspace_id, "read", resource)

    access = hub.Access(assets=can("objects"), tickets=can("tickets"), documents=can("documents"))
    if not (access.assets or access.tickets or access.documents):
        raise HTTPException(status_code=403, detail="Not permitted")
    user_id = user.id if isinstance(identity, OidcIdentity) else None
    return _Scope(x_workspace_id, access, user_id)


@router.get("/search")
def search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(8, ge=1, le=50),
    s: _Scope = Depends(scope),
    db: Session = Depends(get_db),
):
    return hub.unified_search(db, s.workspace_id, s.access, q, limit)


@router.get("/overview")
def overview(s: _Scope = Depends(scope), db: Session = Depends(get_db)):
    return hub.overview(db, s.workspace_id, s.access, s.user_id)


@router.get("/assets/{uid}/context")
def asset_context(uid: str, s: _Scope = Depends(scope), db: Session = Depends(get_db)):
    if not s.access.assets:
        raise HTTPException(status_code=403, detail="Not permitted")
    asset = db.get(Asset, uid)
    if asset is None or asset.deleted_at is not None or not asset_visible_in(asset, s.workspace_id):
        raise HTTPException(status_code=404, detail="Asset not found")
    return hub.asset_context(db, s.workspace_id, asset, s.access)


@router.get("/tickets/{uid}/context")
def ticket_context(uid: str, s: _Scope = Depends(scope), db: Session = Depends(get_db)):
    if not s.access.tickets:
        raise HTTPException(status_code=403, detail="Not permitted")
    issue = db.get(Issue, uid)
    if issue is None or issue.deleted_at is not None or issue.workspace_id != s.workspace_id or not can_see(issue):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return hub.ticket_context(db, s.workspace_id, issue, s.access)


@router.get("/documents/{uid}/context")
def document_context(uid: str, s: _Scope = Depends(scope), db: Session = Depends(get_db)):
    if not s.access.documents:
        raise HTTPException(status_code=403, detail="Not permitted")
    doc = db.get(Document, uid)
    readable = doc is not None and (
        doc.workspace_id == s.workspace_id
        or (doc.is_global and doc.confidentiality != "riservato")
    )
    if not readable:
        raise HTTPException(status_code=404, detail="Document not found")
    return hub.document_context(db, s.workspace_id, doc, s.access)
