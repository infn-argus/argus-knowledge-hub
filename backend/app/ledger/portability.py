"""Complete export in open formats, and loading it into an empty instance
(asset-model-revision §19 item 9).

A bundle is one JSON-lines file per kind: the workspace, its types, records,
tickets, comments, relations, attachment metadata (with SHA-256; the files
travel alongside) and the ledger's decisions and record events. Loading a
bundle into a fresh database gives the same records, links and history —
which is what `tests/test_readiness_ops.py` proves against a real empty
database.

The API export (`/v1/export`) shows only what the viewer may see; an
instance export for migration or escrow runs with every grant.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation
from app.models.attachment import Attachment
from app.models.issue import Issue, IssueComment
from app.models.ledger import Decision, RecordEvent
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.visibility import (can_see, redacted_attributes, restriction_clause, visible_assets_clause,
                                     visible_issues_clause)

KINDS = ("workspace", "schemas", "assets", "tickets", "comments", "relations", "attachments", "ledger")
FORMAT = "argus-export/1"


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def rows(db: Session, ws: str, kind: str) -> Iterator[dict]:
    if kind == "workspace":
        w = db.get(Workspace, ws)
        yield {"format": FORMAT, "id": w.id, "name": w.name, "is_global": bool(getattr(w, "is_global", False))}
    elif kind == "schemas":
        # The workspace's own types, and the shared types its records use
        # (with their ancestors): without them the bundle cannot load alone.
        wanted = set(db.scalars(select(Schema.uid).where(Schema.workspace_id == ws)))
        wanted |= {u for u in db.scalars(select(Asset.schema_uid).where(Asset.workspace_id == ws)) if u}
        wanted |= {u for u in db.scalars(select(Issue.schema_uid).where(Issue.workspace_id == ws)) if u}
        frontier = set(wanted)
        while frontier:
            parents = {p for p in db.scalars(select(Schema.parent_schema_uid).where(Schema.uid.in_(frontier))) if p}
            frontier = parents - wanted
            wanted |= parents
        for s in db.scalars(select(Schema).where(Schema.uid.in_(wanted)).order_by(Schema.uid)):
            yield {"uid": s.uid, "name": s.name, "description": s.description, "parent_schema_uid": s.parent_schema_uid,
                   "attributes": s.attributes or [], "metadata": s.metadata_json or {}, "applies_to": s.applies_to,
                   "is_concrete": s.is_concrete, "is_global": s.is_global, "owner": s.workspace_id,
                   "external": s.workspace_id != ws}
    elif kind == "assets":
        for a in db.scalars(select(Asset).where(Asset.workspace_id == ws, visible_assets_clause(ws))
                            .order_by(Asset.uid)):
            yield {"uid": a.uid, "key": a.key, "name": a.name, "type": a.type, "schema_uid": a.schema_uid,
                   "record_status": a.record_status, "merged_into_uid": a.merged_into_uid,
                   "attributes": redacted_attributes(db, a), "is_global": a.is_global}
    elif kind == "tickets":
        for i in db.scalars(select(Issue).where(Issue.workspace_id == ws, visible_issues_clause()).order_by(Issue.uid)):
            yield {"uid": i.uid, "title": i.title, "description": i.description, "state": i.state,
                   "priority": i.priority, "assignee": i.assignee, "asset_uid": i.asset_uid,
                   "schema_uid": i.schema_uid, "attributes": redacted_attributes(db, i), "labels": i.labels or [],
                   "created_by": i.created_by, "created_at": _iso(i.created_at), "updated_at": _iso(i.updated_at),
                   "closed_at": _iso(i.closed_at)}
    elif kind == "comments":
        tickets = select(Issue.uid).where(Issue.workspace_id == ws, visible_issues_clause())
        for c in db.scalars(select(IssueComment).where(IssueComment.issue_uid.in_(tickets))
                            .order_by(IssueComment.uid)):
            yield {"uid": c.uid, "issue_uid": c.issue_uid, "author": c.author, "body": c.body,
                   "created_at": _iso(c.created_at)}
    elif kind == "relations":
        visible = select(Asset.uid).where(restriction_clause(Asset))
        own = set(db.scalars(select(Asset.uid).where(Asset.workspace_id == ws)))
        for r in db.scalars(select(Relation).where(Relation.workspace_id == ws, Relation.from_asset_uid.in_(visible),
                                                   Relation.to_asset_uid.in_(visible)).order_by(Relation.id)):
            # A link to another workspace's record: loaded only where that record exists too.
            yield {"from": r.from_asset_uid, "to": r.to_asset_uid, "relation": r.relation_type,
                   "derivation": r.derivation, "rule": r.rule,
                   "external": r.from_asset_uid not in own or r.to_asset_uid not in own}
    elif kind == "attachments":
        for a in db.scalars(select(Attachment).where(Attachment.workspace_id == ws).order_by(Attachment.uid)):
            owner = db.get(Asset, a.asset_uid) if a.asset_uid else db.get(Issue, a.issue_uid) if a.issue_uid else None
            if owner is not None and not can_see(owner):
                continue
            yield {"uid": a.uid, "asset_uid": a.asset_uid, "issue_uid": a.issue_uid, "filename": a.filename,
                   "mime_type": a.mime_type, "size": a.file_size, "sha256": a.sha256,
                   "file": os.path.basename(a.storage_path or "")}
    elif kind == "ledger":
        def shown(uid):
            a = db.get(Asset, uid) if uid else None
            return a is None or can_see(a)
        for d in db.scalars(select(Decision).where(Decision.workspace_id == ws).order_by(Decision.seq)):
            if shown(d.subject_uid):
                yield {"type": "decision", "decision_id": d.decision_id, "batch_id": d.batch_id, "kind": d.kind,
                       "actor": d.actor, "subject_uid": d.subject_uid, "predicate": d.predicate, "member": d.member,
                       "value": d.value, "target": d.target, "supersedes": d.supersedes, "reason": d.reason,
                       "effective_at": _iso(d.effective_at), "at": _iso(d.at)}
        uids = select(Asset.uid).where(Asset.workspace_id == ws, restriction_clause(Asset))
        for e in db.scalars(select(RecordEvent).where(RecordEvent.uid.in_(uids)).order_by(RecordEvent.seq)):
            yield {"type": "record_event", "uid": e.uid, "kind": e.kind, "before": e.before, "after": e.after,
                   "cause": e.cause, "at": _iso(e.at)}
    else:
        raise ValueError(f"unknown export kind {kind!r}")


def lines(db: Session, ws: str, kind: str) -> Iterator[str]:
    for row in rows(db, ws, kind):
        yield json.dumps(row, default=str, sort_keys=True) + "\n"


def write_bundle(db: Session, ws: str, out_dir: str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for kind in KINDS:
        with open(out / f"{kind}.jsonl", "w") as f:
            n = 0
            for line in lines(db, ws, kind):
                f.write(line)
                n += 1
        counts[kind] = n
    return counts


def read_bundle(in_dir: str) -> dict[str, list[dict]]:
    return {kind: [json.loads(line) for line in open(Path(in_dir) / f"{kind}.jsonl") if line.strip()]
            for kind in KINDS if (Path(in_dir) / f"{kind}.jsonl").exists()}


def _schema_order(schemas: list[dict]) -> list[dict]:
    """Parents before children."""
    by_uid = {s["uid"]: s for s in schemas}
    done, out = set(), []

    def visit(s):
        if s["uid"] in done:
            return
        parent = by_uid.get(s.get("parent_schema_uid"))
        if parent is not None:
            visit(parent)
        done.add(s["uid"])
        out.append(s)
    for s in schemas:
        visit(s)
    return out


def load_bundle(db: Session, bundle: dict[str, list[dict]], attachments_dir: Optional[str] = None,
                workspace_id: Optional[str] = None) -> dict:
    """Load a bundle into an instance that does not hold this workspace yet."""
    from datetime import datetime
    meta = bundle["workspace"][0]
    if meta.get("format") != FORMAT:
        raise ValueError(f"not an {FORMAT} bundle")
    ws = workspace_id or meta["id"]
    if db.get(Workspace, ws) is not None:
        raise ValueError(f"workspace {ws} already exists here; load into an empty instance or another id")

    def dt(v):
        return datetime.fromisoformat(v) if isinstance(v, str) else v

    db.add(Workspace(id=ws, name=meta["name"]))
    db.flush()
    for s in _schema_order(bundle.get("schemas", [])):
        owner = ws
        if s.get("external"):
            if db.get(Schema, s["uid"]) is not None:
                continue                # the shared type is already here
            owner = s["owner"]
            if db.get(Workspace, owner) is None:
                # A shared catalogue the target does not hold yet: its owner
                # comes along as a stub, so the type keeps its identity.
                db.add(Workspace(id=owner, name=owner, is_global=True))
                db.flush()
        db.add(Schema(uid=s["uid"], workspace_id=owner, name=s["name"], description=s.get("description"),
                      parent_schema_uid=s.get("parent_schema_uid"), attributes=s.get("attributes") or [],
                      metadata_json=s.get("metadata") or {}, applies_to=s.get("applies_to") or "objects",
                      is_concrete=s.get("is_concrete", True), is_global=s.get("is_global", False)))
        db.flush()
    for a in bundle.get("assets", []):
        db.add(Asset(uid=a["uid"], workspace_id=ws, key=a["key"], name=a["name"], type=a["type"],
                     schema_uid=a["schema_uid"], record_status=a.get("record_status") or "Active",
                     merged_into_uid=None, attributes=a.get("attributes") or {}, is_global=a.get("is_global", False)))
    db.flush()
    for a in bundle.get("assets", []):
        if a.get("merged_into_uid"):
            db.get(Asset, a["uid"]).merged_into_uid = a["merged_into_uid"]
    for i in bundle.get("tickets", []):
        db.add(Issue(uid=i["uid"], workspace_id=ws, title=i["title"], description=i.get("description"),
                     state=i.get("state") or "new", priority=i.get("priority"), assignee=i.get("assignee"),
                     asset_uid=i.get("asset_uid"), schema_uid=i.get("schema_uid"), attributes=i.get("attributes") or {},
                     labels=i.get("labels") or [], created_by=i.get("created_by"), created_at=dt(i.get("created_at")),
                     updated_at=dt(i.get("updated_at")), closed_at=dt(i.get("closed_at"))))
    db.flush()
    for c in bundle.get("comments", []):
        db.add(IssueComment(uid=c["uid"], issue_uid=c["issue_uid"], author=c["author"], body=c["body"],
                            created_at=dt(c.get("created_at"))))
    unresolved = []
    for r in bundle.get("relations", []):
        if r.get("external") and (db.get(Asset, r["from"]) is None or db.get(Asset, r["to"]) is None):
            unresolved.append(r)        # its other end lives in a workspace this instance does not hold
            continue
        db.add(Relation(workspace_id=ws, from_asset_uid=r["from"], to_asset_uid=r["to"], relation_type=r["relation"],
                        derivation=r.get("derivation"), rule=r.get("rule")))
    for a in bundle.get("attachments", []):
        path = os.path.join(attachments_dir, a["file"]) if attachments_dir else a["file"]
        db.add(Attachment(uid=a["uid"], workspace_id=ws, asset_uid=a.get("asset_uid"), issue_uid=a.get("issue_uid"),
                          filename=a["filename"], mime_type=a.get("mime_type"), file_size=a.get("size"),
                          storage_path=path, sha256=a.get("sha256")))
    for e in bundle.get("ledger", []):
        if e["type"] == "decision":
            db.add(Decision(decision_id=e["decision_id"], batch_id=e["batch_id"], kind=e["kind"], actor=e["actor"],
                            workspace_id=ws, subject_uid=e.get("subject_uid"), predicate=e.get("predicate"),
                            member=e.get("member"), value=e.get("value"), target=e.get("target"),
                            supersedes=e.get("supersedes") or [], reason=e.get("reason"),
                            effective_at=dt(e.get("effective_at")), at=dt(e.get("at"))))
        else:
            db.add(RecordEvent(uid=e["uid"], kind=e["kind"], before=e.get("before"), after=e.get("after"),
                               cause=e.get("cause") or "import", at=dt(e.get("at"))))
    db.flush()
    return {**{kind: len(bundle.get(kind, [])) for kind in KINDS}, "unresolved_external_relations": unresolved}


def fingerprint(db: Session, ws: str) -> dict:
    """A comparable digest of a workspace's content: the same bundle loaded
    anywhere yields the same fingerprint."""
    import hashlib
    out = {}
    for kind in KINDS[1:]:
        h = hashlib.sha256()
        n = 0
        for row in rows(db, ws, kind):
            if kind == "relations" and row.get("external"):
                continue        # compared by an instance-level load, not a workspace one
            row = {k: v for k, v in row.items() if k not in ("workspace_id", "external")}
            h.update(json.dumps(row, default=str, sort_keys=True).encode())
            n += 1
        out[kind] = {"count": n, "sha256": h.hexdigest()}
    return out


def verify_files(bundle: dict, attachments_dir: str) -> list[str]:
    """Attachments whose file is missing or whose checksum differs."""
    from app.models.attachment import file_sha256
    problems = []
    for a in bundle.get("attachments", []):
        digest = file_sha256(os.path.join(attachments_dir, a["file"]))
        if digest != a.get("sha256"):
            problems.append(f"{a['filename']}: {'missing' if digest is None else 'checksum differs'}")
    return problems


def everything():
    """Run an instance export with every grant (escrow, migration)."""
    from app.services.visibility import Grants, set_current_grants
    set_current_grants(Grants.all())

