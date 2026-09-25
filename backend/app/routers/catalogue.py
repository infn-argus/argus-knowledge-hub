"""Governing `Other Equipment` (asset-model-revision §5.5): the equipment
class vocabulary, the report, promotion reviews and promotion."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_identity, require_permission
from app.db import get_db
from app.models.equipment_class import EquipmentClassReview
from app.models.schema import Schema
from app.routers.ledger import actor_of
from app.services import equipment_classes as ec

router = APIRouter(prefix="/v1/catalogue/equipment-classes", tags=["catalogue"])


def _catalogue(db: Session, workspace_id: str) -> None:
    """Catalogue decisions are taken in the catalogue: the workspace that
    holds the global `Asset` type."""
    if db.scalar(select(Schema.uid).where(Schema.workspace_id == workspace_id, Schema.name == "Asset",
                                          Schema.is_global.is_(True))) is None:
        raise HTTPException(status_code=403, detail={"error": "only the catalogue workspace governs equipment classes"})


def _fail(db: Session, exc: Exception):
    db.rollback()
    raise HTTPException(status_code=422, detail={"error": str(exc)})


def _class_view(c) -> dict:
    return {"name": c.name, "status": c.status, "promoted_type": c.promoted_type, "added_by": c.added_by,
            "added_at": c.added_at, "note": c.note}


def _review_view(r) -> dict:
    return {"id": r.id, "class": r.class_name, "triggers": r.triggers, "status": r.status, "opened_at": r.opened_at,
            "decided_by": r.decided_by, "decided_at": r.decided_at, "reason": r.reason}


@router.get("")
def vocabulary(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    out = [_class_view(c) for c in ec.vocabulary(db)]
    db.commit()
    return out


class ClassIn(BaseModel):
    name: str
    note: Optional[str] = None


@router.post("", status_code=201)
def add_class(body: ClassIn, identity=Depends(get_identity), workspace_id: str = Depends(require_permission("approve")),
              db: Session = Depends(get_db)):
    _catalogue(db, workspace_id)
    try:
        c = ec.add_class(db, body.name, actor_of(identity), body.note)
    except ec.ClassError as exc:
        _fail(db, exc)
    db.commit()
    return _class_view(c)


class RequestIn(BaseModel):
    class_name: str
    attribute: str
    reason: Optional[str] = None


@router.post("/requests", status_code=201)
def request_attribute(body: RequestIn, identity=Depends(get_identity),
                      workspace_id: str = Depends(require_permission("create")), db: Session = Depends(get_db)):
    """Anyone who works with the equipment asks for a class-specific attribute."""
    try:
        r = ec.request_attribute(db, workspace_id, actor_of(identity), body.class_name, body.attribute, body.reason)
    except ec.ClassError as exc:
        _fail(db, exc)
    db.commit()
    return {"id": r.id, "class": r.class_name, "attribute": r.attribute}


@router.get("/report")
def report(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    _catalogue(db, workspace_id)
    out = ec.report(db)
    db.commit()
    return out


@router.get("/reviews")
def reviews(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return [_review_view(r) for r in db.scalars(select(EquipmentClassReview)
                                                .order_by(EquipmentClassReview.opened_at.desc()))]


@router.post("/reviews/run")
def run_thresholds(workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """Open a review for every class that meets a threshold (the monthly job does this too)."""
    _catalogue(db, workspace_id)
    opened = ec.open_reviews(db)
    db.commit()
    return [_review_view(r) for r in opened]


class ReviewIn(BaseModel):
    class_name: str
    reason: str


@router.post("/reviews", status_code=201)
def open_review(body: ReviewIn, identity=Depends(get_identity),
                workspace_id: str = Depends(require_permission("create")), db: Session = Depends(get_db)):
    try:
        r = ec.open_review(db, body.class_name, actor_of(identity), body.reason)
    except ec.ClassError as exc:
        _fail(db, exc)
    db.commit()
    return _review_view(r)


class DeclineIn(BaseModel):
    reason: str


@router.post("/reviews/{review_id}/decline")
def decline(review_id: int, body: DeclineIn, identity=Depends(get_identity),
            workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    _catalogue(db, workspace_id)
    try:
        r = ec.decline(db, review_id, actor_of(identity), body.reason)
    except ec.ClassError as exc:
        _fail(db, exc)
    db.commit()
    return _review_view(r)


class PromoteIn(BaseModel):
    class_name: str
    type_name: str
    reason: str


@router.post("/promote")
def promote(body: PromoteIn, identity=Depends(get_identity),
            workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    _catalogue(db, workspace_id)
    try:
        out = ec.promote(db, workspace_id, actor_of(identity), body.class_name, body.type_name, body.reason)
    except ec.ClassError as exc:
        _fail(db, exc)
    db.commit()
    return out
