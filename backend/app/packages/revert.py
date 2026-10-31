"""Taking a workspace back to a version of a package it had before: previewed, applied with a migration plan,
recorded — an upgrade run the other way.

Every version a workspace was given is kept (`PackageSnapshot`, by checksum). A revert compares what the
workspace has now with that earlier version, through the same machinery as an upgrade (app/packages/upgrade.py):
what the newer version added is a removal now, so it needs a decision — `apply` (gone again; the values
records hold under a removed field are kept) or `keep`; what it relabelled goes back by itself where the
workspace did not change it; a type it withdrew is offered again; a field it renamed is renamed back, its
values moved with it.

A revert is refused, before anything changes, when it would leave the workspace inconsistent: another package
here needs the newer version, or a workspace hanging from this one (when it is the shared catalogue) has the
newer version. The installation's packages stay as they ship: after a revert, the newer version is an upgrade
again.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Optional

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.package import PackageSnapshot, WorkspacePackage
from app.models.workspace import Workspace
from app.packages.install import PackageProblem, Plan, Step, _record, history, installed
from app.packages.model import Package


def _older(a: str, b: str) -> bool:
    try:
        return Version(a) < Version(b)
    except InvalidVersion:
        return False


def targets(db: Session, workspace_id: str, package_id: str) -> list[dict]:
    """The earlier versions of a package this workspace had, whose definitions are kept: newest first."""
    row = installed(db, workspace_id).get(package_id)
    if row is None:
        return []
    kept = {s.checksum: s.version for s in db.scalars(select(PackageSnapshot).where(
        PackageSnapshot.package_id == package_id))}
    seen: dict[str, str] = {}
    for h in history(db, workspace_id):
        if h.package_id == package_id and h.checksum in kept and h.checksum != row.checksum \
                and _older(h.to_version, row.version):
            seen[h.checksum] = h.to_version
    return [{"version": v, "checksum": c}
            for c, v in sorted(seen.items(), key=lambda kv: Version(kv[1]), reverse=True)]


def _package(snap: PackageSnapshot) -> Package:
    m = snap.manifest or {}
    return Package(id=snap.package_id, version=snap.version, name=m.get("name") or snap.package_id,
                   description=m.get("description") or "", owner=m.get("owner") or "",
                   depends=dict(m.get("depends") or {}), provides=list(m.get("provides") or []),
                   path=Path("."), checksum=snap.checksum, sections=copy.deepcopy(snap.sections or {}))


def _renames_back(target: Package, current: dict) -> None:
    """A field the newer version renamed (`renamed_from`) is renamed back: the earlier definition is told it
    was the newer one's, so its values move with it instead of being left under a removed key."""
    now = {t["name"]: t for t in (current.get("object_types") or {}).get("types") or []}
    for t in (target.sections.get("object_types") or {}).get("types") or []:
        newer = now.get(t["name"])
        if newer is None:
            continue
        back = {a["renamed_from"]: a["key"] for a in newer.get("attributes") or [] if a.get("renamed_from")}
        for a in t.get("attributes") or []:
            if a.get("key") in back:
                a["renamed_from"] = back[a["key"]]


def _snapshot(db: Session, package_id: str, checksum: str) -> Optional[PackageSnapshot]:
    return db.scalar(select(PackageSnapshot).where(PackageSnapshot.package_id == package_id,
                                                   PackageSnapshot.checksum == checksum))


def blockers(db: Session, workspace_id: str, package_id: str, version: str) -> list[str]:
    """Why this workspace cannot go back to `version` of the package, or nothing."""
    out = []
    for pid, r in installed(db, workspace_id).items():
        if pid == package_id:
            continue
        snap = _snapshot(db, pid, r.checksum)
        depends = ((snap.manifest or {}).get("depends") if snap else None) or {}
        spec = depends.get(package_id)
        if spec is None or str(spec).strip() in ("", "*"):
            continue
        try:
            if Version(version) not in SpecifierSet(str(spec)):
                out.append(f"{pid} {r.version} needs {package_id} {spec}")
        except (InvalidSpecifier, InvalidVersion):
            continue
    for r in db.scalars(select(WorkspacePackage).where(WorkspacePackage.package_id == package_id,
                                                       WorkspacePackage.workspace_id != workspace_id)):
        if (r.options or {}).get("catalogue_workspace_id") == workspace_id and _older(version, r.version):
            out.append(f"workspace {r.workspace_id} hangs from this catalogue with {package_id} {r.version}: "
                       f"revert it first")
    return out


def run(db: Session, workspace_id: str, package_id: str, checksum: str, *, decisions: Optional[dict] = None,
        actor: Optional[str] = None, keep: bool) -> Plan:
    """Preview (keep=False: applied and rolled back) or carry out the revert. The caller commits."""
    from app.packages import upgrade
    if db.get(Workspace, workspace_id) is None:
        raise PackageProblem(f"no workspace {workspace_id!r}")
    row = installed(db, workspace_id).get(package_id)
    if row is None:
        raise PackageProblem(f"workspace {workspace_id} does not have {package_id}")
    if checksum not in {t["checksum"] for t in targets(db, workspace_id, package_id)}:
        raise PackageProblem(f"{package_id}: that is not an earlier version this workspace had (or its definitions "
                             f"were not kept), so it cannot go back to it")
    snap = _snapshot(db, package_id, checksum)
    target = _package(snap)
    blocked = blockers(db, workspace_id, package_id, target.version)
    if blocked:
        raise PackageProblem(f"{package_id} cannot go back to {target.version} here: " + "; ".join(blocked))
    current = _snapshot(db, package_id, row.checksum)
    if current is not None:
        _renames_back(target, current.sections or {})
    step = Step(package_id, target.version, target.checksum, "revert", row.version, True)
    options = dict(row.options or {})
    savepoint = db.begin_nested()
    try:
        step.result = upgrade.apply(db, workspace_id, target, decisions) if keep else \
            upgrade.preview(db, workspace_id, target, decisions)
        if keep:
            _record(db, workspace_id, target, "revert", row.version, options, step.result, actor)
        db.flush()
    except upgrade.PlanProblem as e:
        savepoint.rollback()
        raise PackageProblem(str(e)) from None
    except Exception:
        savepoint.rollback()
        raise
    if keep:
        savepoint.commit()
    else:
        savepoint.rollback()
    return Plan(workspace_id, [step], options)
