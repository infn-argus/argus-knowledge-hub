"""Golden incidents: the root-cause walk's regression set (asset-model-revision
§12.6 I-MIG-7).

The teams record past incidents: their symptoms, what was healthy, and the
causes they know were behind them. The walk is run on each one. Across a
legacy migration it must keep finding every cause it found before, either
the same record or a more precisely resolved one (the Equipment a legacy
object became, the unit that realizes a Position): "equipment instead of
channel, never fewer".
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import lookup
from app.models.asset import Asset, Relation
from app.models.ledger import MigrationMap
from app.models.legacy_migration import GoldenIncident

TOP = 20


class GoldenError(ValueError):
    pass


def _resolve(db: Session, workspace_id: str, ref: str) -> Optional[str]:
    a = db.get(Asset, ref)
    if a is None:
        a = db.scalar(select(Asset).where(Asset.key == ref))
    if a is None:
        hit = lookup.resolve(db, ref, [workspace_id])
        a = db.get(Asset, hit["uid"]) if hit and hit.get("kind") == "asset" else None
    a = lookup._survivor(db, a) if a is not None else None
    return a.uid if a is not None else None


def record(db: Session, workspace_id: str, actor: str, *, name: str, symptoms: list[str], expected_causes: list[str],
           symptom_kind: Optional[dict] = None, healthy: Optional[list[str]] = None,
           ticket_uid: Optional[str] = None) -> GoldenIncident:
    if not name.strip() or not symptoms or not expected_causes:
        raise GoldenError("a golden incident needs a name, its symptoms and the causes behind it")
    resolved: dict[str, str] = {}
    unknown = []
    for ref in [*symptoms, *expected_causes, *(healthy or []), *(symptom_kind or {})]:
        if ref not in resolved:
            uid = _resolve(db, workspace_id, ref)
            if uid is None:
                unknown.append(ref)
            else:
                resolved[ref] = uid
    if unknown:
        raise GoldenError(f"not found: {', '.join(sorted(set(unknown)))}")
    g = GoldenIncident(id=f"GOLD-{uuid.uuid4().hex[:10]}", workspace_id=workspace_id, name=name,
                       symptoms=[resolved[s] for s in symptoms], expected_causes=[resolved[c] for c in expected_causes],
                       healthy=[resolved[h] for h in healthy or []],
                       symptom_kind={resolved[k]: v for k, v in (symptom_kind or {}).items()},
                       ticket_uid=ticket_uid, created_by=actor)
    db.add(g)
    db.flush()
    return g


def incidents(db: Session, workspace_id: str) -> list[GoldenIncident]:
    return list(db.scalars(select(GoldenIncident).where(GoldenIncident.workspace_id == workspace_id)
                           .order_by(GoldenIncident.created_at)))


def more_precise(db: Session, uid: str) -> set[str]:
    """The record itself, what a migration made of it, and the units that
    realize it (a Position resolves to its Equipment)."""
    out = {uid} | set(db.scalars(select(MigrationMap.new_uid).where(MigrationMap.legacy_uid == uid)))
    out |= set(db.scalars(select(Relation.to_asset_uid).where(Relation.from_asset_uid.in_(list(out)),
                                                              Relation.relation_type == "realized by")))
    return out


def evaluate(db: Session, g: GoldenIncident) -> dict:
    from app.services.root_cause import root_causes
    result = root_causes(db, g.workspace_id, list(g.symptoms), healthy=list(g.healthy or []), top=TOP,
                         symptom_kind=dict(g.symptom_kind or {}) or None)
    found = [c["uid"] for c in result["candidates"]]
    causes = {}
    for expected in g.expected_causes:
        match = next((f for f in found if f in more_precise(db, expected)), None)
        causes[expected] = {"found": match is not None, "as": match,
                            "rank": found.index(match) + 1 if match else None,
                            "more_precise": match is not None and match != expected}
    return {"incident": g.id, "name": g.name, "causes": causes, "found": sum(c["found"] for c in causes.values()),
            "expected": len(causes)}


def run(db: Session, workspace_id: str) -> dict:
    results = [evaluate(db, g) for g in incidents(db, workspace_id)]
    return {"workspace_id": workspace_id, "incidents": len(results),
            "found": sum(r["found"] for r in results), "expected": sum(r["expected"] for r in results),
            "results": results}


def compare(before: dict, after: dict) -> dict:
    """I-MIG-7: every cause found before is still found, the same or more
    precisely; never fewer."""
    after_by = {r["incident"]: r for r in after["results"]}
    lost = []
    for r in before["results"]:
        now = after_by.get(r["incident"])
        for cause, was in r["causes"].items():
            if was["found"] and not (now and now["causes"].get(cause, {}).get("found")):
                lost.append({"incident": r["name"], "cause": cause})
    refined = sum(1 for r in after["results"] for c in r["causes"].values() if c["more_precise"])
    return {"ok": not lost and after["found"] >= before["found"], "incidents": after["incidents"],
            "before": before["found"], "after": after["found"], "lost": lost, "more_precise": refined}
