"""Map imported hardware models into a catalogue (services/catalogue_mapping.py).

Reading the source needs read on objects there; proposing, reviewing and
applying need create on objects in the catalogue. A token is fixed to one
workspace and a mapping spans two, so it takes a signed-in person.
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Identity, PatIdentity, get_identity
from app.db import get_db
from app.models.catalogue_mapping import CatalogueMapping
from app.models.workspace import Workspace
from app.routers.ledger import actor_of
from app.services import catalogue_mapping as cm
from app.services import record_mapping as rm
from app.services.permissions import resolve_permission

router = APIRouter(prefix="/v1/catalogue-mappings", tags=["catalogue-mappings"])


def _person(identity: Identity):
    if isinstance(identity, PatIdentity):
        raise HTTPException(status_code=403, detail="A mapping spans two workspaces; sign in as a person to use it")
    return identity.user


def _can(db: Session, identity: Identity, workspace_id: str, action: str) -> None:
    user = _person(identity)
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail=f"No workspace {workspace_id}")
    if not resolve_permission(db, user, workspace_id, action, "objects"):
        raise HTTPException(status_code=403, detail=f"You may not {action} objects in {workspace_id}")


def _mapping(db: Session, identity: Identity, mapping_id: str, write: bool) -> CatalogueMapping:
    mapping = db.get(CatalogueMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="No such mapping")
    _can(db, identity, mapping.source_workspace_id, "read")
    _can(db, identity, mapping.target_workspace_id, "create" if write else "read")
    return mapping


def _fail(db: Session, exc: Exception):
    db.rollback()
    raise HTTPException(status_code=422, detail=str(exc))


class MappingStartIn(BaseModel):
    kind: str = "catalogue"                   # catalogue | records
    source_workspace_id: str
    target_workspace_id: str
    type_uids: list[str]
    use_ai: bool = True
    include_mapped: bool = False


class MappingDecideIn(BaseModel):
    status: Optional[str] = None
    fields: Optional[dict] = None
    attributes: Optional[dict] = None
    vendor: Optional[str] = None
    action: Optional[str] = None
    merge_into_uid: Optional[str] = None


class MappingBulkIn(BaseModel):
    item_ids: list[str] = []
    status: Optional[str] = None
    min_confidence: Optional[float] = None
    type_uid: Optional[str] = None


class MappingPlanIn(BaseModel):
    target_type_uid: Optional[str] = None
    share: Optional[bool] = None
    companions: Optional[dict] = None
    fixed: Optional[dict] = None
    fields: Optional[dict] = None
    relations: Optional[dict] = None


def _svc(mapping):
    return rm if mapping.kind == rm.KIND else cm


@router.get("/sources")
def list_sources(workspace_id: str, kind: str = "catalogue", target_workspace_id: Optional[str] = None,
                 identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """The source workspace's object types with their open and mapped records."""
    _can(db, identity, workspace_id, "read")
    if kind == rm.KIND:
        return rm.sources(db, workspace_id, target_workspace_id)
    return cm.sources(db, workspace_id)


@router.get("")
def list_mappings(identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    user = _person(identity)
    rows = db.scalars(select(CatalogueMapping).order_by(CatalogueMapping.created_at.desc()).limit(50)).all()
    visible = [m for m in rows
               if resolve_permission(db, user, m.source_workspace_id, "read", "objects")
               and resolve_permission(db, user, m.target_workspace_id, "read", "objects")]
    out = []
    for m in visible:
        v = cm.view(db, m)
        v.pop("items")
        out.append(v)
    return out


@router.post("", status_code=201)
def start_mapping(body: MappingStartIn, background: BackgroundTasks, identity: Identity = Depends(get_identity),
                  db: Session = Depends(get_db)):
    """Proposes what each open record of the chosen types becomes; the analysis runs in the background."""
    _can(db, identity, body.source_workspace_id, "read")
    _can(db, identity, body.target_workspace_id, "create")
    svc = rm if body.kind == rm.KIND else cm
    try:
        mapping = svc.start(db, actor_of(identity), body.source_workspace_id, body.target_workspace_id,
                            body.type_uids, body.use_ai, body.include_mapped)
    except cm.MappingError as exc:
        _fail(db, exc)
    db.commit()
    background.add_task(svc.run_in_background, mapping.id)
    return cm.view(db, mapping, with_items=False)


@router.get("/{mapping_id}")
def get_mapping(mapping_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    return cm.view(db, _mapping(db, identity, mapping_id, write=False))


@router.get("/{mapping_id}/vocabulary")
def get_vocabulary(mapping_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """For a record mapping: the target's types, the attributes of those in the plan, and the relation verbs."""
    return rm.vocabulary(db, _mapping(db, identity, mapping_id, write=False))


@router.post("/{mapping_id}/share-references")
def share_mapping_references(mapping_id: str, identity: Identity = Depends(get_identity),
                             db: Session = Depends(get_db)):
    """Share the records rows name but cannot see, and derive the rows again. Needs modify rights where
    those records live."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    if mapping.kind != rm.KIND:
        raise HTTPException(status_code=422, detail="Only a record mapping resolves references")
    for ws in {h["workspace_id"] for h in rm.hidden_references(db, mapping).values()}:
        _can(db, identity, ws, "modify")
    result = rm.share_references(db, mapping)
    db.commit()
    return result


@router.post("/{mapping_id}/fill-references")
def fill_mapping_references(mapping_id: str, identity: Identity = Depends(get_identity),
                            db: Session = Depends(get_db)):
    """Applied rows: set the references their records still lack, now that they resolve."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    if mapping.kind != rm.KIND:
        raise HTTPException(status_code=422, detail="Only a record mapping resolves references")
    result = rm.fill_references(db, mapping, actor_of(identity))
    db.commit()
    return result


@router.post("/{mapping_id}/recheck")
def recheck_mapping(mapping_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """Derive the open rows again, e.g. once the catalogue's records are shared."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    if mapping.kind != rm.KIND:
        raise HTTPException(status_code=422, detail="Only a record mapping follows a plan")
    result = rm.recheck(db, mapping)
    db.commit()
    return result


@router.put("/{mapping_id}/plan/{type_uid}")
def put_plan(mapping_id: str, type_uid: str, body: MappingPlanIn, identity: Identity = Depends(get_identity),
             db: Session = Depends(get_db)):
    """Correct one source type's plan; its rows follow, except those a person changed."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    if mapping.kind != rm.KIND:
        raise HTTPException(status_code=422, detail="Only a record mapping has a plan")
    try:
        entry = rm.set_plan(db, mapping, type_uid, body.model_dump(exclude_unset=True), actor_of(identity))
    except cm.MappingError as exc:
        _fail(db, exc)
    db.commit()
    return entry


@router.patch("/{mapping_id}/items/{item_id}")
def decide_item(mapping_id: str, item_id: str, body: MappingDecideIn, identity: Identity = Depends(get_identity),
                db: Session = Depends(get_db)):
    """Accept, skip or correct one row. A correction accepts the row."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    edits = body.model_dump(exclude_unset=True)
    status = edits.pop("status", None)
    try:
        item = _svc(mapping).decide(db, mapping, actor_of(identity), item_id, status, edits or None)
    except cm.MappingError as exc:
        _fail(db, exc)
    db.commit()
    return cm.item_view(item)


@router.post("/{mapping_id}/items")
def decide_many(mapping_id: str, body: MappingBulkIn, identity: Identity = Depends(get_identity),
                db: Session = Depends(get_db)):
    """Several rows at once: a status for the listed rows, or accept every proposed row at least this confident."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    actor = actor_of(identity)
    changed, errors = 0, []
    svc = _svc(mapping)
    if body.min_confidence is not None:
        changed = (rm.accept_confident(db, mapping, actor, body.min_confidence, body.type_uid) if svc is rm
                   else cm.accept_confident(db, mapping, actor, body.min_confidence))
    elif body.status:
        for item_id in body.item_ids:
            try:
                svc.decide(db, mapping, actor, item_id, body.status)
                changed += 1
            except cm.MappingError as exc:
                errors.append({"item": item_id, "error": str(exc)})
    db.commit()
    return {"changed": changed, "errors": errors}


@router.post("/{mapping_id}/apply")
def apply_mapping(mapping_id: str, keep_text: bool = False, identity: Identity = Depends(get_identity),
                  db: Session = Depends(get_db)):
    """Creates the accepted rows. Skipped and proposed rows stay open. A record mapping refuses rows that
    name records the target cannot see, unless `keep_text` says to store those references as text."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    if mapping.state != "ready":
        raise HTTPException(status_code=409, detail="The mapping is still being analysed")
    try:
        result = (rm.apply(db, mapping, actor_of(identity), keep_text=keep_text) if mapping.kind == rm.KIND
                  else cm.apply(db, mapping, actor_of(identity)))
    except rm.HiddenReferences as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"error": str(exc), "code": "hidden_references",
                                                     "references": list(exc.found.values())[:50]})
    except cm.MappingError as exc:
        _fail(db, exc)
    db.commit()
    return result


@router.post("/{mapping_id}/carry")
def carry_mapping(mapping_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """Rows applied before attachments and history came along: bring them to the records they became."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    result = cm.carry_applied(db, mapping, actor_of(identity))
    db.commit()
    return result


@router.post("/{mapping_id}/share")
def share_mapping(mapping_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """Share the catalogue records this mapping created with every workspace."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    result = cm.share(db, mapping)
    db.commit()
    return result


@router.post("/{mapping_id}/undo")
def undo_mapping(mapping_id: str, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """Retires what this mapping created and removes its aliases; its rows are open again."""
    mapping = _mapping(db, identity, mapping_id, write=True)
    result = _svc(mapping).undo(db, mapping, actor_of(identity))
    db.commit()
    return result
