"""The beam model's API (docs/beam-model.md): read the physics positions, their topology and datasets, and
everything the facility knows behind each one; import a canonical model; bind positions to hardware.

Binding decisions are the Installations' own: confirm, reject and swap are `/v1/installations/...`."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_identity, require_permission
from app.db import get_db
from app.ledger.engine import LedgerError
from app.models.asset import Asset
from app.routers.hub import scope as hub_scope
from app.services import beam_model as bm

systems_router = APIRouter(prefix="/v1/beam-systems", tags=["beam-model"])
paths_router = APIRouter(prefix="/v1/beam-paths", tags=["beam-model"])
elements_router = APIRouter(prefix="/v1/beam-elements", tags=["beam-model"])
diagnostics_router = APIRouter(prefix="/v1/diagnostics", tags=["beam-model"])
observables_router = APIRouter(prefix="/v1/observables", tags=["beam-model"])
datasets_router = APIRouter(prefix="/v1/model-datasets", tags=["beam-model"])
bindings_router = APIRouter(prefix="/v1/model-bindings", tags=["beam-model"])
model_router = APIRouter(prefix="/v1/beam-model", tags=["beam-model"])
ROUTERS = [systems_router, paths_router, elements_router, diagnostics_router, observables_router,
           datasets_router, bindings_router, model_router]


def _actor(identity) -> str:
    from app.routers.ledger import actor_of
    return actor_of(identity)


def _record(db: Session, workspace_id: str, uid: str, types: Optional[set] = None, what: str = "record") -> Asset:
    a = db.get(Asset, uid)
    if a is None or a.workspace_id != workspace_id or a.deleted_at is not None or (types and a.type not in types):
        raise HTTPException(status_code=404, detail=f"No such {what} in this workspace")
    return a


def _element(db: Session, workspace_id: str, uid: str) -> Asset:
    from app.ledger.registry import BEAM_ELEMENTS
    return _record(db, workspace_id, uid, BEAM_ELEMENTS, "beam element")


def _of_type(db: Session, workspace_id: str, types: set) -> list[Asset]:
    return list(db.scalars(select(Asset).where(Asset.workspace_id == workspace_id, Asset.type.in_(types),
                                               Asset.deleted_at.is_(None),
                                               Asset.record_status.notin_(("Retired", "Merged")))
                           .order_by(Asset.name)))


# --------------------------------------------------------------------------- systems and paths

@systems_router.get("")
def list_systems(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The beam systems here, each with its beams and paths."""
    out = []
    for s in _of_type(db, workspace_id, {"Beam System"}):
        beams = [bm._summary(b) | {"attributes": _attrs(b)} for b in bm._sources(db, "beam of", [s.uid])]
        paths = [bm._summary(p) for p in bm._sources(db, "part of", [s.uid]) if p.type == "Beam Path"]
        out.append({**bm._summary(s), "beams": beams, "paths": paths})
    return out


@systems_router.get("/{uid}")
def get_system(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    s = _record(db, workspace_id, uid, {"Beam System"}, "beam system")
    return {**bm._summary(s), "attributes": _attrs(s),
            "beams": [bm._summary(b) | {"attributes": _attrs(b)} for b in bm._sources(db, "beam of", [uid])],
            "paths": [bm._summary(p) for p in bm._sources(db, "part of", [uid]) if p.type == "Beam Path"]}


@paths_router.get("")
def list_paths(system: Optional[str] = None, workspace_id: str = Depends(require_permission("read")),
               db: Session = Depends(get_db)):
    paths = _of_type(db, workspace_id, {"Beam Path"})
    if system:
        paths = [p for p in paths if any(t.uid == system for t in bm._targets(db, "part of", [p.uid]))]
    return [bm._summary(p) | {"attributes": _attrs(p)} for p in paths]


@paths_router.get("/{uid}/graph")
def path_graph(uid: str, dataset: Optional[str] = None, workspace_id: str = Depends(require_permission("read")),
               db: Session = Depends(get_db)):
    """The path for a viewer: ordered nodes with `s` and geometry from a dataset (its design optics when none
    is named), the edges between them, and the branches that leave and join it."""
    _record(db, workspace_id, uid, {"Beam Path"}, "beam path")
    return bm.path_graph(db, workspace_id, uid, dataset)


@paths_router.get("/{uid}/elements")
def path_elements(uid: str, dataset: Optional[str] = None, workspace_id: str = Depends(require_permission("read")),
                  db: Session = Depends(get_db)):
    _record(db, workspace_id, uid, {"Beam Path"}, "beam path")
    return bm.path_graph(db, workspace_id, uid, dataset)["nodes"]


@paths_router.get("/{uid}")
def get_path(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    p = _record(db, workspace_id, uid, {"Beam Path"}, "beam path")
    return {**bm._summary(p), "attributes": _attrs(p),
            "system": [bm._summary(s) for s in bm._targets(db, "part of", [uid])],
            "datasets": [bm._summary(d) for d in bm._sources(db, "models", [uid])]}


# --------------------------------------------------------------------------- elements

@elements_router.get("")
def list_elements(path: Optional[str] = None, kind: Optional[str] = None, q: Optional[str] = None,
                  workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Beam elements, in beam order when a path is given."""
    from app.ledger.registry import BEAM_ELEMENTS
    if path:
        _record(db, workspace_id, path, {"Beam Path"}, "beam path")
        rows = [db.get(Asset, u) for u in bm.ordered_elements(bm._Graph(db, workspace_id), path)]
    else:
        rows = _of_type(db, workspace_id, BEAM_ELEMENTS)
    out = [bm._summary(a) for a in rows if a is not None]
    if kind:
        out = [a for a in out if a.get("element_kind") == kind or a["type"] == kind]
    if q:
        needle = q.lower()
        out = [a for a in out if needle in (a["name"] or "").lower() or needle in (a.get("model_name") or "").lower()]
    return out


@elements_router.get("/{uid}")
def get_element(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    a = _element(db, workspace_id, uid)
    path = bm.path_of(db, uid)
    return {**bm._summary(a), "attributes": _attrs(a), "path": bm._summary(db.get(Asset, path)) if path else None}


@elements_router.get("/{uid}/context")
def element_context(uid: str, dataset: Optional[str] = None, db: Session = Depends(get_db),
                    s=Depends(hub_scope)):
    """Everything a viewer shows for a selected position: physics and optics from the datasets, the hardware
    installed and its history, power, controls (signal identities, never values), documentation and tickets
    of the installed unit, and what it observes. Documents and tickets follow the reader's own rights."""
    if not s.access.assets:
        raise HTTPException(status_code=403, detail="Not permitted")
    _element(db, s.workspace_id, uid)
    return bm.context(db, s.workspace_id, uid, dataset, access=s.access)


@elements_router.get("/{uid}/upstream")
def upstream(uid: str, n: int = Query(1, ge=1, le=1000), workspace_id: str = Depends(require_permission("read")),
             db: Session = Depends(get_db)):
    _element(db, workspace_id, uid)
    return bm.neighbours(db, workspace_id, uid, "upstream", n)


@elements_router.get("/{uid}/downstream")
def downstream(uid: str, n: int = Query(1, ge=1, le=1000), workspace_id: str = Depends(require_permission("read")),
               db: Session = Depends(get_db)):
    _element(db, workspace_id, uid)
    return bm.neighbours(db, workspace_id, uid, "downstream", n)


@elements_router.get("/{uid}/between/{other}")
def between(uid: str, other: str, workspace_id: str = Depends(require_permission("read")),
            db: Session = Depends(get_db)):
    _element(db, workspace_id, uid)
    _element(db, workspace_id, other)
    found = bm.between(db, workspace_id, uid, other)
    if found is None:
        raise HTTPException(status_code=404, detail="The beam does not go from one to the other")
    return found


@elements_router.get("/{uid}/equipment")
def element_equipment(uid: str, at: Optional[datetime] = None,
                      workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The hardware installed at the position now, or at `at`, and its whole installation history."""
    _element(db, workspace_id, uid)
    return bm.equipment(db, workspace_id, uid, at.isoformat() if at else None)


@elements_router.get("/{uid}/controls")
def element_controls(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    _element(db, workspace_id, uid)
    return bm.controls(db, workspace_id, uid)


@elements_router.get("/{uid}/observables")
def element_observables(uid: str, workspace_id: str = Depends(require_permission("read")),
                        db: Session = Depends(get_db)):
    _element(db, workspace_id, uid)
    return bm.observables_of(db, workspace_id, uid)


@elements_router.get("/{uid}/diagnostics")
def element_diagnostics(uid: str, n: int = Query(20, ge=1, le=1000),
                        workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The diagnostics nearest the position, up- and downstream within n steps."""
    _element(db, workspace_id, uid)
    out = {}
    for direction in ("upstream", "downstream"):
        out[direction] = [x for x in bm.neighbours(db, workspace_id, uid, direction, n)
                          if bm._is_diagnostic(db.get(Asset, x["uid"]))]
    return out


@elements_router.get("/{uid}/correctors")
def element_correctors(uid: str, plane: str = Query("x", pattern="^(x|y)$"),
                       workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The steering elements upstream of the position that act in a plane, nearest first."""
    _element(db, workspace_id, uid)
    return bm.correctors_upstream(db, workspace_id, uid, plane)


# --------------------------------------------------------------------------- diagnostics and observables

@diagnostics_router.get("")
def list_diagnostics(path: Optional[str] = None, observable: Optional[str] = None,
                     workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Diagnostic positions, of a path or all; only those observing `observable` when given."""
    return bm.diagnostics(db, workspace_id, path, observable)


@observables_router.get("")
def list_observables(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    return [bm._summary(o) | {"attributes": _attrs(o)} for o in _of_type(db, workspace_id, {"Observable"})]


@observables_router.get("/{quantity}")
def get_observable(quantity: str, workspace_id: str = Depends(require_permission("read")),
                   db: Session = Depends(get_db)):
    """An observable: the diagnostics that observe it and the control signals that measure it."""
    obs = next((o for o in _of_type(db, workspace_id, {"Observable"}) if (o.attributes or {}).get("quantity") == quantity), None)
    if obs is None:
        raise HTTPException(status_code=404, detail="No such observable in this workspace")
    signals = [bm._summary(s) for s in bm._sources(db, "measures", [obs.uid]) if s.type == "Control Signal"]
    return {**bm._summary(obs), "attributes": _attrs(obs), "diagnostics": bm.diagnostics(db, workspace_id, None, quantity),
            "signals": signals}


# --------------------------------------------------------------------------- datasets and bindings

@datasets_router.get("")
def list_datasets(path: Optional[str] = None, workspace_id: str = Depends(require_permission("read")),
                  db: Session = Depends(get_db)):
    rows = _of_type(db, workspace_id, {"Model Dataset"})
    if path:
        rows = [d for d in rows if any(t.uid == path for t in bm._targets(db, "models", [d.uid]))]
    return [bm._summary(d) | {"attributes": _attrs(d)} for d in rows]


@datasets_router.get("/{uid}")
def get_dataset(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """A dataset, its provenance, and its values per element in `s` order."""
    view = bm.dataset_view(db, workspace_id, uid)
    if view is None:
        raise HTTPException(status_code=404, detail="No such model dataset in this workspace")
    return view


@bindings_router.get("")
def list_bindings(state: Optional[str] = Query(None, pattern="^(confirmed|historical|proposed|rejected|withdrawn)$"),
                  workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Every position's bindings to hardware: confirmed (current), historical (ended), proposed (waiting for a
    person in the review queue), rejected or withdrawn. Confirm or reject one at /v1/installations/{uid}."""
    rows = bm.bindings(db, workspace_id)
    return [r for r in rows if not state or r["state"] == state]


@bindings_router.post("/propose")
def propose_bindings(identity=Depends(get_identity), workspace_id: str = Depends(require_permission("create")),
                     db: Session = Depends(get_db)):
    """Propose bindings by name: each unbound position whose model name names exactly one physical asset here
    gets a proposed Installation in the review queue. Nothing becomes a binding until a person confirms it."""
    try:
        report = bm.propose_bindings(db, workspace_id)
    except LedgerError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    return report


class BindingIn(BaseModel):
    position_uid: str
    asset_uid: str
    valid_from: datetime


@bindings_router.post("", status_code=201)
def create_binding(body: BindingIn, identity=Depends(get_identity),
                   workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    """A person binds a position to the hardware installed there from a date: a confirmed Installation."""
    from app.ledger import service
    actor = _actor(identity)
    try:
        uid = service.new_installation_claims(db, workspace_id, actor, body.position_uid, body.asset_uid,
                                              {"kind": "date", "nominal": body.valid_from.isoformat(),
                                               "precision": "instant"})
        service.confirm_installation(db, workspace_id, actor, uid)
    except LedgerError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    return {"installation_uid": uid}


# --------------------------------------------------------------------------- import and signals

@model_router.get("/formats")
def formats():
    """What can be read: the canonical JSON, and every simulator converter installed (app/beam_converters)."""
    from app import beam_converters as bc
    return [{"name": "argus", "label": "ARGUS canonical JSON (argus.beam-model/1)", "extensions": [".json"]}] + [
        {"name": c.name, "label": c.label, "extensions": list(c.extensions)} for c in bc.converters()]


@model_router.get("/schema")
def schema():
    """The JSON Schema of the canonical representation (docs/beam-model-format.md)."""
    return bm.json_schema()


class ConvertIn(BaseModel):
    filename: str
    content: str
    converter: Optional[str] = None
    options: dict = {}


@model_router.post("/convert")
def convert(body: ConvertIn, workspace_id: str = Depends(require_permission("read"))):
    """A simulator file (MAD-X sequence or TFS table, Elegant lattice …) turned into a canonical model, checked,
    and returned for a person to look at. Nothing is written: importing is a separate step."""
    from app import beam_converters as bc
    try:
        options = bc.Options(**{k: v for k, v in body.options.items() if k in bc.Options.__dataclass_fields__})
        doc = bc.convert(body.filename, body.content, options, body.converter)
    except (bc.ConversionError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail={"problems": [str(e)]}) from e
    report = doc.pop("conversion", {})
    return {"model": doc, "report": report, "check": bm.check_all([doc])[0]}


@model_router.get("/models")
def list_models(workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The beam models in this workspace, by model id, with what each holds."""
    return bm.list_models(db, workspace_id)


@model_router.get("/models/{model_id}/export")
def export_model(model_id: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """One model as canonical JSON (argus.beam-model/1), from what the hub holds now: importing it again, here
    or in another hub, gives the same model."""
    doc = bm.export_canonical(db, workspace_id, model_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No such beam model in this workspace")
    return doc


@model_router.get("/export")
def export_models(model: Optional[list[str]] = Query(None, description="Model ids; all when omitted"),
                  workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Several models (or all) in one bundle (argus.beam-model-bundle/1)."""
    return bm.export_bundle(db, workspace_id, model)


@model_router.post("/validate")
def validate_models(doc=Body(..., description="A model, a bundle, or a list of models"),
                    workspace_id: str = Depends(require_permission("read"))):
    """Check models without importing them: each one's problems, or what it holds."""
    return {"models": bm.check_all(bm.models_of(doc))}


@model_router.post("/import")
def import_model(doc=Body(..., description="A canonical beam model (argus.beam-model/1), a bundle "
                                           "(argus.beam-model-bundle/1) or a list of models"),
                 identity=Depends(get_identity), workspace_id: str = Depends(require_permission("create")),
                 db: Session = Depends(get_db)):
    """Import (or update) one or several canonical beam models, all or none: if any is invalid nothing is written.
    Records and topology become ledger claims with their provenance; each dataset's values are replaced. A model
    a signed-in person brings takes effect at once; one an API token pushes (the Accelerator Model Toolbox) is
    external, and waits for the authority policy to cover its source. A revision that would retire too much is
    held for approval."""
    from app.auth import PatIdentity
    docs = bm.models_of(doc)
    checks = bm.check_all(docs)
    if not docs or any(not c["ok"] for c in checks):
        if len(docs) == 1 and checks:
            raise HTTPException(status_code=422, detail={"problems": checks[0]["problems"]})
        raise HTTPException(status_code=422, detail={"models": checks})
    trusted = not isinstance(identity, PatIdentity)
    reports = []
    try:
        for d in docs:
            reports.append(bm.import_canonical(db, workspace_id, d, _actor(identity), trusted=trusted))
    except bm.BeamModelError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={"problems": e.problems}) from e
    except LedgerError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    return reports[0] if len(docs) == 1 and not isinstance(doc, list) and \
        not (isinstance(doc, dict) and doc.get("format") == bm.BUNDLE_FORMAT) else {"models": reports}


class SignalIn(BaseModel):
    name: str
    address: str
    role: str
    device_uid: Optional[str] = None
    for_uid: Optional[str] = None
    measures: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    system: str = "EPICS"


@model_router.post("/signals", status_code=201)
def create_signal(body: SignalIn, identity=Depends(get_identity),
                  workspace_id: str = Depends(require_permission("create")), db: Session = Depends(get_db)):
    """A control signal's identity: which PV carries which quantity, for which position, from which device."""
    try:
        uid = bm.ensure_signal(db, workspace_id, _actor(identity), **body.model_dump())
    except (bm.BeamModelError, LedgerError) as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
    db.commit()
    return {"uid": uid}


def _attrs(a: Asset) -> dict:
    return {k: v for k, v in (a.attributes or {}).items() if not k.startswith("argus_")}
