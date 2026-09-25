"""Jira retirement (asset-model-revision §19 item 14): the conditions, the
retention decision (U1) and the signature. Instance-wide, for administrators."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import OidcIdentity, get_identity
from app.db import get_db
from app.routers.ledger import actor_of
from app.services import retirement

router = APIRouter(prefix="/v1/retirement", tags=["retirement"])


def require_admin(identity=Depends(get_identity)):
    if not isinstance(identity, OidcIdentity) or not identity.user.is_admin:
        raise HTTPException(status_code=403, detail="Retiring Jira is for administrators")
    return identity


@router.get("")
def retirement_status(identity=Depends(require_admin), db: Session = Depends(get_db)):
    return {**retirement.status(db), "attestations": retirement.ATTESTATIONS}


class RetentionIn(BaseModel):
    reference: str
    jira_archive_until: date
    exports_until: Optional[date] = None
    audit_until: Optional[date] = None
    note: Optional[str] = None


@router.post("/retention", status_code=201)
def record_retention(body: RetentionIn, identity=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        d = retirement.record_retention(db, actor_of(identity), reference=body.reference,
                                        jira_archive_until=body.jira_archive_until, exports_until=body.exports_until,
                                        audit_until=body.audit_until, note=body.note)
    except retirement.RetirementError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    db.commit()
    return {"decision_id": d.decision_id, **d.value}


class SignIn(BaseModel):
    attestations: dict[str, bool] = {}
    reason: Optional[str] = None


@router.post("/sign")
def sign(body: SignIn, identity=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        decision = retirement.sign(db, actor_of(identity), body.attestations, body.reason)
    except retirement.RetirementError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={
            "error": str(exc), "conditions": retirement.conditions(db, body.attestations)})
    db.commit()
    return {"decision_id": decision.decision_id, **retirement.status(db)}
