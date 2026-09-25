"""Complete export in open formats (asset-model-revision §19 item 9).

JSON lines: one record per line, per kind. What a viewer may not see —
restricted classes they hold no grant for — is not exported (I-ACL-1).
"""
import json
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.asset import Asset, Relation
from app.models.issue import Issue
from app.models.ledger import Decision, RecordEvent
from app.services.visibility import can_see, restriction_clause, visible_assets_clause, visible_issues_clause

router = APIRouter(prefix="/v1/export", tags=["export"])

KINDS = ("assets", "tickets", "relations", "ledger")


def _lines(rows: Iterator[dict]) -> Iterator[str]:
    for row in rows:
        yield json.dumps(row, default=str, sort_keys=True) + "\n"


def _assets(db: Session, ws: str):
    for a in db.scalars(select(Asset).where(Asset.workspace_id == ws, visible_assets_clause(ws))
                        .order_by(Asset.uid)):
        yield {"uid": a.uid, "key": a.key, "name": a.name, "type": a.type, "schema_uid": a.schema_uid,
               "record_status": a.record_status, "merged_into_uid": a.merged_into_uid,
               "attributes": a.attributes or {}, "is_global": a.is_global}


def _tickets(db: Session, ws: str):
    for i in db.scalars(select(Issue).where(Issue.workspace_id == ws, visible_issues_clause()).order_by(Issue.uid)):
        yield {"uid": i.uid, "title": i.title, "description": i.description, "state": i.state,
               "priority": i.priority, "assignee": i.assignee, "asset_uid": i.asset_uid,
               "schema_uid": i.schema_uid, "attributes": i.attributes or {}, "labels": i.labels or [],
               "created_at": i.created_at, "updated_at": i.updated_at, "closed_at": i.closed_at}


def _relations(db: Session, ws: str):
    visible = select(Asset.uid).where(restriction_clause(Asset))
    for r in db.scalars(select(Relation).where(Relation.workspace_id == ws, Relation.from_asset_uid.in_(visible),
                                               Relation.to_asset_uid.in_(visible)).order_by(Relation.id)):
        yield {"from": r.from_asset_uid, "to": r.to_asset_uid, "relation": r.relation_type,
               "derivation": r.derivation, "rule": r.rule}


def _ledger(db: Session, ws: str):
    def shown(uid):
        a = db.get(Asset, uid) if uid else None
        return a is None or can_see(a)
    for d in db.scalars(select(Decision).where(Decision.workspace_id == ws).order_by(Decision.seq)):
        if shown(d.subject_uid):
            yield {"type": "decision", "seq": d.seq, "decision_id": d.decision_id, "batch_id": d.batch_id,
                   "kind": d.kind, "actor": d.actor, "subject_uid": d.subject_uid, "predicate": d.predicate,
                   "member": d.member, "value": d.value, "target": d.target, "supersedes": d.supersedes,
                   "reason": d.reason, "at": d.at}
    uids = select(Asset.uid).where(Asset.workspace_id == ws, restriction_clause(Asset))
    for e in db.scalars(select(RecordEvent).where(RecordEvent.uid.in_(uids)).order_by(RecordEvent.seq)):
        yield {"type": "record_event", "seq": e.seq, "uid": e.uid, "kind": e.kind, "before": e.before,
               "after": e.after, "cause": e.cause, "at": e.at}


@router.get("/{kind}")
def export(kind: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"export kinds are {', '.join(KINDS)}")
    rows = {"assets": _assets, "tickets": _tickets, "relations": _relations, "ledger": _ledger}[kind](db, workspace_id)
    # Materialized before the session closes: the response streams after the request.
    body = list(_lines(rows))
    return StreamingResponse(iter(body), media_type="application/x-ndjson",
                             headers={"Content-Disposition": f'attachment; filename="{workspace_id}-{kind}.jsonl"'})
