"""The type catalogue as one map: every object type a workspace can use, where it sits in the tree, what it
says it is, what its records hold (own and inherited), the names imports call it by, what its references
mean in the graph, and how many records of it this workspace has.

It describes the types a workspace sees (its own, and the shared ones it has no own copy of), so the same
page answers "what is a Turbo Pump here, and what does it carry" in any workspace.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.schema import Schema

BRANCHES = {                                     # the catalogue's top branches, for the page's filters
    "Asset": "equipment", "Equipment Port": "equipment", "Functional Element": "functional",
    "Control Item": "control", "Catalog Item": "catalogue", "Location": "locations", "IT Record": "it",
    "Engineering Record": "engineering",
}


def _attr_view(a: dict, origin: str, ref_names: dict, relations: dict) -> dict:
    key = a.get("key") or a.get("name")
    ref = a.get("referenceType") or ref_names.get(a.get("referenceSchemaUid"))
    return {"key": key, "name": a.get("name") or key, "type": a.get("type") or "string", "origin": origin,
            "required": bool(a.get("required")), "multi": bool(a.get("multiValue")), "unique": bool(a.get("unique")),
            "options": [o.get("value") for o in a.get("options") or []], "refers_to": ref,
            "relation": relations.get(key) if a.get("type") == "reference" else None}


def catalogue(db: Session, workspace_id: str) -> dict:
    from app.services.asset_types import REFERENCE_RELATIONS
    rows = list(db.scalars(select(Schema).where(
        Schema.applies_to == "objects", or_(Schema.workspace_id == workspace_id, Schema.is_global.is_(True)))))
    # One type per name: the workspace's own where it has one, else the shared one.
    by_name: dict[str, Schema] = {}
    for s in sorted(rows, key=lambda s: s.workspace_id != workspace_id):
        by_name.setdefault(s.name, s)
    visible = {s.uid: s for s in by_name.values()}
    every = {s.uid: s for s in rows}
    ref_names = {s.uid: s.name for s in rows}

    counts = Counter(dict(db.execute(select(Asset.schema_uid, func.count()).where(
        Asset.workspace_id == workspace_id, Asset.deleted_at.is_(None),
        Asset.record_status.notin_(("Retired", "Merged"))).group_by(Asset.schema_uid)).all()))

    def parent_of(s: Schema) -> Optional[Schema]:
        p = every.get(s.parent_schema_uid) if s.parent_schema_uid else None
        if p is None and s.parent_schema_uid:
            p = db.get(Schema, s.parent_schema_uid)
        return p

    def chain(s: Schema) -> list[Schema]:
        out, seen, cur = [], set(), s
        while cur is not None and cur.uid not in seen:
            out.append(cur)
            seen.add(cur.uid)
            cur = parent_of(cur)
        return out

    types = []
    for s in visible.values():
        lineage = chain(s)
        names = [x.name for x in lineage]
        attrs: dict[str, dict] = {}
        for ancestor in reversed(lineage):                        # root first; a child overrides in place
            for a in ancestor.attributes or []:
                k = a.get("key") or a.get("name")
                if k:
                    attrs[k] = _attr_view(a, ancestor.name, ref_names, REFERENCE_RELATIONS)
        branch = next((BRANCHES[n] for n in names if n in BRANCHES), "other")
        types.append({
            "uid": s.uid, "name": s.name, "description": s.description, "parent": names[1] if len(names) > 1 else None,
            "path": list(reversed(names)), "branch": branch, "abstract": s.is_concrete is False,
            "shared": s.workspace_id != workspace_id, "owner_workspace": s.workspace_id, "is_global": s.is_global,
            "icon_uid": s.icon_uid, "aliases": (s.metadata_json or {}).get("aliases") or [],
            "attributes": list(attrs.values()), "records": counts.get(s.uid, 0),
        })
    # Records of a type and of every type below it, as the type tree counts them.
    children: dict[str, list[str]] = {}
    for t in types:
        if t["parent"]:
            children.setdefault(t["parent"], []).append(t["name"])
    by = {t["name"]: t for t in types}

    def total(name: str, seen=None) -> int:
        seen = seen or set()
        if name in seen:
            return 0
        seen.add(name)
        return by[name]["records"] + sum(total(c, seen) for c in children.get(name, []) if c in by)
    for t in types:
        t["records_with_subtypes"] = total(t["name"])

    from app.services import equipment_classes as ec
    classes = [{"name": c.name, "status": c.status, "promoted_type": c.promoted_type, "note": c.note}
               for c in ec.vocabulary(db)]
    return {"types": sorted(types, key=lambda t: t["path"]), "equipment_classes": classes,
            "branches": sorted(set(BRANCHES.values()) | {"other"})}
