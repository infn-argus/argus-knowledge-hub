"""Legacy migration plans (asset-model-revision §12): plan, review and
override, apply, roll back, finalize."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import PatIdentity, get_identity, require_permission
from app.db import get_db
from app.ledger import legacy
from app.ledger.engine import LedgerError
from app.models.legacy_migration import LegacyMigrationPlan
from app.routers.ledger import actor_of

router = APIRouter(prefix="/v1/migration", tags=["legacy migration"])


def _owned(db: Session, plan_id: str, workspace_id: str) -> LegacyMigrationPlan:
    p = db.get(LegacyMigrationPlan, plan_id)
    if p is None or p.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Plan not found")
    return p


def _fail(db: Session, exc: Exception):
    db.rollback()
    raise HTTPException(status_code=409, detail={"error": str(exc)})


class PlanIn(BaseModel):
    inventory_workspace_id: Optional[str] = None


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, identity=Depends(get_identity), workspace_id: str = Depends(require_permission("approve")),
                db: Session = Depends(get_db)):
    inventory = body.inventory_workspace_id or workspace_id
    if inventory != workspace_id:
        from app.services.permissions import resolve_permission
        if isinstance(identity, PatIdentity) or not resolve_permission(db, identity.user, inventory, "create", "objects"):
            raise HTTPException(status_code=403, detail=f"creating Equipment in {inventory} needs its create right")
    p = legacy.plan(db, workspace_id, actor_of(identity), inventory)
    db.commit()
    return legacy.view(db, p)


@router.get("/plans")
def list_plans(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    plans = db.scalars(select(LegacyMigrationPlan).where(LegacyMigrationPlan.workspace_id == workspace_id)
                       .order_by(LegacyMigrationPlan.created_at.desc()))
    return [legacy.view(db, p, rows=False) for p in plans]


@router.get("/gate")
def gate(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """§17.4 criterion 4: nothing M-BLOCK, every M-MIXED resolved or accepted."""
    return legacy.gate(db, workspace_id)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return legacy.view(db, _owned(db, plan_id, workspace_id))


@router.get("/plans/{plan_id}/report.csv", response_class=PlainTextResponse)
def report_csv(plan_id: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    p = _owned(db, plan_id, workspace_id)
    return PlainTextResponse(legacy.report_csv(db, p), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{p.id}.csv"'})


class OverrideIn(BaseModel):
    outcome: str
    reason: str


@router.post("/plans/{plan_id}/items/{item_id}/override")
def override(plan_id: str, item_id: int, body: OverrideIn, identity=Depends(get_identity),
             workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    _owned(db, plan_id, workspace_id)
    try:
        item = legacy.override(db, plan_id, item_id, body.outcome, actor_of(identity), body.reason)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return legacy.report_row(item)


@router.post("/plans/{plan_id}/apply")
def apply(plan_id: str, identity=Depends(get_identity), workspace_id: str = Depends(require_permission("approve")),
          db: Session = Depends(get_db)):
    _owned(db, plan_id, workspace_id)
    try:
        p = legacy.apply(db, plan_id, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return legacy.view(db, p)


class RollbackIn(BaseModel):
    item_ids: Optional[list[int]] = None


@router.post("/plans/{plan_id}/rollback")
def rollback(plan_id: str, body: RollbackIn, identity=Depends(get_identity),
             workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    _owned(db, plan_id, workspace_id)
    try:
        p = legacy.rollback(db, plan_id, actor_of(identity), body.item_ids)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return legacy.view(db, p)


@router.post("/plans/{plan_id}/verify")
def deep_verify(plan_id: str, identity=Depends(get_identity), workspace_id: str = Depends(require_permission("approve")),
                db: Session = Depends(get_db)):
    """I-MIG-5 and I-MIG-6; needed before finalizing."""
    _owned(db, plan_id, workspace_id)
    try:
        p = legacy.deep_verify(db, plan_id, actor_of(identity))
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return legacy.view(db, p)


class FinalizeIn(BaseModel):
    golden_waiver: Optional[str] = None     # why I-MIG-7 could not be checked


@router.post("/plans/{plan_id}/finalize")
def finalize(plan_id: str, body: Optional[FinalizeIn] = None, identity=Depends(get_identity),
             workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    _owned(db, plan_id, workspace_id)
    try:
        p = legacy.finalize(db, plan_id, actor_of(identity), (body or FinalizeIn()).golden_waiver)
    except LedgerError as exc:
        _fail(db, exc)
    db.commit()
    return legacy.view(db, p)


# --------------------------------------------------------------------------- golden incidents (I-MIG-7)

class GoldenIn(BaseModel):
    name: str
    symptoms: list[str]
    expected_causes: list[str]
    symptom_kind: dict[str, str] = {}
    healthy: list[str] = []
    ticket_uid: Optional[str] = None


def _golden_view(g) -> dict:
    return {"id": g.id, "name": g.name, "symptoms": g.symptoms, "expected_causes": g.expected_causes,
            "symptom_kind": g.symptom_kind, "healthy": g.healthy, "ticket_uid": g.ticket_uid,
            "created_by": g.created_by, "created_at": g.created_at}


@router.get("/golden-incidents")
def list_golden(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    from app.ledger import golden
    return [_golden_view(g) for g in golden.incidents(db, workspace_id)]


@router.post("/golden-incidents", status_code=201)
def create_golden(body: GoldenIn, identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    from app.ledger import golden
    try:
        g = golden.record(db, workspace_id, actor_of(identity), name=body.name, symptoms=body.symptoms,
                          expected_causes=body.expected_causes, symptom_kind=body.symptom_kind,
                          healthy=body.healthy, ticket_uid=body.ticket_uid)
    except golden.GoldenError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    db.commit()
    return _golden_view(g)


@router.delete("/golden-incidents/{incident_id}", status_code=204)
def delete_golden(incident_id: str, workspace_id: str = Depends(require_permission("approve")),
                  db: Session = Depends(get_db)):
    from app.models.legacy_migration import GoldenIncident
    g = db.get(GoldenIncident, incident_id)
    if g is None or g.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Incident not found")
    db.delete(g)
    db.commit()


@router.post("/golden-incidents/run")
def run_golden(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Walk every golden incident now: which expected causes are found, and at what rank."""
    from app.ledger import golden
    return golden.run(db, workspace_id)
