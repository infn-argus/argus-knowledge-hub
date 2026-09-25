"""Equipment readiness and controlled bulk changes (asset-model-revision §19
items 5 and 7)."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_identity, require_permission
from app.db import get_db
from app.ledger import bulk, equipment
from app.ledger.engine import LedgerError
from app.models.asset import Asset
from app.models.ledger import BulkChange
from app.routers.ledger import _fail, _readable_workspaces, actor_of
from app.services.visibility import asset_visible_in

router = APIRouter(prefix="/v1/equipment", tags=["equipment"])
bulk_router = APIRouter(prefix="/v1/bulk-changes", tags=["bulk changes"])


def _record(db: Session, uid: str, workspace_id: str) -> Asset:
    record = db.get(Asset, uid)
    if record is None or not asset_visible_in(record, workspace_id):
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.get("/{uid}")
def equipment_state(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Lifecycle, custody and location with their history."""
    record = _record(db, uid, workspace_id)
    lc = equipment.lifecycle(db, record)
    return {"lifecycle": {**lc, "installation": {k: v for k, v in (lc["installation"] or {}).items()
                                                 if k != "interval"} or None},
            "states": equipment.LIFECYCLE, "custody": equipment.value_history(db, uid, "custodian"),
            "location": equipment.value_history(db, uid, "argus_location"),
            "lifecycle_history": equipment.value_history(db, uid, "argus_lifecycle"),
            "designated_spare": bool((record.attributes or {}).get("is_designated_spare"))}


class LifecycleIn(BaseModel):
    state: str
    reason: Optional[str] = None


@router.post("/{uid}/lifecycle")
def set_lifecycle(uid: str, body: LifecycleIn, identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    try:
        result = equipment.set_lifecycle(db, workspace_id, actor_of(identity), uid, body.state, body.reason)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return {k: v for k, v in result.items() if k != "installation"}


class CustodyIn(BaseModel):
    custodian: str
    reason: Optional[str] = None


@router.post("/{uid}/custody")
def set_custody(uid: str, body: CustodyIn, identity=Depends(get_identity),
                workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    try:
        equipment.set_custodian(db, workspace_id, actor_of(identity), uid, body.custodian, body.reason)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return equipment.value_history(db, uid, "custodian")


@router.get("/spares/available")
def list_spares(product_model: Optional[str] = None, type: Optional[str] = None, identity=Depends(get_identity),
                workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return equipment.spares(db, _readable_workspaces(db, identity), product_model=product_model, type_name=type)


@router.get("/positions/{uid}/spares")
def position_spares(uid: str, identity=Depends(get_identity),
                    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    _record(db, uid, workspace_id)
    return equipment.spares_for_position(db, uid, _readable_workspaces(db, identity))


# --------------------------------------------------------------------------- bulk changes

class BulkIn(BaseModel):
    spec: dict[str, Any]
    description: Optional[str] = None


@bulk_router.post("", status_code=201)
def preview_bulk(body: BulkIn, identity=Depends(get_identity),
                 workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    """A dry run: shows every record's before and after; writes no decision."""
    try:
        change = bulk.preview(db, workspace_id, actor_of(identity), body.spec, body.description)
    except (LedgerError, KeyError) as exc:
        _fail(db, exc)
    db.commit()
    return bulk.view(change)


@bulk_router.get("")
def list_bulk(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return [bulk.view(c, rows=0) for c in db.scalars(select(BulkChange).where(BulkChange.workspace_id == workspace_id)
                                                     .order_by(BulkChange.created_at.desc()).limit(100))]


@bulk_router.get("/{change_id}")
def get_bulk(change_id: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    change = db.get(BulkChange, change_id)
    if change is None or change.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Bulk change not found")
    return bulk.view(change, rows=1000)


def _step(fn, change_id: str, identity, workspace_id: str, db: Session):
    try:
        change = fn(db, workspace_id, change_id, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return bulk.view(change)


@bulk_router.post("/{change_id}/apply")
def apply_bulk(change_id: str, identity=Depends(get_identity),
               workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    return _step(bulk.apply, change_id, identity, workspace_id, db)


@bulk_router.post("/{change_id}/approve")
def approve_bulk(change_id: str, identity=Depends(get_identity),
                 workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    return _step(bulk.approve, change_id, identity, workspace_id, db)


@bulk_router.post("/{change_id}/undo")
def undo_bulk(change_id: str, identity=Depends(get_identity),
              workspace_id: str = Depends(require_permission("modify")), db: Session = Depends(get_db)):
    return _step(bulk.undo, change_id, identity, workspace_id, db)
