"""The system catalogue: which workspace is the installation's catalogue of Vendors and Product Models, what
it may hold, and what it refuses (docs/system-catalogue.md).

One workspace carries `role = catalogue`. Every workspace reads its models; units stay in workspaces and point
at them. It is protected: it cannot be deleted, transferred, exported as a workspace bundle, or made to hang
from another, and it holds Vendors and Product Models only — a unit put there would belong to no workspace.
Its shared types are managed by its packages, as before.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace

ROLE = "catalogue"
RECORD_TYPES = ("Vendor", "Product Model")


class CatalogueProtected(ValueError):
    """What the catalogue workspace refuses."""


def designated(db: Session) -> Optional[str]:
    """The catalogue workspace's id, or None when none is designated."""
    return db.scalar(select(Workspace.id).where(Workspace.role == ROLE))


def is_catalogue(db: Session, workspace_id: Optional[str]) -> bool:
    from app.catalogue import install
    return bool(workspace_id) and install.catalogue_workspace(db) == workspace_id


def refuse(db: Session, workspace_id: Optional[str], what: str) -> None:
    """Raise when `workspace_id` is the catalogue, which cannot be `what`."""
    if is_catalogue(db, workspace_id):
        raise CatalogueProtected(f"{workspace_id} is the installation's catalogue: it cannot be {what} "
                                 f"(docs/system-catalogue.md)")


def check_record(db: Session, workspace_id: str, type_name: str) -> None:
    """The catalogue holds Vendors and Product Models only."""
    if type_name not in RECORD_TYPES and is_catalogue(db, workspace_id):
        raise CatalogueProtected(f"{workspace_id} is the installation's catalogue: it holds Vendors and Product "
                                 f"Models only. A {type_name} belongs in a workspace, pointing at its model")


def designate(db: Session, workspace_id: str) -> None:
    """Make `workspace_id` the catalogue. Refused while another is, or while it holds other records."""
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise CatalogueProtected(f"no workspace {workspace_id!r}")
    current = designated(db)
    if current == workspace_id:
        return
    if current is not None:
        raise CatalogueProtected(f"{current} is already the installation's catalogue")
    others = _other_records(db, workspace_id)
    if others:
        raise CatalogueProtected(f"{workspace_id} holds records that are not Vendors or Product Models "
                                 f"({', '.join(f'{n} {t}' for t, n in others[:5])}): move them to a workspace first")
    ws.role = ROLE
    db.flush()


def designate_if_none(db: Session, workspace_id: str) -> bool:
    """The first workspace given the object catalogue as the one others hang from becomes the catalogue, when
    none is designated and it holds nothing else. Returns whether it did."""
    if designated(db) is not None or _other_records(db, workspace_id):
        return False
    db.get(Workspace, workspace_id).role = ROLE
    db.flush()
    return True


def _other_records(db: Session, workspace_id: str) -> list[tuple[str, int]]:
    from app.models.asset import Asset
    return [(t, n) for t, n in db.execute(
        select(Asset.type, func.count()).where(Asset.workspace_id == workspace_id, Asset.type.notin_(RECORD_TYPES))
        .group_by(Asset.type).order_by(func.count().desc()))]


def status(db: Session) -> dict:
    """What the catalogue is, holds and has depending on it. Read-only."""
    from app.models.asset import Asset
    from app.models.package import WorkspacePackage
    from app.models.schema import Schema
    ws = designated(db)
    candidates = list(db.scalars(select(Schema.workspace_id).where(
        Schema.name == "Asset", Schema.applies_to == "objects", Schema.is_global.is_(True)).distinct()))
    out: dict = {"designated": ws, "candidates": sorted(candidates)}
    if ws is None:
        return out
    w = db.get(Workspace, ws)
    out["name"] = w.name
    out["records"] = {t: n for t, n in db.execute(
        select(Asset.type, func.count()).where(Asset.workspace_id == ws).group_by(Asset.type))}
    out["other_records"] = dict(_other_records(db, ws))
    out["not_shared"] = db.scalar(select(func.count()).select_from(Asset).where(
        Asset.workspace_id == ws, Asset.type.in_(RECORD_TYPES), Asset.is_global.is_(False)))
    out["shared_types"] = db.scalar(select(func.count()).select_from(Schema).where(
        Schema.workspace_id == ws, Schema.is_global.is_(True)))
    out["own_types"] = db.scalar(select(func.count()).select_from(Schema).where(
        Schema.workspace_id == ws, Schema.is_global.is_(False)))
    hanging: dict[str, list[str]] = {}
    for r in db.scalars(select(WorkspacePackage)):
        if (r.options or {}).get("catalogue_workspace_id") == ws:
            hanging.setdefault(r.workspace_id, []).append(r.package_id)
    out["hanging"] = {k: sorted(v) for k, v in sorted(hanging.items())}
    models = select(Asset.uid).where(Asset.workspace_id == ws, Asset.type == "Product Model").scalar_subquery()
    units = db.execute(select(Asset.workspace_id, func.count()).where(
        Asset.workspace_id != ws, Asset.attributes["product_model"].astext.in_(models))
        .group_by(Asset.workspace_id)).all()
    out["units"] = {w_: n for w_, n in sorted(units)}
    from app.catalogue.install import installed
    out["collections"] = {c: r.version for c, r in sorted(installed(db, ws).items())}
    return out


# --------------------------------------------------------------------------- the backstop

def _guard_flush(session, flush_context, instances) -> None:
    """Whatever writes it — the API, an import, a script — a record that is not a Vendor or a Product Model is
    refused in the catalogue workspace, when created there or retyped there."""
    from sqlalchemy import inspect as sa_inspect

    from app.models.asset import Asset
    touched = [o for o in session.new if isinstance(o, Asset) and o.type not in RECORD_TYPES]
    for o in session.dirty:
        if isinstance(o, Asset) and o.type not in RECORD_TYPES:
            state = sa_inspect(o)
            if state.attrs.type.history.has_changes() or state.attrs.workspace_id.history.has_changes():
                touched.append(o)
    if not touched:
        return
    with session.no_autoflush:
        ws = session.scalar(select(Workspace.id).where(Workspace.role == ROLE))
    for o in touched:
        if ws is not None and o.workspace_id == ws:
            raise CatalogueProtected(f"{ws} is the installation's catalogue: it holds Vendors and Product Models "
                                     f"only. A {o.type} belongs in a workspace, pointing at its model")


def install_guard() -> None:
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    if not event.contains(Session, "before_flush", _guard_flush):
        event.listen(Session, "before_flush", _guard_flush)


install_guard()
