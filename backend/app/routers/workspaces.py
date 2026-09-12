import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import Identity, PatIdentity, get_identity, require_permission
from app.db import get_db
from app.models.global_value import GlobalValue
from app.models.membership import Membership
from app.models.schema import Schema
from app.models.user import User
from app.models.workspace import Workspace
from app.services.integrity import cleanup_workspace, generate_integrity_report, relink_workspace
from app.services.relations import rebuild_relations_for_schemas
from app.schemas.workspace import (
    CleanupOptions,
    DefaultAccess,
    MemberDirectoryOut,
    MembershipOut,
    MembershipUpdate,
    MeOut,
    MyWorkspaceOut,
    UserAdminUpdate,
    UserOut,
    WorkspaceCreate,
    WorkspaceDetailOut,
    WorkspaceOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/v1", tags=["workspaces"])


def seed_default_global_values(db: Session, workspace_id: str) -> None:
    """Seed the starter set of shared enumerations for a new workspace.
    Idempotent: skips any (applies_to, key) that already exists, so this can
    also be run as a one-off backfill against existing workspaces."""
    existing = {
        (gv.applies_to, gv.key)
        for gv in db.scalars(
            select(GlobalValue).where(GlobalValue.workspace_id == workspace_id)
        )
    }

    def _add(applies_to: str, key: str, name: str, options: list, default_value: str | None = None):
        if (applies_to, key) in existing:
            return
        db.add(GlobalValue(
            uid=str(uuid.uuid4()), workspace_id=workspace_id, key=key, name=name,
            type="enumeration", applies_to=applies_to, is_system_default=True,
            default_value=default_value, options=options,
        ))

    # Optional per type (a schema opts in via a reference/global attribute),
    # never forced. Matches the Flutter app's own default set; a later Jira
    # import may overwrite its options with the source system's real
    # statuses (same key, upsert-by-key there).
    _add("objects", "status", "Status", default_value="uninstalled", options=[
        {"id": "active", "value": "Active"},
        {"id": "action_needed", "value": "Action Needed"},
        {"id": "broken", "value": "Broken"},
        {"id": "not_active", "value": "Not Active"},
        {"id": "ok", "value": "Ok"},
        {"id": "uninstalled", "value": "Uninstalled"},
    ])
    _add("tickets", "priority", "Priority", options=[
        {"id": "low", "value": "Low"},
        {"id": "medium", "value": "Medium"},
        {"id": "high", "value": "High"},
        {"id": "blocker", "value": "Blocker"},
        {"id": "critical", "value": "Critical"},
    ])
    _add("tickets", "status", "Status", default_value="new", options=[
        {"id": "new", "value": "New", "responsible": "Help Desk (Queue)",
         "meaning": "Created and waiting to be picked up."},
        {"id": "in_progress", "value": "In Progress", "responsible": "Assigned Technician",
         "meaning": "Actively being analyzed or fixed."},
        {"id": "pending", "value": "Pending", "responsible": "External Party (User/Vendor)",
         "meaning": "Paused, waiting for an external action."},
        {"id": "resolved", "value": "Resolved", "responsible": "User (for verification)",
         "meaning": "The solution has been applied."},
        {"id": "closed", "value": "Closed", "responsible": "None (Archived)",
         "meaning": "Successfully resolved and locked."},
    ])


def _require_owner_or_admin(workspace_id: str, identity: Identity, db: Session) -> None:
    """Membership management requires full rights on the target workspace, or is_admin."""
    if isinstance(identity, PatIdentity):
        if identity.workspace_id != workspace_id:
            raise HTTPException(status_code=403, detail="Not permitted")
        return
    if identity.user.is_admin:
        return
    membership = db.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == identity.user.id
        )
    )
    if membership is None or not (
        membership.can_create and membership.can_modify and membership.can_delete
    ):
        raise HTTPException(status_code=403, detail="Not permitted")


@router.get("/me", response_model=MeOut)
def get_me(identity: Identity = Depends(get_identity)):
    if isinstance(identity, PatIdentity):
        return MeOut(auth_type="pat", workspace_id=identity.workspace_id)
    user = identity.user
    return MeOut(
        auth_type="oidc", user_id=user.id, email=user.email, name=user.name, is_admin=user.is_admin
    )


@router.get("/me/workspaces", response_model=list[MyWorkspaceOut])
def list_my_workspaces(identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    if isinstance(identity, PatIdentity):
        ws = db.get(Workspace, identity.workspace_id)
        if ws is None:
            return []
        return [MyWorkspaceOut(
            id=ws.id, name=ws.name, is_global=ws.is_global, created_at=ws.created_at,
            can_read=True, can_create=True, can_modify=True, can_delete=True,
            can_read_tickets=True, can_create_tickets=True,
            can_modify_tickets=True, can_delete_tickets=True,
            can_read_documents=True, can_create_documents=True,
            can_modify_documents=True, can_delete_documents=True, can_approve_documents=True,
        )]

    user = identity.user
    if user.is_admin:
        return [
            MyWorkspaceOut(
                id=ws.id, name=ws.name, is_global=ws.is_global, created_at=ws.created_at,
                can_read=True, can_create=True, can_modify=True, can_delete=True,
                can_read_tickets=True, can_create_tickets=True,
                can_modify_tickets=True, can_delete_tickets=True,
                can_read_documents=True, can_create_documents=True,
                can_modify_documents=True, can_delete_documents=True, can_approve_documents=True,
            )
            for ws in db.scalars(select(Workspace)).all()
        ]

    rows = db.execute(
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user.id)
    ).all()
    result = [
        MyWorkspaceOut(
            id=ws.id, name=ws.name, is_global=ws.is_global, created_at=ws.created_at,
            can_read=m.can_read, can_create=m.can_create,
            can_modify=m.can_modify, can_delete=m.can_delete,
            can_read_tickets=m.can_read_tickets, can_create_tickets=m.can_create_tickets,
            can_modify_tickets=m.can_modify_tickets, can_delete_tickets=m.can_delete_tickets,
            can_read_documents=m.can_read_documents, can_create_documents=m.can_create_documents,
            can_modify_documents=m.can_modify_documents, can_delete_documents=m.can_delete_documents,
            can_approve_documents=m.can_approve_documents,
        )
        for m, ws in rows
    ]

    # Also surface workspaces with no explicit membership but where the
    # workspace's default access grants this authenticated user something —
    # otherwise that default access would be enforced but unreachable, since
    # the user would have no way to pick the workspace in the first place.
    member_ws_ids = {ws.id for _, ws in rows}
    default_accessible = db.scalars(
        select(Workspace).where(
            Workspace.id.not_in(member_ws_ids) if member_ws_ids else True,
            (
                Workspace.default_can_read | Workspace.default_can_create
                | Workspace.default_can_modify | Workspace.default_can_delete
                | Workspace.default_can_read_tickets | Workspace.default_can_create_tickets
                | Workspace.default_can_modify_tickets | Workspace.default_can_delete_tickets
                | Workspace.default_can_read_documents | Workspace.default_can_create_documents
                | Workspace.default_can_modify_documents | Workspace.default_can_delete_documents
                | Workspace.default_can_approve_documents
            ),
        )
    ).all()
    result.extend(
        MyWorkspaceOut(
            id=ws.id, name=ws.name, is_global=ws.is_global, created_at=ws.created_at,
            can_read=ws.default_can_read, can_create=ws.default_can_create,
            can_modify=ws.default_can_modify, can_delete=ws.default_can_delete,
            can_read_tickets=ws.default_can_read_tickets,
            can_create_tickets=ws.default_can_create_tickets,
            can_modify_tickets=ws.default_can_modify_tickets,
            can_delete_tickets=ws.default_can_delete_tickets,
            can_read_documents=ws.default_can_read_documents,
            can_create_documents=ws.default_can_create_documents,
            can_modify_documents=ws.default_can_modify_documents,
            can_delete_documents=ws.default_can_delete_documents,
            can_approve_documents=ws.default_can_approve_documents,
        )
        for ws in default_accessible
    )
    return result


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    body: WorkspaceCreate, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    if isinstance(identity, PatIdentity) or not identity.user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create workspaces")
    if db.get(Workspace, body.id) is not None:
        raise HTTPException(status_code=409, detail="Workspace id already exists")

    workspace = Workspace(id=body.id, name=body.name)
    db.add(workspace)
    db.flush()
    db.add(Membership(
        workspace_id=workspace.id, user_id=identity.user.id,
        can_read=True, can_create=True, can_modify=True, can_delete=True,
        can_read_tickets=True, can_create_tickets=True,
        can_modify_tickets=True, can_delete_tickets=True,
        can_read_documents=True, can_create_documents=True,
        can_modify_documents=True, can_delete_documents=True, can_approve_documents=True,
    ))
    seed_default_global_values(db, workspace.id)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceDetailOut)
def get_workspace(
    workspace_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    _require_owner_or_admin(workspace_id, identity, db)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _require_admin(identity)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    turning_global = body.is_global is True and not workspace.is_global
    if body.name is not None:
        workspace.name = body.name
    if body.is_global is not None:
        workspace.is_global = body.is_global
    db.commit()
    db.refresh(workspace)

    if turning_global:
        schema_uids = list(
            db.scalars(select(Schema.uid).where(Schema.workspace_id == workspace_id))
        )
        db.query(Schema).filter(Schema.workspace_id == workspace_id).update(
            {Schema.is_global: True}, synchronize_session=False
        )
        db.commit()
        rebuild_relations_for_schemas(db, schema_uids)
        db.commit()

    return workspace


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(
    workspace_id: str,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    """Admin-only: permanently deletes the workspace and, via ON DELETE
    CASCADE, everything scoped to it — schemas, assets, tickets, labels,
    global values, import history, memberships and PATs."""
    _require_admin(identity)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    db.delete(workspace)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Could not delete this workspace — it is still referenced elsewhere"
        )


@router.get("/workspaces/{workspace_id}/integrity-report")
def get_integrity_report(
    workspace_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    _require_owner_or_admin(workspace_id, identity, db)
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return generate_integrity_report(db, workspace_id)


@router.post("/workspaces/{workspace_id}/relink")
def relink_workspace_endpoint(
    workspace_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    _require_owner_or_admin(workspace_id, identity, db)
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    relink_result = relink_workspace(db, workspace_id)
    return {"relink": relink_result, "report": generate_integrity_report(db, workspace_id)}


@router.post("/workspaces/{workspace_id}/cleanup")
def cleanup_workspace_endpoint(
    workspace_id: str,
    body: CleanupOptions,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _require_owner_or_admin(workspace_id, identity, db)
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    cleanup_result = cleanup_workspace(db, workspace_id, body.model_dump())
    return {"cleanup": cleanup_result, "report": generate_integrity_report(db, workspace_id)}


@router.put("/workspaces/{workspace_id}/default-access", response_model=WorkspaceDetailOut)
def set_default_access(
    workspace_id: str,
    body: DefaultAccess,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _require_owner_or_admin(workspace_id, identity, db)
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    for field, value in body.model_dump().items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/members", response_model=list[MemberDirectoryOut])
def list_member_directory(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    """Lightweight member lookup for "user"-type attribute pickers (assignee,
    etc.) — available to anyone with read access, unlike the full permissions
    listing below which is owner/admin-only."""
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
    ).all()
    return [MemberDirectoryOut(user_id=u.id, email=u.email, name=u.name) for _, u in rows]


@router.get("/workspaces/{workspace_id}/members", response_model=list[MembershipOut])
def list_members(
    workspace_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    _require_owner_or_admin(workspace_id, identity, db)
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
    ).all()
    return [
        MembershipOut(
            user_id=u.id, email=u.email, name=u.name,
            can_read=m.can_read, can_create=m.can_create,
            can_modify=m.can_modify, can_delete=m.can_delete,
            can_read_tickets=m.can_read_tickets, can_create_tickets=m.can_create_tickets,
            can_modify_tickets=m.can_modify_tickets, can_delete_tickets=m.can_delete_tickets,
            can_read_documents=m.can_read_documents, can_create_documents=m.can_create_documents,
            can_modify_documents=m.can_modify_documents, can_delete_documents=m.can_delete_documents,
            can_approve_documents=m.can_approve_documents,
        )
        for m, u in rows
    ]


@router.put("/workspaces/{workspace_id}/members", response_model=MembershipOut)
def upsert_member(
    workspace_id: str,
    body: MembershipUpdate,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _require_owner_or_admin(workspace_id, identity, db)
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    target = db.scalar(select(User).where(User.email == body.email))
    if target is None:
        raise HTTPException(
            status_code=404,
            detail="No user found with that email — they must sign in at least once first",
        )

    membership = db.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == target.id
        )
    ) or Membership(workspace_id=workspace_id, user_id=target.id)
    membership.can_read = body.can_read
    membership.can_create = body.can_create
    membership.can_modify = body.can_modify
    membership.can_delete = body.can_delete
    membership.can_read_tickets = body.can_read_tickets
    membership.can_create_tickets = body.can_create_tickets
    membership.can_modify_tickets = body.can_modify_tickets
    membership.can_delete_tickets = body.can_delete_tickets
    membership.can_read_documents = body.can_read_documents
    membership.can_create_documents = body.can_create_documents
    membership.can_modify_documents = body.can_modify_documents
    membership.can_delete_documents = body.can_delete_documents
    membership.can_approve_documents = body.can_approve_documents
    db.add(membership)
    db.commit()

    return MembershipOut(
        user_id=target.id, email=target.email, name=target.name,
        can_read=membership.can_read, can_create=membership.can_create,
        can_modify=membership.can_modify, can_delete=membership.can_delete,
        can_read_tickets=membership.can_read_tickets,
        can_create_tickets=membership.can_create_tickets,
        can_modify_tickets=membership.can_modify_tickets,
        can_delete_tickets=membership.can_delete_tickets,
        can_read_documents=membership.can_read_documents,
        can_create_documents=membership.can_create_documents,
        can_modify_documents=membership.can_modify_documents,
        can_delete_documents=membership.can_delete_documents,
        can_approve_documents=membership.can_approve_documents,
    )


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
def remove_member(
    workspace_id: str,
    user_id: str,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _require_owner_or_admin(workspace_id, identity, db)
    membership = db.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == user_id
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(membership)
    db.commit()


def _require_admin(identity: Identity) -> None:
    if isinstance(identity, PatIdentity) or not identity.user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")


@router.get("/admin/users", response_model=list[UserOut])
def list_users(identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    _require_admin(identity)
    return db.scalars(select(User).order_by(User.email)).all()


@router.put("/admin/users/{user_id}", response_model=UserOut)
def set_user_admin(
    user_id: str,
    body: UserAdminUpdate,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    _require_admin(identity)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_admin = body.is_admin
    db.commit()
    db.refresh(target)
    return target
