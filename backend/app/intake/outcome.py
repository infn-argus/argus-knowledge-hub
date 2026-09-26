"""What the person did with the suggestions, once the record is saved (§23.8, §23.11).

For every suggested field: kept, corrected or left out. The record itself
was saved by the ordinary create path, as the person's own confirmed
statements; this only adds the provenance.

For an asset the suggestions also enter the fact ledger as AI claims, in
the stream `ai:<workspace>:asset.describe`, with their evidence and
confidence. A kept suggestion is accepted, and a corrected or left-out one
is rejected with that reason. The person's confirmation stays the effective
fact, and the model's proposal stays in the history beside it.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.ledger.engine import LedgerError, ParsedClaim
from app.models.asset import Asset
from app.models.intake import IntakeOutcome, IntakeRun

EMPTY = (None, "", [], {})


class OutcomeError(LedgerError):
    pass


def _same(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip()
    return a == b


def verdicts(proposed: dict, final: dict) -> dict:
    out = {}
    for field, suggestion in (proposed or {}).items():
        value = suggestion.get("value")
        chosen = final.get(field)
        if chosen in EMPTY:
            verdict = "left_out"
        elif _same(chosen, value):
            verdict = "kept"
        else:
            verdict = "corrected"
        out[field] = {"proposed": value, "final": chosen, "verdict": verdict,
                      "confidence": suggestion.get("confidence"), "method": suggestion.get("method")}
    return out


def _predicate(field: str, suggestion: dict) -> Optional[tuple[str, object]]:
    if field == "name":
        return "name", suggestion["value"]
    if field == "schema_uid":
        return "type", suggestion.get("label")
    if field.startswith("attributes."):
        return f"attr:{field.split('.', 1)[1]}", suggestion["value"]
    return None                      # the key lives on the record's existence claim


def record(db: Session, workspace_id: str, actor: str, run_id: str, record_uid: str, final: dict) -> dict:
    run = db.get(IntakeRun, run_id)
    if run is None or run.workspace_id != workspace_id:
        raise OutcomeError("no such intake run in this workspace")
    if db.scalar(select(IntakeOutcome.id).where(IntakeOutcome.run_id == run_id)):
        raise OutcomeError("the outcome of this run is already recorded")
    proposed = (run.output or {}).get("fields") or {}
    fields = verdicts(proposed, final or {})
    if run.kind == "asset":
        asset = db.get(Asset, record_uid)
        if asset is None or asset.workspace_id != workspace_id:
            raise OutcomeError("the record is not an asset of this workspace")
        _ledger(db, workspace_id, actor, run, asset, proposed, fields)
    row = IntakeOutcome(run_id=run_id, workspace_id=workspace_id, record_kind=run.kind, record_uid=record_uid,
                        fields=fields, decided_by=actor)
    db.add(row)
    db.flush()
    counts: dict[str, int] = {}
    for f in fields.values():
        counts[f["verdict"]] = counts.get(f["verdict"], 0) + 1
    return {"run_id": run_id, "record_uid": record_uid, "fields": fields, "counts": counts}


def _ledger(db: Session, workspace_id: str, actor: str, run: IntakeRun, asset: Asset, proposed: dict,
            fields: dict) -> None:
    stream = engine.register_stream(db, f"ai:{workspace_id}:{run.operation}", workspace_id, "ai")
    claims, verdict_of = [], {}
    for field, suggestion in proposed.items():
        pv = _predicate(field, suggestion)
        if pv is None or pv[1] in EMPTY:
            continue
        predicate, value = pv
        c = ParsedClaim(f"uid:{asset.uid}", predicate, value, method=suggestion.get("method") or "ai_extracted",
                        rule_id=run.rule_id, confidence=suggestion.get("confidence"),
                        evidence={"intake_run": run.id, "quote": suggestion.get("evidence"),
                                  "grounded": suggestion.get("grounded")})
        claims.append(c)
        verdict_of[c.claim_id(stream.id)] = fields[field]["verdict"]
    if not claims:
        return
    ids = engine.add_manual_claims(db, stream, claims, cause=f"intake run {run.id}")
    batch = []
    for cid in ids:
        verdict = verdict_of.get(cid)
        if verdict == "kept":
            batch.append({"kind": "accept", "target": {"claim_id": cid}, "reason": f"kept from intake run {run.id}"})
        elif verdict in ("corrected", "left_out"):
            batch.append({"kind": "reject", "target": {"claim_id": cid},
                          "reason": "corrected" if verdict == "corrected" else "left out"})
    if batch:
        engine.apply_decisions(db, workspace_id, actor, batch)


def provenance(db: Session, workspace_id: str, record_uid: str) -> list[dict]:
    """The intake runs behind a record, as its owner reads them."""
    out = []
    for o in db.scalars(select(IntakeOutcome).where(IntakeOutcome.workspace_id == workspace_id,
                                                    IntakeOutcome.record_uid == record_uid)):
        run = db.get(IntakeRun, o.run_id)
        out.append({"run_id": o.run_id, "operation": run.operation if run else None,
                    "model": run.model if run else None, "provider": run.provider if run else None,
                    "prompt_version": run.prompt_version if run else None,
                    "requested_by": run.requested_by if run else None,
                    "at": o.at, "decided_by": o.decided_by, "fields": o.fields})
    return out
