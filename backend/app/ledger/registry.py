"""The relation registry in warn mode (asset-model-revision §6, §13 S3b).

Every edge is checked against the registry: deprecated verbs, the types
its ends may have, its cardinality (at any instant for derived edges), the
relations that must stay acyclic, and edges to retired or merged records.
In warn mode nothing is refused; the report is what stewards triage, and
the legacy migration's I-MIG-5 compares it before and after a plan.

Only the entries whose constraints are unambiguous are checked; the others
are listed as unchecked so the report says what it did not look at.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger.engine import ACCESS_POINT, INSTALLABLE, INSTALLATION
from app.models.asset import Asset, Relation

MODE = "warn"
POS = INSTALLABLE
CONTROL = {"Control Device", "IOC"}
NOT_EQUIPMENT = POS | CONTROL | {INSTALLATION, ACCESS_POINT, "Location", "Facility", "Section", "Area",
                                 "Machine Module", "Product Model", "Work Package", "Equipment Port"}
DEPRECATED = {"replaced", "carried by", "on line", "spare for"}

# name: (source rule, target rule); a rule is ("in", types) or ("not in", types) or None.
ENDPOINTS = {
    "installed at": (("in", {INSTALLATION}), ("in", POS)),
    "installation of": (("in", {INSTALLATION}), ("not in", NOT_EQUIPMENT)),
    "realized by": (("in", POS), ("not in", NOT_EQUIPMENT)),
    "assigned to": (("in", {ACCESS_POINT}), ("in", POS)),
    "powers": (("in", POS), ("not in", {INSTALLATION, ACCESS_POINT})),
    "acts on": (("in", CONTROL), ("not in", {INSTALLATION, ACCESS_POINT})),
    "port of": (("in", {"Equipment Port"}), ("not in", NOT_EQUIPMENT - {"Equipment Port"})),
    "runs on": (("in", {"IOC"}), None),
    "part of": (None, ("not in", {"Location"})),
}
# name: (at most per source, at most per target); None is unbounded.
CARDINALITY = {
    "installed at": (1, None),
    "installation of": (1, None),
    "realized by": (1, 1),
    "assigned to": (1, None),
    "part of": (1, None),
    "composed of": (None, 1),
    "runs on": (1, None),
}
ACYCLIC = {"part of", "composed of"}
# Edges that may keep pointing at a retired record (history of the retired thing itself).
RETIRE_EXEMPT_SOURCES = {INSTALLATION}


def _ok(rule, type_name: str) -> bool:
    if rule is None:
        return True
    op, types = rule
    return type_name in types if op == "in" else type_name not in types


def _gone(a: Asset) -> bool:
    return a.record_status == "Retired" or a.merged_into_uid is not None or a.deleted_at is not None


def report(db: Session, workspace_ids: Iterable[str], detail_limit: int = 200) -> dict:
    ws = list(set(workspace_ids))
    rels = list(db.scalars(select(Relation).join(Asset, Asset.uid == Relation.from_asset_uid)
                           .where(Asset.workspace_id.in_(ws))))
    uids = {r.from_asset_uid for r in rels} | {r.to_asset_uid for r in rels}
    records = {a.uid: a for a in db.scalars(select(Asset).where(Asset.uid.in_(uids)))} if uids else {}
    violations: list[dict] = []

    def add(rule: str, r: Optional[Relation], message: str, **extra):
        violations.append({"rule": rule, "relation": r.relation_type if r else extra.pop("relation", None),
                           "from": r.from_asset_uid if r else None, "to": r.to_asset_uid if r else None,
                           "message": message, **extra})

    per_source, per_target, graph = Counter(), Counter(), defaultdict(lambda: defaultdict(set))
    for r in rels:
        a, b = records.get(r.from_asset_uid), records.get(r.to_asset_uid)
        if a is None or b is None:
            add("dangling", r, "an end of the relation does not exist")
            continue
        name = r.relation_type
        if name in DEPRECATED or (name == "assigned to" and b.type == "Work Package"):
            add("deprecated", r, f"'{name}' is deprecated; the legacy migration rewrites it")
        ends = ENDPOINTS.get(name)
        if ends and not _ok(ends[0], a.type):
            add("source_type", r, f"'{name}' cannot start at a {a.type}")
        if ends and not _ok(ends[1], b.type):
            add("target_type", r, f"'{name}' cannot point to a {b.type}")
        if _gone(b) and not _gone(a) and a.type not in RETIRE_EXEMPT_SOURCES:
            add("retired_end", r, f"'{name}' points to a retired or merged record")
        if name in CARDINALITY:
            per_source[(name, r.from_asset_uid)] += 1
            per_target[(name, r.to_asset_uid)] += 1
        if name in ACYCLIC:
            graph[name][r.from_asset_uid].add(r.to_asset_uid)

    for (name, uid), n in per_source.items():
        limit = CARDINALITY[name][0]
        if limit is not None and n > limit:
            add("cardinality", None, f"{n} '{name}' edges from one record (at most {limit})", relation=name, record=uid)
    for (name, uid), n in per_target.items():
        limit = CARDINALITY[name][1]
        if limit is not None and n > limit:
            add("cardinality", None, f"{n} '{name}' edges to one record (at most {limit})", relation=name, record=uid)

    for name, edges in graph.items():
        seen, on_path = set(), set()

        def visit(u) -> bool:
            if u in on_path:
                return True
            if u in seen:
                return False
            seen.add(u)
            on_path.add(u)
            cyclic = any(visit(v) for v in edges.get(u, ()))
            on_path.discard(u)
            return cyclic

        for start in list(edges):
            if start not in seen and visit(start):
                add("cycle", None, f"'{name}' contains a cycle", relation=name, record=start)

    counts = Counter(v["rule"] for v in violations)
    by_relation = Counter(v["relation"] for v in violations)
    return {"mode": MODE, "workspaces": sorted(ws), "relations": len(rels), "total": len(violations),
            "counts": dict(counts), "by_relation": dict(by_relation),
            "checked": sorted(set(ENDPOINTS) | set(CARDINALITY) | ACYCLIC | DEPRECATED),
            "violations": violations[:detail_limit]}


def compare(before: dict, after: dict) -> dict:
    """I-MIG-5: the number of violations must not grow. A rule that grew
    while the total fell is reported, not failed: fixing one kind of edge
    can expose another."""
    rules = set(before.get("counts", {})) | set(after.get("counts", {}))
    grew = {r: [before.get("counts", {}).get(r, 0), after.get("counts", {}).get(r, 0)] for r in sorted(rules)
            if after.get("counts", {}).get(r, 0) > before.get("counts", {}).get(r, 0)}
    return {"ok": after.get("total", 0) <= before.get("total", 0), "before": before.get("total", 0),
            "after": after.get("total", 0), "grew": grew}
