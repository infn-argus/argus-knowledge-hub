from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.global_value import GlobalValue
from app.schemas.global_value import GlobalValueCreate, GlobalValueOut, GlobalValueUpdate

router = APIRouter(prefix="/v1/global-values", tags=["global-values"])


def _get_owned(uid: str, workspace_id: str, db: Session) -> GlobalValue:
    gv = db.get(GlobalValue, uid)
    if gv is None or gv.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Global value not found")
    return gv


@router.get("", response_model=list[GlobalValueOut])
def list_global_values(
    applies_to: Optional[str] = None,
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    stmt = select(GlobalValue).where(GlobalValue.workspace_id == workspace_id)
    if applies_to:
        stmt = stmt.where(GlobalValue.applies_to == applies_to)
    return db.scalars(stmt).all()


@router.post("", response_model=GlobalValueOut, status_code=201)
def create_global_value(
    body: GlobalValueCreate,
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    if db.get(GlobalValue, body.uid) is not None:
        raise HTTPException(status_code=409, detail="Global value uid already exists")
    gv = GlobalValue(workspace_id=workspace_id, **body.model_dump())
    db.add(gv)
    db.commit()
    db.refresh(gv)
    return gv


@router.get("/{uid}", response_model=GlobalValueOut)
def get_global_value(
    uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    return _get_owned(uid, workspace_id, db)


@router.put("/{uid}", response_model=GlobalValueOut)
def update_global_value(
    uid: str,
    body: GlobalValueUpdate,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    gv = _get_owned(uid, workspace_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(gv, field, value)
    db.commit()
    db.refresh(gv)
    return gv


@router.delete("/{uid}", status_code=204)
def delete_global_value(
    uid: str, workspace_id: str = Depends(require_permission("delete")), db: Session = Depends(get_db)
):
    gv = _get_owned(uid, workspace_id, db)
    db.delete(gv)
    db.commit()
