"""Controlled bulk changes (asset-model-revision §19 item 7).

A bulk change names its targets (explicit uids, or a type and an attribute
filter) and what to set on them, or that they retire. It is always
previewed first — a dry run that writes nothing and shows each record's
before and after. Above `APPROVAL_THRESHOLD` records a second person must
approve it. It is applied as **one** ledger batch of decisions, and undone
by revoking that batch: whatever held before comes back, sources included.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.ledger.engine import LedgerError, now
from app.models.asset import Asset
from app.models.ledger import BulkChange, Decision
from app.services.visibility import can_see, hidden_fields

APPROVAL_THRESHOLD = 100
MAX_RECORDS = 5000


def _targets(db: Session, workspace_id: str, spec: dict) -> list[Asset]:
    t = spec.get("targets") or {}
    if t.get("uids"):
        rows = [a for a in (db.get(Asset, u) for u in t["uids"]) if a is not None]
    else:
        q = select(Asset).where(Asset.workspace_id == workspace_id, Asset.deleted_at.is_(None),
                                Asset.record_status.notin_(("Merged", "Retired")))
        if t.get("type"):
            q = q.where(Asset.type == t["type"])
        where = t.get("where") or {}
        if where.get("attribute"):
            col = Asset.attributes[where["attribute"]].astext
            q = q.where(col == str(where["equals"])) if "equals" in where else q.where(col.isnot(None))
        rows = list(db.scalars(q.limit(MAX_RECORDS + 1)))
    if len(rows) > MAX_RECORDS:
        raise LedgerError(f"a bulk change touches at most {MAX_RECORDS} records")
    # Only records the actor owns and may see (I-ACL-1).
    return [a for a in rows if a.workspace_id == workspace_id and can_see(a)]


def _changes(db: Session, record: Asset, spec: dict) -> list[dict]:
    out = []
    hidden = hidden_fields(db, record)
    if spec.get("retire"):
        if record.record_status != "Retired":
            out.append({"predicate": "exists", "before": record.record_status, "after": "Retired",
                        "value": "absent"})
        return out
    for item in spec.get("set") or []:
        predicate = item["predicate"]
        if not predicate.startswith("attr:"):
            raise LedgerError("a bulk change sets attributes (attr:<name>) or retires records")
        name = predicate[5:]
        if name in hidden:
            continue
        before = (record.attributes or {}).get(name)
        if before != item.get("value"):
            out.append({"predicate": predicate, "before": before, "after": item.get("value"),
                        "value": item.get("value")})
    return out


def preview(db: Session, workspace_id: str, actor: str, spec: dict, description: Optional[str] = None) -> BulkChange:
    """The dry run: nothing is written to the ledger."""
    rows = []
    for record in _targets(db, workspace_id, spec):
        changes = _changes(db, record, spec)
        if changes:
            rows.append({"uid": record.uid, "key": record.key, "name": record.name, "type": record.type,
                         "changes": [{k: c[k] for k in ("predicate", "before", "after")} for c in changes]})
    change = BulkChange(id=str(uuid.uuid4()), workspace_id=workspace_id, actor=actor, description=description,
                        spec=spec, preview=rows, count=len(rows), state="previewed", created_at=now())
    db.add(change)
    db.flush()
    return change


def _get(db: Session, change_id: str, workspace_id: str) -> BulkChange:
    change = db.get(BulkChange, change_id)
    if change is None or change.workspace_id != workspace_id:
        raise LedgerError("no such bulk change")
    return change


def apply(db: Session, workspace_id: str, change_id: str, actor: str) -> BulkChange:
    change = _get(db, change_id, workspace_id)
    if change.state not in ("previewed", "awaiting_approval"):
        raise LedgerError(f"this bulk change is {change.state}")
    if change.count > APPROVAL_THRESHOLD and change.approved_by is None:
        change.state = "awaiting_approval"
        db.flush()
        return change
    batch = []
    for record in _targets(db, workspace_id, change.spec):
        for c in _changes(db, record, change.spec):
            replaces = [d.decision_id for d in engine._active_decisions(db, record.uid, c["predicate"], None)]
            item = {"subject_uid": record.uid, "predicate": c["predicate"], "value": c["value"],
                    "reason": change.description or f"bulk change {change.id}"}
            batch.append({**item, "kind": "supersede", "supersedes": replaces} if replaces
                         else {**item, "kind": "confirm"})
    if not batch:
        raise LedgerError("nothing to change any more; preview again")
    written = engine.apply_decisions(db, workspace_id, actor, batch)
    change.state, change.batch_id, change.applied_at = "applied", written[0].batch_id, now()
    db.flush()
    return change


def approve(db: Session, workspace_id: str, change_id: str, approver: str) -> BulkChange:
    change = _get(db, change_id, workspace_id)
    if change.state != "awaiting_approval":
        raise LedgerError("only a bulk change awaiting approval can be approved")
    if approver == change.actor:
        raise LedgerError("a bulk change is approved by someone other than its author")
    change.approved_by = approver
    db.flush()
    return apply(db, workspace_id, change_id, change.actor)


def undo(db: Session, workspace_id: str, change_id: str, actor: str) -> BulkChange:
    """Revoke the whole batch: every record gets back what held before."""
    change = _get(db, change_id, workspace_id)
    if change.state != "applied":
        raise LedgerError("only an applied bulk change can be undone")
    decisions = [d.decision_id for d in db.scalars(select(Decision).where(Decision.batch_id == change.batch_id))]
    written = engine.apply_decisions(db, workspace_id, actor, [
        {"kind": "revoke", "target": {"decisions": decisions}, "reason": f"undo of bulk change {change.id}"}])
    change.state, change.undo_batch_id = "undone", written[0].batch_id
    db.flush()
    return change


def view(change: BulkChange, rows: int = 200) -> dict:
    return {"id": change.id, "actor": change.actor, "description": change.description, "spec": change.spec,
            "count": change.count, "state": change.state, "approved_by": change.approved_by,
            "needs_approval": change.count > APPROVAL_THRESHOLD, "threshold": APPROVAL_THRESHOLD,
            "batch_id": change.batch_id, "undo_batch_id": change.undo_batch_id, "created_at": change.created_at,
            "applied_at": change.applied_at, "preview": change.preview[:rows]}
