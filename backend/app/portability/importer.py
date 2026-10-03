"""Load a verified checkpoint: dry run, staged idempotent load, rebuild, reconciliation, finalize.

Deterministic throughout. Every row an import writes is recorded in the row map by its key in the
archive (sequenced rows: the exporting instance's `seq`) and its key here, so that

* the same commit imported again changes nothing (identical rows are skipped and mapped);
* an interrupted import resumes from its last finished chunk (`checkpoints`);
* a staged import is discarded exactly, audit rows included, leaving active state as it was;
* an increment updates only rows the same origin wrote and nobody here has changed since.

Outcomes per row:

  identical            skip
  new                  create
  same key, same origin, unchanged here     update (an increment of the same chain)
  same key, divergent  block — never overwritten
  identity / types     a person already known is kept as is; a type that differs is a catalogue
                       conflict to review, never overwritten
  missing reference    block, or by decision `unresolved_references: defer` left unresolved and
                       listed in the reconciliation

Projections are never loaded: the importer replays bindings and stream heads from events, rebuilds
fact state, derived relations and conflicts with the ledger engine, and then compares the result
with the projections the export carried (`reconcile`).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.orm import Session

from app.db import Base
from app.ledger.writer import writing
from app.models.attachment import file_sha256
from app.models.ledger import (ClaimEvent, Conflict, ConflictEvent, Decision, IdentityBinding, IdentityEvent,
                               RecordEvent, RevisionEvent, SourceRevision, StatusEvent, StreamHead)
from app.models.portability import PortabilityChainLink, PortabilityRowMap
from app.models.workspace import Workspace
from app.portability import chunks
from app.portability.families import BY_NAME, FAMILIES, GROUP_ORDER, Family, Scope, from_json, to_json

LOAD_GROUPS = ("catalogue", "identity", "access", "governance", "records", "ledger")
GOVERNANCE = ("policies", "rulesets")
REFERENCE_ONLY = ("identities",)              # never updated, never compared as a failure
EVENT_TABLES = (ClaimEvent, RevisionEvent, Decision, StatusEvent, IdentityEvent, RecordEvent, ConflictEvent)


class ImportBlocked(ValueError):
    def __init__(self, message: str, code: str = "blocked", detail: Optional[dict] = None):
        super().__init__(message)
        self.code, self.detail = code, detail or {}


@dataclass
class Plan:
    import_id: str
    origin: str
    mode: str                                  # restore | clone | merge | selective | evidence
    checkpoint: Path
    manifest: dict
    blob_dir: Path
    attachments_dir: Path
    decisions: dict = field(default_factory=dict)

    @property
    def ws_map(self) -> dict:
        return dict(self.decisions.get("workspace_map") or {})

    def map_ws(self, ws):
        return self.ws_map.get(ws, ws) if isinstance(ws, str) else ws

    def unmap_ws(self, ws):
        rev = {v: k for k, v in self.ws_map.items()}
        return rev.get(ws, ws) if isinstance(ws, str) else ws

    def families(self, groups=LOAD_GROUPS) -> list[Family]:
        out = [f for g in groups for f in FAMILIES if f.group == g and f.name in self.manifest["families"]]
        # Workspaces first: types, records and streams all belong to one.
        out.sort(key=lambda f: f.name != "workspaces")
        if self.mode in ("merge", "selective") and self.decisions.get("governance") != "load":
            out = [f for f in out if f.name not in GOVERNANCE]
        return out

    @property
    def workspaces(self) -> list[str]:
        return [self.map_ws(w) for w in self.manifest["workspaces"]]


_MODELS = {m.class_.__table__.name: m.class_ for m in Base.registry.mappers if hasattr(m.class_, "__table__")}


def archive_rows(plan: Plan, fam: Family) -> Iterator[tuple[str, str, dict]]:
    for c in plan.manifest["families"][fam.name]["chunks"]:
        for key, row in chunks.read_chunk(plan.checkpoint / c["file"], fam.name):
            yield c["file"], key, row


def _attr(fam: Family, column: str) -> str:
    for prop in fam.model.__mapper__.column_attrs:
        if prop.columns[0].name == column:
            return prop.key
    return column


def _mapped_row(plan: Plan, fam: Family, row: dict) -> dict:
    """An archive row with this instance's workspace ids."""
    out = dict(row)
    for col in ("workspace_id",):
        if col in out:
            out[col] = plan.map_ws(out[col])
    if fam.name == "workspaces":
        out["id"] = plan.map_ws(out["id"])
    if fam.name == "rulesets" and out.get("scope") != "*":
        out["scope"] = plan.map_ws(out.get("scope"))
    return out


def archive_form(plan: Plan, fam: Family, obj, key: str) -> dict:
    """A local row as the exporter would have written it, in the archive's workspace ids."""
    row = {c: to_json(getattr(obj, _attr(fam, c))) for c in fam.columns}
    for col, kind in fam.blobs.items():
        v = getattr(obj, _attr(fam, col))
        if v is None:
            row[col] = None
        elif kind == "file":
            digest = file_sha256(v)
            row[col] = f"sha256:{digest}" if digest else None
        else:
            row[col] = f"sha256:{hashlib.sha256(bytes(v)).hexdigest()}"
    if fam.sequenced:
        row["seq"] = int(key)
    for col in ("workspace_id",):
        if col in row:
            row[col] = plan.unmap_ws(row[col])
    if fam.name == "workspaces":
        row["id"] = plan.unmap_ws(row["id"])
    if fam.name == "rulesets" and row.get("scope") != "*":
        row["scope"] = plan.unmap_ws(row.get("scope"))
    return row


def _digest(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()


def find_local(db: Session, plan: Plan, fam: Family, key: str, row: dict):
    """The local row that holds this archive row, if any."""
    rm = db.scalar(select(PortabilityRowMap).where(PortabilityRowMap.origin == plan.origin,
                                                   PortabilityRowMap.family == fam.name,
                                                   PortabilityRowMap.source_key == key))
    if fam.sequenced:
        if rm is not None:
            return db.get(fam.model, int(rm.local_key)), rm
        if fam.name == "decisions":            # a decision is globally unique by its id
            return db.scalar(select(Decision).where(Decision.decision_id == row["decision_id"])), None
        return None, None
    mapped = _mapped_row(plan, fam, row)
    pk = [c.name for c in fam.model.__table__.primary_key.columns]
    if set(pk) <= set(fam.key):
        ident = tuple(from_json(fam.model, c, mapped[c]) for c in pk)
        return db.get(fam.model, ident[0] if len(ident) == 1 else ident), rm
    conds = []
    for c in fam.key:
        col = fam.model.__table__.columns[c]
        v = from_json(fam.model, c, mapped.get(c))
        conds.append(col.is_(None) if v is None else col == v)
    return db.scalar(select(fam.model).where(and_(*conds)).limit(1)), rm


def _blob_value(plan: Plan, kind: str, value):
    if value is None:
        return None
    if not (isinstance(value, str) and value.startswith("sha256:")):
        raise ImportBlocked(f"a blob reference is malformed: {str(value)[:40]}", "malformed")
    digest = value[len("sha256:"):]
    src = plan.blob_dir / digest
    if not src.is_file():
        raise ImportBlocked(f"blob sha256:{digest} was not fetched into quarantine", "missing_artifact")
    if kind == "bytes":
        return src.read_bytes()
    dest = plan.attachments_dir / "portable" / digest[:2] / digest
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    return str(dest)


def _values(plan: Plan, fam: Family, row: dict, *, with_deferred: bool) -> dict:
    mapped = _mapped_row(plan, fam, row)
    out = {}
    for c in fam.columns:
        if c in fam.deferred and not with_deferred:
            continue
        if fam.sequenced and c == "seq":
            continue
        v = mapped.get(c)
        out[_attr(fam, c)] = (_blob_value(plan, fam.blobs[c], v) if c in fam.blobs else from_json(fam.model, c, v))
    if fam.name == "workspaces":
        out["import_state"] = "staging"
    return out


def _missing_refs(db: Session, fam: Family, values: dict, pending: dict) -> list[tuple[str, str]]:
    """Foreign keys whose target is neither here nor in this import."""
    out = []
    for col in fam.model.__table__.columns:
        attr = _attr(fam, col.name)
        v = values.get(attr)
        if v is None or not col.foreign_keys:
            continue
        if fam.name == "types" and col.name == "workspace_id":
            continue                            # a shared type's owner comes as a stub (_ensure_owner)
        for fk in col.foreign_keys:
            target = _MODELS.get(fk.column.table.name)
            if target is None or v in pending.get(fk.column.table.name, ()):
                continue
            if db.get(target, v) is None:
                out.append((col.name, f"{fk.column.table.name}:{v}"))
    return out


# --------------------------------------------------------------------------- dry run

def dry_run(db: Session, plan: Plan) -> dict:
    """What executing would do, row by row, without writing anything."""
    counts: dict = defaultdict(lambda: defaultdict(int))
    blocking: list = []
    catalogue: list = []
    candidates: list = []
    refs: list = []
    identity_notes: list = []
    pending = _pending_keys(plan)
    for fam in plan.families():
        for _, key, row in archive_rows(plan, fam):
            local, rm = find_local(db, plan, fam, key, row)
            if local is None:
                missing = _missing_refs(db, fam, _values_for_check(plan, fam, row), pending)
                if missing:
                    refs.append({"family": fam.name, "key": key, "missing": missing})
                    counts[fam.name]["unresolved_reference"] += 1
                else:
                    counts[fam.name]["create"] += 1
                if fam.name == "assets":
                    candidates += _candidates(db, row)
                continue
            if archive_form(plan, fam, local, key) == row:
                counts[fam.name]["identical"] += 1
                continue
            if fam.name in REFERENCE_ONLY:
                counts[fam.name]["known_identity"] += 1
                identity_notes.append({"user": key, "note": "known here with other details; kept as is"})
                continue
            if rm is not None and rm.content_sha256 == _digest(archive_form(plan, fam, local, key)):
                counts[fam.name]["update_same_origin"] += 1
                continue
            counts[fam.name]["divergent"] += 1
            item = {"family": fam.name, "key": key, "reason": "same key, different content, not from this chain"}
            (catalogue if fam.name == "types" else blocking).append(item)
    unresolved = refs if (plan.decisions.get("unresolved_references") or "block") == "block" else []
    governance = [f for f in GOVERNANCE if f in plan.manifest["families"] and f not in [x.name for x in plan.families()]]
    workspaces = []
    for w in plan.manifest["workspaces"]:
        local_ws = plan.map_ws(w)
        here = db.get(Workspace, local_ws)
        if here is not None and plan.mode in ("restore", "clone", "selective") and \
                not _ours(db, plan, "workspaces", w):
            blocking.append({"family": "workspaces", "key": w,
                             "reason": f"workspace {local_ws} already exists here; map it to another id or merge"})
        workspaces.append({"archive": w, "local": local_ws, "exists": here is not None})
    chain = chain_status(db, plan)
    if chain.get("problem"):
        blocking.append({"family": "chain", "key": plan.manifest["export_id"], "reason": chain["problem"]})
    return {
        "mode": plan.mode, "export_id": plan.manifest["export_id"], "origin": plan.origin,
        "labels": plan.manifest["labels"], "workspaces": workspaces,
        "families": {k: dict(v) for k, v in counts.items()},
        "blocking": blocking[:200], "blocking_count": len(blocking),
        "catalogue_conflicts": catalogue[:200], "identity_candidates": candidates[:200],
        "unresolved_references": refs[:200], "unresolved_reference_count": len(refs),
        "unresolved_references_outcome": plan.decisions.get("unresolved_references") or "block",
        "identities": identity_notes[:50], "governance_not_loaded": governance, "chain": chain,
        "ready": not blocking and not catalogue and not unresolved,
    }


def _values_for_check(plan: Plan, fam: Family, row: dict) -> dict:
    mapped = _mapped_row(plan, fam, row)
    return {_attr(fam, c): (None if c in fam.blobs else from_json(fam.model, c, mapped.get(c)))
            for c in fam.columns if not (fam.sequenced and c == "seq")}


def _pending_keys(plan: Plan) -> dict:
    """Primary keys this import will bring, by table: references to them are not missing."""
    out: dict = defaultdict(set)
    for fam in plan.families():
        pk = [c.name for c in fam.model.__table__.primary_key.columns]
        if len(pk) != 1 or pk[0] not in fam.key:
            continue
        for _, key, row in archive_rows(plan, fam):
            out[fam.table].add(_mapped_row(plan, fam, row).get(pk[0]))
    return out


def _candidates(db: Session, row: dict) -> list:
    """Records here holding the same immutable external identifier: candidates, never merges."""
    from app.models.asset import Asset
    out = []
    attrs = row.get("attributes") or {}
    for name in ("argus_source_key", "insight_object_id", "serial_number", "serial", "mac"):
        v = attrs.get(name)
        if not v:
            continue
        other = db.scalar(select(Asset.uid).where(Asset.attributes[name].astext == str(v), Asset.uid != row["uid"])
                          .limit(1))
        if other:
            out.append({"archive": row["uid"], "here": other, "identifier": name, "value": str(v)})
    return out


def _ours(db: Session, plan: Plan, family: str, key: str) -> bool:
    return db.scalar(select(func.count()).select_from(PortabilityRowMap).where(
        PortabilityRowMap.origin == plan.origin, PortabilityRowMap.family == family,
        PortabilityRowMap.source_key == key)) > 0


def chain_status(db: Session, plan: Plan) -> dict:
    """Where this export sits in the chain of exports applied here from the same origin."""
    m = plan.manifest
    links = list(db.scalars(select(PortabilityChainLink).where(PortabilityChainLink.origin == plan.origin)
                            .order_by(PortabilityChainLink.position)))
    applied = {l.export_id for l in links}
    if m["export_id"] in applied:
        return {"status": "already_applied", "applied": len(links)}
    if m["mode"] == "incremental":
        base = (m.get("base") or {}).get("export_id")
        if not links:
            return {"status": "out_of_order", "problem": f"increment of {base}, which was never imported here"}
        if links[-1].export_id != base:
            return {"status": "out_of_order",
                    "problem": f"increment of {base}, but the last export applied here from this origin is "
                               f"{links[-1].export_id}: an increment is missing or out of order"}
        if links[-1].watermark_label != m["base"]["watermark"]["label"]:
            return {"status": "out_of_order", "problem": "the base watermark differs from the one applied here"}
        return {"status": "next", "applied": len(links)}
    return {"status": "first" if not links else "new_checkpoint", "applied": len(links)}


# --------------------------------------------------------------------------- execute

def execute(db: Session, plan: Plan, done: set, save: Callable[[set], None],
            stop_after: Optional[int] = None) -> dict:
    """Load the checkpoint chunk by chunk. `done` holds the finished steps; `save` persists them and
    commits. `stop_after` stops after that many steps (tests use it to prove resumption)."""
    report = {"created": 0, "updated": 0, "identical": 0, "deferred": [], "steps": 0}
    pending = _pending_keys(plan)
    steps = 0

    def step(name: str, fn):
        nonlocal steps
        if name in done:
            return
        if stop_after is not None and steps >= stop_after:
            raise InterruptedError(f"stopped before {name}")
        with writing(db):
            fn()
        done.add(name)
        save(done)
        steps += 1
        report["steps"] += 1

    for fam in plan.families():
        for c in plan.manifest["families"][fam.name]["chunks"]:
            step(f"{fam.name}:{c['file']}", lambda fam=fam, c=c: _load_chunk(db, plan, fam, c, pending, report))
        if fam.replace_set and plan.manifest["mode"] == "incremental":
            step(f"{fam.name}:replace", lambda fam=fam: _replace(db, plan, fam))
    # References inside and across families (a document's current revision, a merge survivor, a parent
    # type) once everything they can name is loaded.
    for fam in plan.families():
        if fam.deferred:
            step(f"{fam.name}:deferred", lambda fam=fam: _deferred(db, plan, fam, pending, report))
    return report


def _remember(db: Session, plan: Plan, fam: Family, key: str, local_key: str, created: bool, form: dict) -> None:
    rm = db.scalar(select(PortabilityRowMap).where(PortabilityRowMap.origin == plan.origin,
                                                   PortabilityRowMap.family == fam.name,
                                                   PortabilityRowMap.source_key == key))
    if rm is None:
        db.add(PortabilityRowMap(origin=plan.origin, family=fam.name, source_key=key, local_key=local_key,
                                 import_id=plan.import_id, created=created, content_sha256=_digest(form)))
    else:
        rm.content_sha256 = _digest(form)


def _local_key(fam: Family, obj) -> str:
    pk = [c.name for c in fam.model.__table__.primary_key.columns]
    return "|".join(str(getattr(obj, _attr(fam, c))) for c in pk)


def _load_chunk(db: Session, plan: Plan, fam: Family, chunk: dict, pending: dict, report: dict) -> None:
    for key, row in chunks.read_chunk(plan.checkpoint / chunk["file"], fam.name):
        local, rm = find_local(db, plan, fam, key, row)
        if local is not None:
            form = archive_form(plan, fam, local, key)
            if form == row or fam.name in REFERENCE_ONLY:
                if rm is None:
                    _remember(db, plan, fam, key, _local_key(fam, local), False, form)
                report["identical"] += 1
                continue
            if rm is None or rm.content_sha256 != _digest(form):
                raise ImportBlocked(f"{fam.name} {key} exists here with different content", "divergent",
                                    {"family": fam.name, "key": key})
            for attr, v in _values(plan, fam, row, with_deferred=True).items():
                setattr(local, attr, v)
            db.flush()
            _remember(db, plan, fam, key, _local_key(fam, local), False, archive_form(plan, fam, local, key))
            report["updated"] += 1
            continue
        values = _values(plan, fam, row, with_deferred=False)
        missing = _missing_refs(db, fam, values, pending)
        if missing:
            if (plan.decisions.get("unresolved_references") or "block") != "defer":
                raise ImportBlocked(f"{fam.name} {key} refers to what is neither here nor in the archive",
                                    "unresolved_reference", {"family": fam.name, "key": key, "missing": missing})
            nullable = {c.name: c.nullable for c in fam.model.__table__.columns}
            if not all(nullable[c] for c, _ in missing):
                report["deferred"].append({"family": fam.name, "key": key, "missing": missing, "row": "left out"})
                continue
            for c, _ in missing:
                values[_attr(fam, c)] = None
            report["deferred"].append({"family": fam.name, "key": key, "missing": missing, "row": "loaded"})
        if fam.name == "types":
            _ensure_owner(db, plan, values.get("workspace_id"))
        obj = fam.model(**values)
        db.add(obj)
        db.flush()
        _remember(db, plan, fam, key, _local_key(fam, obj), True, archive_form(plan, fam, obj, key))
        report["created"] += 1


def _ensure_owner(db: Session, plan: Plan, ws: Optional[str]) -> None:
    """A shared type's owner workspace, when this instance does not have it: a stub, so the type
    keeps its identity. Staged like the rest, and removed if the import is discarded."""
    if not ws or db.get(Workspace, ws) is not None:
        return
    db.add(Workspace(id=ws, name=ws, is_global=True, import_state="staging"))
    db.flush()
    db.add(PortabilityRowMap(origin=plan.origin, family="workspaces", source_key=plan.unmap_ws(ws), local_key=ws,
                             import_id=plan.import_id, created=True, content_sha256=None))


def _deferred(db: Session, plan: Plan, fam: Family, pending: dict, report: dict) -> None:
    for _, key, row in archive_rows(plan, fam):
        values = {k: v for k, v in _values(plan, fam, row, with_deferred=True).items()
                  if k in {_attr(fam, c) for c in fam.deferred}}
        if not any(v is not None for v in values.values()):
            continue
        local, _ = find_local(db, plan, fam, key, row)
        if local is None:
            continue
        for attr, v in values.items():
            setattr(local, attr, v)
        db.flush()
        _remember(db, plan, fam, key, _local_key(fam, local), False, archive_form(plan, fam, local, key))


def _replace(db: Session, plan: Plan, fam: Family) -> None:
    """An increment states a set-valued family whole: what this origin wrote earlier and the set no
    longer holds goes. Nothing another origin or a person here wrote is touched."""
    keys = {key for _, key, _ in archive_rows(plan, fam)}
    for rm in list(db.scalars(select(PortabilityRowMap).where(PortabilityRowMap.origin == plan.origin,
                                                               PortabilityRowMap.family == fam.name,
                                                               PortabilityRowMap.created.is_(True)))):
        if rm.source_key in keys:
            continue
        local = _by_local_key(db, fam, rm.local_key)
        if local is not None:
            db.delete(local)
        db.delete(rm)
    db.flush()


def _by_local_key(db: Session, fam: Family, local_key: str):
    pk = [c for c in fam.model.__table__.primary_key.columns]
    parts = local_key.split("|")
    vals = [int(p) if str(c.type) in ("INTEGER", "BIGINT") else p for c, p in zip(pk, parts)]
    return db.get(fam.model, vals[0] if len(vals) == 1 else tuple(vals))


# --------------------------------------------------------------------------- rebuild

def _imported(db: Session, plan: Plan, family: str) -> list[PortabilityRowMap]:
    return list(db.scalars(select(PortabilityRowMap).where(PortabilityRowMap.origin == plan.origin,
                                                           PortabilityRowMap.family == family)))


def rebuild(db: Session, plan: Plan) -> dict:
    """Projections from the ledger alone: bindings and heads replayed from events, then the engine's
    own rebuild (fact state, attributes, status, derived relations, conflicts), then the conflicts
    the engine keeps only as events. Returns what the rebuild itself wrote to the audit."""
    from app.ledger import engine
    from app.ledger.engine import DERIVED_CONFLICTS
    from app.models.asset import Asset
    before = {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in EVENT_TABLES}
    with writing(db):
        refs = {db.get(IdentityEvent, int(rm.local_key)).source_ref for rm in _imported(db, plan, "identity_events")}
        for ref in sorted(refs):
            state = None
            for ev in db.scalars(select(IdentityEvent).where(IdentityEvent.source_ref == ref).order_by(IdentityEvent.seq)):
                state = None if ev.kind == "unbound" else ev.uid
            b = db.get(IdentityBinding, ref)
            if state is None and b is not None:
                db.delete(b)
            elif state is not None and b is None:
                db.add(IdentityBinding(source_ref=ref, uid=state))
            elif state is not None:
                b.uid = state
        db.flush()
        for rm in _imported(db, plan, "streams"):
            sid = rm.local_key
            revs = list(db.scalars(select(SourceRevision).where(SourceRevision.stream_id == sid,
                                                                SourceRevision.ordering == "head")
                                   .order_by(SourceRevision.number)))
            pub = db.scalar(select(RevisionEvent).where(RevisionEvent.stream_id == sid,
                                                        RevisionEvent.kind.in_(("published", "rewound_to")))
                            .order_by(RevisionEvent.seq.desc()).limit(1))
            head = db.get(StreamHead, sid) or StreamHead(stream_id=sid)
            head.parsed_head = revs[-1].id if revs else None
            head.parsed_number = revs[-1].number if revs else 0
            published = db.get(SourceRevision, pub.revision_id) if pub else None
            head.published_head = published.id if published else None
            head.published_number = published.number if published else 0
            db.add(head)
        db.flush()
        for ws in plan.workspaces:
            if db.get(Workspace, ws) is not None:
                engine.rebuild(db, ws)
        uids = set(db.scalars(select(Asset.uid).where(Asset.workspace_id.in_(plan.workspaces))))
        last: dict = {}
        for ev in db.scalars(select(ConflictEvent).where(ConflictEvent.subject_uid.in_(uids),
                                                         ConflictEvent.conflict_type.in_(DERIVED_CONFLICTS))
                             .order_by(ConflictEvent.seq)):
            last[ev.conflict_id] = ev
        for cid, ev in last.items():
            here = db.get(Conflict, cid)
            if ev.kind == "opened" and here is None:
                rec = db.get(Asset, ev.subject_uid)
                db.add(Conflict(conflict_id=cid, conflict_type=ev.conflict_type,
                                severity="blocking" if ev.conflict_type == "merge_installation_overlap" else "non-blocking",
                                workspace_id=rec.workspace_id, subject_uid=ev.subject_uid, predicate=ev.predicate,
                                member=ev.member, detail=ev.detail or {}, opened_seq=ev.seq))
            elif ev.kind != "opened" and here is not None:
                db.delete(here)
        db.flush()
        # A record's timestamps are not ledger state: loading references and rebuilding touched them,
        # the archive has them.
        for fam in plan.families():
            if "updated_at" not in fam.columns or "uid" not in fam.key:
                continue
            for _, key, row in archive_rows(plan, fam):
                if row.get("updated_at"):
                    db.execute(update(fam.model).where(fam.model.uid == row["uid"])
                               .values(updated_at=from_json(fam.model, "updated_at", row["updated_at"]))
                               .execution_options(synchronize_session=False))
        db.flush()
    db.expire_all()
    after = {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in EVENT_TABLES}
    return {"events_written_by_rebuild": {k: after[k] - before[k] for k in after if after[k] != before[k]}}


# --------------------------------------------------------------------------- reconcile

def reconcile(db: Session, plan: Plan, deferred: Optional[list] = None) -> dict:
    """Authoritative families row by row against the archive (and so against the manifest's hashes),
    projections rebuilt here against the projections the export carried, invariants."""
    explained = {(d["family"], d["key"]) for d in (deferred or [])}
    fams: dict = {}
    for fam in plan.families():
        h = hashlib.sha256()
        mismatches = []
        rows = 0
        for c in plan.manifest["families"][fam.name]["chunks"]:
            ch = hashlib.sha256()
            for key, row in chunks.read_chunk(plan.checkpoint / c["file"], fam.name):
                local, _ = find_local(db, plan, fam, key, row)
                form = archive_form(plan, fam, local, key) if local is not None else {}
                if form != row and (fam.name, key) not in explained and fam.name not in REFERENCE_ONLY:
                    mismatches.append({"key": key, "missing": local is None,
                                       "fields": sorted(_differs(row, form))[:10]})
                ch.update(chunks.line(fam.name, key, form))
                rows += 1
            h.update(ch.hexdigest().encode())
        expected = plan.manifest["families"][fam.name]
        fams[fam.name] = {"rows": rows, "expected_rows": expected["rows"], "sha256": h.hexdigest(),
                          "expected_sha256": expected["sha256"], "mismatches": mismatches[:20],
                          "mismatch_count": len(mismatches),
                          "ok": not mismatches and rows == expected["rows"]}
    projections = _compare_projections(db, plan)
    from app.ledger import invariants
    local_inv = invariants.report(db, [w for w in plan.workspaces if db.get(Workspace, w) is not None])
    exported_ok = (plan.manifest.get("invariants") or {}).get("ok")
    inv_ok = bool(local_inv.get("ok")) or exported_ok is False
    passed = all(f["ok"] for f in fams.values()) and all(p["ok"] for p in projections.values()) and inv_ok
    return {"import_id": plan.import_id, "export_id": plan.manifest["export_id"], "origin": plan.origin,
            "watermark": plan.manifest["watermark"], "families": fams, "projections": projections,
            "invariants": {"ok": local_inv.get("ok"), "exported_ok": exported_ok, "acceptable": inv_ok},
            "deferred_references": deferred or [], "passed": passed}


def _differs(expected: dict, got: dict) -> list[str]:
    """Which fields differ, naming keys inside JSON objects too — never their values."""
    out = []
    for k in set(expected) | set(got):
        a, b = expected.get(k), got.get(k)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            out += [f"{k}.{sub}" for sub in sorted(set(a) | set(b)) if a.get(sub) != b.get(sub)]
        else:
            out.append(k)
    return out


PROJECTION_TIMESTAMPS = ("created_at", "updated_at")   # when a projection row was derived, not what it says


def _proj_key(fam: Family, row: dict) -> str:
    return json.dumps({k: v for k, v in sorted(row.items()) if k not in PROJECTION_TIMESTAMPS},
                      sort_keys=True, default=str)


def _compare_projections(db: Session, plan: Plan) -> dict:
    out = {}
    sc = Scope(workspaces=plan.workspaces, watermark={})
    for fam in [f for f in FAMILIES if f.group == "projection" and f.name in plan.manifest["families"]]:
        exported = {_proj_key(fam, _mapped_row(plan, fam, row)) for _, _, row in archive_rows(plan, fam)}
        local = set()
        for obj in db.scalars(fam.select(db, sc)):
            row = {c: to_json(getattr(obj, _attr(fam, c))) for c in fam.columns}
            local.add(_proj_key(fam, row))
        only_exported, only_local = sorted(exported - local), sorted(local - exported)
        out[fam.name] = {"exported": len(exported), "rebuilt": len(local), "ok": not only_exported and not only_local,
                         "only_in_export": [json.loads(x) for x in only_exported[:5]],
                         "only_rebuilt": [json.loads(x) for x in only_local[:5]]}
    return out


# --------------------------------------------------------------------------- finalize, discard

def finalize(db: Session, plan: Plan) -> None:
    for rm in _imported(db, plan, "workspaces"):
        if rm.import_id == plan.import_id and rm.created:
            ws = db.get(Workspace, rm.local_key)
            if ws is not None:
                ws.import_state = None
    position = db.scalar(select(func.coalesce(func.max(PortabilityChainLink.position), 0)).where(
        PortabilityChainLink.origin == plan.origin)) + 1
    db.add(PortabilityChainLink(origin=plan.origin, export_id=plan.manifest["export_id"], position=position,
                                watermark_label=plan.manifest["watermark"]["label"], import_id=plan.import_id))
    db.flush()


def discard(db: Session, plan_origin: str, import_id: str) -> dict:
    """Remove exactly what a staged import wrote, newest first, audit rows included (the sanctioned
    purge), and the staged workspaces. Rows that were already here are untouched."""
    from app.ledger.audit import allow_purge
    allow_purge(db)
    removed = 0
    order = [f.name for g in reversed(GROUP_ORDER) for f in reversed(FAMILIES) if f.group == g]
    maps = list(db.scalars(select(PortabilityRowMap).where(PortabilityRowMap.import_id == import_id)))
    by_family: dict = defaultdict(list)
    for rm in maps:
        by_family[rm.family].append(rm)
    with writing(db):
        for name in order:
            fam = BY_NAME[name]
            for rm in sorted(by_family.get(name, []), key=lambda r: r.id, reverse=True):
                if rm.created and name != "workspaces":
                    local = _by_local_key(db, fam, rm.local_key)
                    if local is not None:
                        if name == "assets":
                            local.merged_into_uid = None
                        db.delete(local)
                        removed += 1
                db.delete(rm)
            db.flush()
        for rm in by_family.get("workspaces", []):
            if rm.created:
                ws = db.get(Workspace, rm.local_key)
                if ws is not None and ws.import_state == "staging":
                    _purge_workspace(db, ws.id)
                    removed += 1
    db.flush()
    return {"removed": removed}


def _purge_workspace(db: Session, ws: str) -> None:
    """A staged workspace and what the rebuild derived inside it."""
    from app.models.asset import Asset, Relation
    db.execute(delete(Relation).where(Relation.workspace_id == ws))
    db.execute(delete(Conflict).where(Conflict.workspace_id == ws))
    uids = select(Asset.uid).where(Asset.workspace_id == ws)
    from app.models.ledger import FactState
    db.execute(delete(FactState).where(FactState.subject_uid.in_(uids)))
    db.execute(delete(IdentityBinding).where(IdentityBinding.uid.in_(uids)))
    for model in (ConflictEvent, StatusEvent, RecordEvent):
        col = model.subject_uid if hasattr(model, "subject_uid") else model.uid
        db.execute(delete(model).where(col.in_(uids)))
    db.execute(delete(IdentityEvent).where(IdentityEvent.uid.in_(uids)))
    db.execute(delete(Workspace).where(Workspace.id == ws))
    db.flush()
