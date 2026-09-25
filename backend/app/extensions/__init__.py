"""Model extensions (asset-model-revision §5.1, §13 S8).

The revision adds no types. It keeps the triggers of the first revision, the
areas the model will grow into, and lets each one enter only when it has
**an owner, a source and a query**:

* the owner answers for the extension's types and relations;
* the source says where its records come from (ARGUS itself, entered by
  people, is a source);
* the query is the question the extension exists to answer. It ships with
  a fixture and the answer expected on it, and the test suite runs it.

An extension is declared in code, one module per extension in this package,
and reviewed like the rule catalogue. A module defines `EXTENSION`. The
gate (`check`) refuses one that lacks any of the three, adds a type that
exists, hangs a type from a parent the catalogue does not have, or adds a
relation without saying which way a failure travels along it: an
unclassified relation is silently ignored by every root-cause walk.

A declared extension's relations are known to the causal model and the
registry at once. Its types enter a catalogue only when admitted there
(`admit`): the gate runs again, the query runs on its fixture, and the
admission is a decision with its author and reason.
"""
from __future__ import annotations

import importlib
import pkgutil
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

# §5.1: the triggers set in the first revision.
TRIGGERS = {
    "rf-distribution": "RF distribution",
    "diagnostics": "Diagnostics",
    "magnets-undulators": "Magnets and undulators",
    "cabling": "Cabling",
    "network-topology": "Network topology",
    "consoles": "Consoles",
    "stores": "Stores",
    "safety": "Safety",
    "plant-electronics": "Plant and electronics",
    "engineering": "Engineering",
}
ATTRIBUTE_TYPES = {"string", "text", "integer", "float", "boolean", "date", "datetime", "user", "enumeration"}


@dataclass
class ExtType:
    name: str
    parent: str
    description: str
    attributes: list = field(default_factory=list)      # (key, label, type) or (key, label, "enumeration", [options])


@dataclass
class ExtRelation:
    name: str
    layer: str                                          # a causal_model.LAYERS key
    flows: str                                          # forward | reverse | none
    carries: Optional[str]                              # control | function | permit | degradation | None
    note: str
    source_types: Optional[set] = None                  # None: any
    target_types: Optional[set] = None
    at_most_per_source: Optional[int] = None
    at_most_per_target: Optional[int] = None


@dataclass
class ExtQuery:
    name: str
    question: str
    run: Callable                                       # (db, workspace_id) -> list[dict]
    fixture: Callable                                   # (db, workspace_id) -> context, builds records
    expect: Callable                                    # (rows, context) -> bool


@dataclass
class Extension:
    id: str
    trigger: str
    owner: str
    source: str
    summary: str
    query: Optional[ExtQuery]
    types: list = field(default_factory=list)
    relations: list = field(default_factory=list)


class ExtensionError(ValueError):
    pass


def declared() -> list[Extension]:
    """Every extension module in this package, in id order."""
    out = []
    for m in pkgutil.iter_modules(__path__):
        if m.name.startswith("_"):
            continue
        ext = getattr(importlib.import_module(f"{__name__}.{m.name}"), "EXTENSION", None)
        if isinstance(ext, Extension):
            out.append(ext)
    return sorted(out, key=lambda e: e.id)


def by_id(ext_id: str) -> Optional[Extension]:
    return next((e for e in declared() if e.id == ext_id), None)


def check(ext: Extension, others: Optional[list] = None) -> list[str]:
    """What keeps the extension out: empty when the gate passes."""
    from app.services import asset_types, causal_model
    problems = []
    if ext.trigger not in TRIGGERS:
        problems.append(f"'{ext.trigger}' is not one of the triggers (§5.1)")
    if not (ext.owner or "").strip():
        problems.append("it has no owner")
    if not (ext.source or "").strip():
        problems.append("it has no source")
    if ext.query is None or not all(callable(getattr(ext.query, f, None)) for f in ("run", "fixture", "expect")):
        problems.append("it has no query with a fixture and an expected answer")
    others = [o for o in (others if others is not None else declared()) if o.id != ext.id]
    if any(o.id == ext.id for o in others):
        problems.append(f"the id '{ext.id}' is taken")
    base = set(asset_types.BY_NAME)
    taken = base | {t.name for o in others for t in o.types}
    own: set = set()
    for t in ext.types:
        if t.name in taken or t.name in own:
            problems.append(f"the type '{t.name}' exists already")
        if t.parent not in base and t.parent not in own:
            problems.append(f"the type '{t.name}' hangs from '{t.parent}', which the catalogue does not have")
        for a in t.attributes:
            if len(a) < 3 or a[2] not in ATTRIBUTE_TYPES or (a[2] == "enumeration" and len(a) < 4):
                problems.append(f"the type '{t.name}' has an attribute that is not (key, label, type)")
        own.add(t.name)
    known_types = base | own | {t.name for o in others for t in o.types}
    rel_taken = set(causal_model.BASE_SEMANTICS) | {r.name for o in others for r in o.relations}
    for r in ext.relations:
        if r.name.strip().lower() in rel_taken:
            problems.append(f"the relation '{r.name}' exists already")
        if r.layer not in causal_model.LAYERS:
            problems.append(f"the relation '{r.name}' has no known layer")
        if r.flows not in (causal_model.FORWARD, causal_model.REVERSE, causal_model.NONE):
            problems.append(f"the relation '{r.name}' does not say which way a failure travels")
        elif (r.carries is None) != (r.flows == causal_model.NONE) or (
                r.carries is not None and r.carries not in (causal_model.CONTROL, causal_model.FUNCTION,
                                                             causal_model.PERMIT, causal_model.DEGRADATION)):
            problems.append(f"the relation '{r.name}' does not say what a failure takes with it")
        for ends in (r.source_types, r.target_types):
            for n in sorted(ends or ()):
                if n not in known_types:
                    problems.append(f"the relation '{r.name}' names the unknown type '{n}'")
    return problems


def semantics(extensions: Optional[list] = None) -> dict:
    """The causal meaning of every relation declared by an extension that passes the gate."""
    from app.services.causal_model import RelationSemantics
    exts = extensions if extensions is not None else declared()
    return {r.name.strip().lower(): RelationSemantics(r.layer, r.flows, r.carries, note=r.note)
            for e in exts if not check(e, exts) for r in e.relations}


def registry_rules(extensions: Optional[list] = None) -> tuple[dict, dict]:
    exts = extensions if extensions is not None else declared()
    endpoints, cardinality = {}, {}
    for e in exts:
        if check(e, exts):
            continue
        for r in e.relations:
            if r.source_types or r.target_types:
                endpoints[r.name] = (("in", set(r.source_types)) if r.source_types else None,
                                     ("in", set(r.target_types)) if r.target_types else None)
            if r.at_most_per_source or r.at_most_per_target:
                cardinality[r.name] = (r.at_most_per_source, r.at_most_per_target)
    return endpoints, cardinality


def run_fixture(db, ext: Extension) -> dict:
    """The query on its own fixture, in a workspace made for it and thrown
    away: nothing of it stays."""
    from app.models.workspace import Workspace
    ws = f"ext-fixture-{uuid.uuid4().hex[:8]}"
    sp = db.begin_nested()
    try:
        db.add(Workspace(id=ws, name=f"fixture of {ext.id}"))
        db.flush()
        _seed_types(db, ws, ext, is_global=False)
        context = ext.query.fixture(db, ws)
        rows = ext.query.run(db, ws)
        ok = bool(ext.query.expect(rows, context))
        return {"ok": ok, "rows": len(rows)}
    except Exception as exc:                    # a broken query is a gate failure, not a server error
        return {"ok": False, "rows": 0, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        sp.rollback()


def _seed_types(db, workspace_id: str, ext: Extension, *, is_global: bool) -> list[str]:
    """The extension's types, under their parents in this workspace (or the
    shared ones it sees). Existing types are left alone."""
    from sqlalchemy import select
    from app.ledger import engine
    from app.models.schema import Schema
    from app.services.asset_types import _attr
    created = []
    for t in ext.types:
        if db.scalar(select(Schema.uid).where(Schema.workspace_id == workspace_id, Schema.name == t.name,
                                              Schema.applies_to == "objects")):
            continue
        parent = engine.ensure_type(db, workspace_id, t.parent)
        attrs = [_attr(a[0], a[1], a[2], options=a[3] if a[2] == "enumeration" else None) for a in t.attributes]
        db.add(Schema(uid=str(uuid.uuid4()), workspace_id=workspace_id, name=t.name, description=t.description,
                      parent_schema_uid=parent.uid, attributes=attrs, is_global=is_global, applies_to="objects",
                      is_concrete=True, metadata_json={"source": "argus", "extension": ext.id}))
        db.flush()
        created.append(t.name)
    return created


def admissions(db, workspace_id: str) -> dict[str, dict]:
    """extension id -> the decision that admitted it here, unless revoked."""
    from sqlalchemy import select
    from app.ledger import engine
    from app.models.ledger import Decision
    ended = engine._ended(db, workspace_id)
    out = {}
    for d in db.scalars(select(Decision).where(Decision.workspace_id == workspace_id,
                                               Decision.kind == "admit_extension").order_by(Decision.at)):
        if d.decision_id not in ended:
            out[(d.target or {}).get("extension")] = {"decision_id": d.decision_id, "by": d.actor, "at": d.at,
                                                     "reason": d.reason}
    return out


def overview(db, workspace_id: str, *, run_queries: bool = False) -> list[dict]:
    """Each trigger, with the extension declared for it and where it stands."""
    exts = declared()
    admitted = admissions(db, workspace_id)
    rows = []
    for trigger, label in TRIGGERS.items():
        mine = [e for e in exts if e.trigger == trigger]
        entry = {"trigger": trigger, "label": label, "extensions": []}
        for e in mine:
            problems = check(e, exts)
            item = {"id": e.id, "owner": e.owner, "source": e.source, "summary": e.summary,
                    "query": {"name": e.query.name, "question": e.query.question} if e.query else None,
                    "types": [{"name": t.name, "parent": t.parent} for t in e.types],
                    "relations": [{"name": r.name, "layer": r.layer, "flows": r.flows, "carries": r.carries}
                                  for r in e.relations],
                    "problems": problems, "admitted": admitted.get(e.id)}
            if run_queries and not problems:
                item["fixture"] = run_fixture(db, e)
            entry["extensions"].append(item)
        rows.append(entry)
    return rows


def admit(db, workspace_id: str, actor: str, ext_id: str, reason: str) -> dict:
    """Let an extension's types into this catalogue. The caller commits."""
    from app.ledger import engine
    ext = by_id(ext_id)
    if ext is None:
        raise ExtensionError("no such extension is declared")
    if not (reason or "").strip():
        raise ExtensionError("an admission needs a reason")
    if ext_id in admissions(db, workspace_id):
        raise ExtensionError("the extension is admitted here already")
    problems = check(ext)
    if problems:
        raise ExtensionError("the gate refuses it: " + "; ".join(problems))
    fixture = run_fixture(db, ext)
    if not fixture["ok"]:
        raise ExtensionError(f"its query '{ext.query.name}' does not give the expected answer on its fixture"
                             + (f" ({fixture['error']})" if fixture.get("error") else ""))
    created = _seed_types(db, workspace_id, ext, is_global=True)
    d = engine._record_decision(db, "admit_extension", actor, workspace_id, reason=reason,
                                target={"extension": ext.id, "trigger": ext.trigger},
                                value={"owner": ext.owner, "source": ext.source, "types": created,
                                       "relations": [r.name for r in ext.relations], "query": ext.query.name})
    return {"extension": ext.id, "types": created, "decision_id": d.decision_id}


def run_query(db, workspace_id: str, ext_id: str) -> dict:
    """The extension's question, asked of a workspace whose catalogue admitted it."""
    from app.services.asset_types import catalogue_of
    ext = by_id(ext_id)
    if ext is None:
        raise ExtensionError("no such extension is declared")
    if ext_id not in admissions(db, catalogue_of(db, workspace_id) or workspace_id):
        raise ExtensionError("the extension is not admitted in this workspace's catalogue")
    return {"extension": ext.id, "query": ext.query.name, "question": ext.query.question,
            "rows": ext.query.run(db, workspace_id)}
