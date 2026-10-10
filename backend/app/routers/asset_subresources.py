from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_identity, require_permission
from app.db import get_db
from app.models.asset import Asset
from app.models.asset_subresources import (
    AssetComment,
    AssetHistory,
    AssetLabel,
    AssetTicket,
)
from app.services.asset_ticket_links import issue_uid_by_ticket_key
from app.schemas.asset_subresources import (
    AssetCommentCreate,
    AssetCommentOut,
    AssetHistoryCreate,
    AssetHistoryOut,
    AssetLabelCreate,
    AssetLabelOut,
    AssetTicketCreate,
    AssetTicketOut,
)

router = APIRouter(prefix="/v1/assets/{asset_uid}", tags=["asset-subresources"])


def _check_asset(asset_uid: str, workspace_id: str, db: Session) -> None:
    asset = db.get(Asset, asset_uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")


def _reject_duplicate_label(db: Session, workspace_id: str, body) -> None:
    """The Flutter model declares (type, value) unique and the mobile app
    relies on a scan resolving to exactly one object; Postgres never got the
    matching constraint, so a second object could quietly claim the same
    code. Enforced here (per workspace, the boundary the rest of the API
    uses) rather than as a migration, which would fail on any duplicate
    already imported."""
    clash = db.scalars(
        select(AssetLabel)
        .join(Asset, AssetLabel.asset_uid == Asset.uid)
        .where(
            Asset.workspace_id == workspace_id,
            AssetLabel.type == body.type,
            AssetLabel.value == body.value,
        )
    ).first()
    if clash is not None:
        owner = db.get(Asset, clash.asset_uid)
        raise HTTPException(
            status_code=409,
            detail=f"This {body.type} is already used by {owner.name if owner else clash.asset_uid}",
        )


def _make_subresource_routes(
    path: str, model, create_schema, out_schema, id_field: str = "uid", on_create=None,
    with_list: bool = True, after_create=None,
):
    # Tickets have a hand-written listing (it resolves the local ticket for
    # each row), so the generic one must not also claim the path.
    if with_list:
        @router.get(f"/{path}", response_model=list[out_schema], name=f"list_{path}")
        def list_items(
            asset_uid: str,
            workspace_id: str = Depends(require_permission("read")),
            db: Session = Depends(get_db),
        ):
            _check_asset(asset_uid, workspace_id, db)
            return db.scalars(select(model).where(model.asset_uid == asset_uid)).all()

    @router.post(f"/{path}", response_model=out_schema, status_code=201, name=f"create_{path}")
    def create_item(
        asset_uid: str,
        body: create_schema,
        workspace_id: str = Depends(require_permission("create")),
        identity=Depends(get_identity),
        db: Session = Depends(get_db),
    ):
        _check_asset(asset_uid, workspace_id, db)
        if on_create is not None:
            on_create(db, workspace_id, body)
        item = model(asset_uid=asset_uid, **body.model_dump())
        db.add(item)
        if after_create is not None:
            after_create(db, asset_uid, item, identity)
        if model is AssetComment:
            from app.routers.ledger import actor_of
            from app.services import notify
            notify.asset_changed(db, asset_uid, f"comment: {(item.text or '')[:120]}",
                                 actor_of(identity))
        db.commit()
        db.refresh(item)
        return item


@router.get("/tickets", response_model=list[AssetTicketOut], name="list_tickets")
def list_asset_tickets(
    asset_uid: str,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """The object's tickets, each carrying the local ticket it corresponds
    to when there is one — rows created by the asset import name a key from
    the source system, which may since have been imported as a ticket here."""
    _check_asset(asset_uid, workspace_id, db)
    rows = db.scalars(select(AssetTicket).where(AssetTicket.asset_uid == asset_uid)).all()
    by_key = issue_uid_by_ticket_key(db, workspace_id)
    return [
        AssetTicketOut(
            **{c.name: getattr(row, c.name) for c in AssetTicket.__table__.columns},
            issue_uid=by_key.get(row.ticket_key),
        )
        for row in rows
    ]


_make_subresource_routes(
    "tickets", AssetTicket, AssetTicketCreate, AssetTicketOut, with_list=False
)
_make_subresource_routes("comments", AssetComment, AssetCommentCreate, AssetCommentOut)
_make_subresource_routes("history", AssetHistory, AssetHistoryCreate, AssetHistoryOut)
def record_label_change(db: Session, asset_uid: str, label, identity, change: str) -> None:
    """A label put on or taken off a record is a change to that record: it shows in its history and moves
    its "last changed", so a list sorted by change and the cockpit's recent activity show it too."""
    import uuid
    from datetime import datetime, timezone
    from app.routers.ledger import actor_of
    now = datetime.now(timezone.utc)
    db.add(AssetHistory(uid=str(uuid.uuid4()), asset_uid=asset_uid, type="label", author=actor_of(identity),
                        details=f"{change} {label.type} label {label.value}", timestamp=now))
    asset = db.get(Asset, asset_uid)
    if asset is not None:
        asset.updated_at = now
    from app.services import notify
    notify.asset_changed(db, asset_uid, f"{change} {label.type} label {label.value}", actor_of(identity))


_make_subresource_routes(
    "labels", AssetLabel, AssetLabelCreate, AssetLabelOut, on_create=_reject_duplicate_label,
    after_create=lambda db, asset_uid, label, identity: record_label_change(db, asset_uid, label, identity, "Added"),
)
