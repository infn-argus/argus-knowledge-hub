"""Template packages: what this installation ships, what a workspace uses (exact versions and checksums,
with its history), and installing them — previewed first, applied all or nothing (app.packages)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Identity, OidcIdentity, PatIdentity, get_identity
from app.db import get_db
from app.models.workspace import Workspace
from app.packages import install as installer
from app.packages.behaviors import describe as behaviors
from app.packages import revert as reverter
from app.packages.loader import available
from app.packages.validate import validate

router = APIRouter(prefix="/v1", tags=["packages"])


class FeaturesOut(BaseModel):
    tickets: bool
    documents: bool
    equipment: bool
    records: bool
    map: bool
    beam_model: bool
    control_system: bool
    type_catalogue: bool


class MapLayerOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class CapabilitiesOut(BaseModel):
    workspace_id: str
    packages: list[str]
    provides: list[str]
    features: FeaturesOut
    map_layers: list[MapLayerOut]
    ticket_kinds: list[str]
    document_kinds: list[str]
    importers: list[str]


class PackagesIn(BaseModel):
    packages: list[str]
    # for the accelerator catalogue: hang from this catalogue workspace's shared types
    catalogue_workspace_id: Optional[str] = None
    # for the accelerator catalogue: "global" makes this workspace the catalogue others hang from
    scope: Optional[str] = None
    # an upgrade's migration plan: for each breaking change (by id), "apply" or "keep"
    decisions: dict[str, str] = {}


class RevertIn(BaseModel):
    package_id: str
    # the earlier version to go back to, by the checksum of what the workspace was given then
    checksum: str
    decisions: dict[str, str] = {}


class EverywhereIn(BaseModel):
    # the workspaces to upgrade (default: every one behind); each without a decision to make is upgraded
    workspaces: Optional[list[str]] = None


def _may_read(db: Session, identity: Identity, workspace_id: str) -> None:
    from app.services.permissions import resolve_permission
    if db.get(Workspace, workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if isinstance(identity, PatIdentity):
        if identity.workspace_id != workspace_id:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return
    if identity.user.is_admin:
        return
    if not any(resolve_permission(db, identity.user, workspace_id, "read", r) for r in ("objects", "tickets", "documents")):
        raise HTTPException(status_code=404, detail="Workspace not found")


def _may_install(db: Session, identity: Identity, workspace_id: str) -> None:
    from app.routers.workspaces import _require_owner_or_admin
    _require_owner_or_admin(workspace_id, identity, db)


@router.get("/packages")
def list_packages(identity: Identity = Depends(get_identity)):
    """The template packages this installation ships, each with what it holds and whether it is valid."""
    catalog = available()
    return [{**p.describe(), "installable": True,
             "problems": [str(x) for x in validate(p, catalog)]} for p in catalog.values()]


@router.get("/packages/behaviors")
def list_behaviors(identity=Depends(get_identity)):
    """The behaviour ids a package may give a type, and the type each is bound to in this release."""
    return behaviors()


@router.get("/packages/{package_id}")
def get_package(package_id: str, identity=Depends(get_identity)):
    """One package: its manifest and the names of what it defines."""
    p = available().get(package_id)
    if p is None:
        raise HTTPException(status_code=404, detail="No such package")
    objects = (p.section("object_types") or {}).get("types") or []
    return {**p.describe(), "problems": [str(x) for x in validate(p)],
            "object_types": [{"name": t.get("name"), "parent": t.get("parent"), "abstract": bool(t.get("abstract")),
                              "locatable": bool(t.get("locatable")), "map_layer": t.get("map_layer")} for t in objects],
            "ticket_types": [k.get("name") for k in (p.section("ticket_types") or {}).get("kinds") or []],
            "document_types": [k.get("name") for k in (p.section("document_types") or {}).get("kinds") or []],
            "enumerations": [f"{e.get('applies_to')}.{e.get('key')}" for e in p.section("enumerations") or []],
            "workflows": [{"id": w.get("id"), "name": w.get("name"), "applies_to": w.get("applies_to") or []}
                          for w in p.section("workflows") or []],
            "map_layers": p.section("map_layers") or [],
            "extends": [{"area": e.get("area", "object_types"), "type": e.get("type"),
                         "attributes": [a.get("key") for a in e.get("attributes") or []],
                         "options": {k: [o.get("id") for o in v] for k, v in (e.get("options") or {}).items()}}
                        for e in p.section("extends") or []],
            "relation_types": p.section("relation_types") or [],
            "roles": p.section("roles") or [],
            "restricted_classes": p.section("restricted_classes") or [],
            "imports": p.section("imports") or [],
            "queries": [{k: q.get(k) for k in ("id", "title", "entity", "jql", "from", "relation", "expect")}
                        for q in p.section("queries") or []]}


def _problem(e: "installer.PackageProblem") -> dict:
    out = {"error": str(e), "code": "package"}
    if isinstance(e, installer.CatalogueBehind):
        out.update({"code": "catalogue_behind", "catalogue_workspace_id": e.catalogue, "needs": e.needs})
    return out


@router.post("/packages/resolve")
def resolve_packages(body: PackagesIn, identity=Depends(get_identity)):
    """What a new workspace starting from these packages would get: each package (dependencies first) and
    what it holds. For the form that creates a workspace, before there is one to preview in."""
    try:
        order = installer.resolve(list(dict.fromkeys(["core-facility", *body.packages])))
    except installer.PackageProblem as e:
        raise HTTPException(status_code=422, detail={"error": str(e), "code": "package"})
    return [{**p.describe(), "requested": requested} for p, requested in order]


@router.post("/packages/preview")
def preview_new_workspace(body: PackagesIn, identity: Identity = Depends(get_identity), db: Session = Depends(get_db)):
    """What a new workspace made from these packages would get — each package (dependencies first) with its
    exact version and checksum, and the types, kinds and workflows it would create — worked out in a workspace
    made and rolled back. For the form that creates workspaces (administrators)."""
    if isinstance(identity, PatIdentity) or not identity.user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can create workspaces")
    try:
        plan = installer.plan_new(db, body.packages, catalogue_workspace_id=body.catalogue_workspace_id,
                                  scope=body.scope)
    except installer.PackageProblem as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=_problem(e))
    db.rollback()
    return plan.as_dict()


@router.get("/workspaces/{workspace_id}/capabilities", response_model=CapabilitiesOut)
def workspace_capabilities(workspace_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """What this workspace's packages let it do: which pages to show (equipment, map, beam model, records), its
    map layers, ticket and document kinds, and the importers its packages support."""
    _may_read(db, identity, workspace_id)
    return installer.capabilities(db, workspace_id)


def _history(db: Session, workspace_id: str) -> list[dict]:
    return [{"package_id": h.package_id, "action": h.action, "from_version": h.from_version,
             "to_version": h.to_version, "checksum": h.checksum, "actor": h.actor, "at": h.at,
             "result": h.result} for h in installer.history(db, workspace_id)]


def _upgradable(shipped, version: str) -> bool:
    from packaging.version import InvalidVersion, Version
    if shipped is None:
        return False
    try:
        return Version(shipped.version) > Version(version)
    except InvalidVersion:
        return shipped.version != version


def _rows(db: Session, workspace_id: str, catalog: dict) -> list[dict]:
    rows = []
    for r in installer.installed(db, workspace_id).values():
        shipped = catalog.get(r.package_id)
        rows.append({"package_id": r.package_id, "name": shipped.name if shipped else r.package_id,
                     "version": r.version, "checksum": r.checksum, "options": r.options,
                     "installed_at": r.installed_at, "installed_by": r.installed_by,
                     "shipped_version": shipped.version if shipped else None,
                     "upgrade_available": _upgradable(shipped, r.version),
                     "revert_to": reverter.targets(db, workspace_id, r.package_id)})
    return sorted(rows, key=lambda x: x["package_id"])


@router.get("/workspaces/{workspace_id}/packages")
def workspace_packages(workspace_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Exactly which package versions this workspace uses (with the checksum of what was applied, and how it
    was put in), what newer versions this installation ships, the earlier ones it can go back to, and the
    history."""
    _may_read(db, identity, workspace_id)
    return {"workspace_id": workspace_id, "packages": _rows(db, workspace_id, available()),
            "history": _history(db, workspace_id)}


@router.post("/workspaces/{workspace_id}/packages/preview")
def preview_install(workspace_id: str, body: PackagesIn, identity=Depends(get_identity),
                    db: Session = Depends(get_db)):
    """What installing these packages would do here — install, upgrade or leave unchanged, and what it would
    create and extend — worked out by applying it and rolling it back. Nothing is kept."""
    _may_install(db, identity, workspace_id)
    try:
        plan = installer.plan(db, workspace_id, body.packages, catalogue_workspace_id=body.catalogue_workspace_id,
                              scope=body.scope, decisions=body.decisions)
    except installer.PackageProblem as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=_problem(e))
    db.rollback()
    return plan.as_dict()


@router.post("/workspaces/{workspace_id}/packages/install")
def install_packages(workspace_id: str, body: PackagesIn, identity=Depends(get_identity),
                     db: Session = Depends(get_db)):
    """Install these packages (and what they depend on) in this workspace, all or nothing. Reinstalling the
    version it already has changes nothing."""
    _may_install(db, identity, workspace_id)
    actor = identity.user.id if isinstance(identity, OidcIdentity) else "api-token"
    try:
        plan = installer.install(db, workspace_id, body.packages, actor=actor,
                                 catalogue_workspace_id=body.catalogue_workspace_id, scope=body.scope,
                                 decisions=body.decisions)
    except installer.PackageProblem as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=_problem(e))
    db.commit()
    return {**plan.as_dict(), "history": _history(db, workspace_id)}


def _revert(db: Session, workspace_id: str, body: RevertIn, identity, keep: bool) -> dict:
    _may_install(db, identity, workspace_id)
    actor = identity.user.id if isinstance(identity, OidcIdentity) else "api-token"
    try:
        plan = reverter.run(db, workspace_id, body.package_id, body.checksum, decisions=body.decisions,
                            actor=actor if keep else None, keep=keep)
    except installer.PackageProblem as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=_problem(e))
    if not keep:
        db.rollback()
        return plan.as_dict()
    db.commit()
    return {**plan.as_dict(), "history": _history(db, workspace_id)}


@router.post("/workspaces/{workspace_id}/packages/revert/preview")
def preview_revert(workspace_id: str, body: RevertIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """What going back to an earlier version of a package would do here — what it would remove (each a
    decision: apply or keep), restore and rename back — worked out and rolled back. Nothing is kept."""
    return _revert(db, workspace_id, body, identity, keep=False)


@router.post("/workspaces/{workspace_id}/packages/revert")
def revert_package(workspace_id: str, body: RevertIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Go back to an earlier version of a package this workspace had, with its migration plan; recorded in the
    history. Refused while another package here, or a workspace hanging from this catalogue, needs the newer one."""
    return _revert(db, workspace_id, body, identity, keep=True)


# --------------------------------------------------------------------------- every workspace (administrators)

def _admin(identity) -> None:
    if isinstance(identity, PatIdentity) or not identity.user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")


def _catalogue_first(db: Session, workspace_ids: list[str], package_id: str) -> list[str]:
    """Shared catalogues before the workspaces that hang from them."""
    rows = {r.workspace_id: r for r in installer.installed_everywhere(db, package_id)}
    return sorted(workspace_ids, key=lambda w: (0 if ((rows.get(w) and rows[w].options) or {}).get("scope") == "global"
                                                else 1, w))


@router.get("/admin/packages")
def every_workspace(identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Every workspace's packages, at their versions, with the upgrades this installation ships and the earlier
    versions each can go back to; and, per package, the workspaces behind."""
    _admin(identity)
    catalog = available()
    workspaces = []
    behind: dict[str, list[str]] = {}
    for ws in db.query(Workspace).order_by(Workspace.id):
        rows = _rows(db, ws.id, catalog)
        for r in rows:
            if r["upgrade_available"]:
                behind.setdefault(r["package_id"], []).append(ws.id)
        workspaces.append({"id": ws.id, "name": ws.name, "packages": rows})
    return {"packages": [{"id": p.id, "name": p.name, "version": p.version,
                          "behind": _catalogue_first(db, behind.get(p.id, []), p.id)}
                         for p in sorted(catalog.values(), key=lambda p: p.id)],
            "workspaces": workspaces}


def _everywhere(db: Session, package_id: str, body: EverywhereIn, identity, keep: bool) -> dict:
    _admin(identity)
    shipped = available().get(package_id)
    if shipped is None:
        raise HTTPException(status_code=404, detail="No such package")
    rows = {r.workspace_id: r for r in installer.installed_everywhere(db, package_id)}
    wanted = [w for w, r in rows.items() if _upgradable(shipped, r.version)]
    if body.workspaces is not None:
        wanted = [w for w in wanted if w in set(body.workspaces)]
    actor = identity.user.id
    out = []
    going = set()                            # catalogues upgraded (or ready to be) before what hangs from them
    for ws in _catalogue_first(db, wanted, package_id):
        entry = {"workspace_id": ws, "from_version": rows[ws].version, "to_version": shipped.version}
        try:
            plan = installer.plan(db, ws, [package_id])
            db.rollback()
            undecided = sorted({c for s in plan.steps if s.action == "upgrade"
                                for c in (s.result or {}).get("needs_decision") or []})
            entry["steps"] = [{"package_id": s.package_id, "action": s.action, "from_version": s.from_version,
                               "version": s.version} for s in plan.steps if s.action != "unchanged"]
            if undecided:
                entry.update(status="needs_decisions", decisions=len(undecided))
            elif not keep:
                entry["status"] = "ready"
                going.add(ws)
            else:
                installer.install(db, ws, [package_id], actor=actor)
                db.commit()
                entry["status"] = "upgraded"
                going.add(ws)
        except installer.CatalogueBehind as e:
            db.rollback()
            if not keep and e.catalogue in going:
                entry["status"] = "after_catalogue"  # worked out once its catalogue is upgraded, just before it
            else:
                entry.update(status="refused", error=str(e))
        except installer.PackageProblem as e:
            db.rollback()
            entry.update(status="refused", error=str(e))
        out.append(entry)
    return {"package_id": package_id, "version": shipped.version, "workspaces": out}


@router.post("/admin/packages/{package_id}/upgrade-everywhere/preview")
def preview_everywhere(package_id: str, body: EverywhereIn, identity=Depends(get_identity),
                       db: Session = Depends(get_db)):
    """For each workspace behind on this package: ready (no decision to make), needs decisions (upgrade it on
    its own page), or refused (why). Nothing is changed."""
    return _everywhere(db, package_id, body, identity, keep=False)


@router.post("/admin/packages/{package_id}/upgrade-everywhere")
def upgrade_everywhere(package_id: str, body: EverywhereIn, identity=Depends(get_identity),
                       db: Session = Depends(get_db)):
    """Upgrade this package in every workspace behind on it that has no decision to make, shared catalogues
    first, each workspace on its own (one refused leaves the others upgraded). Those that need a migration
    plan are listed, unchanged."""
    return _everywhere(db, package_id, body, identity, keep=True)
