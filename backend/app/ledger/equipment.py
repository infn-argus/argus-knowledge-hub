"""Equipment readiness (asset-model-revision §19 item 5).

* **Lifecycle** (`argus_lifecycle`): a governed set of operational states
  with the transitions allowed between them. `Installed` is not typed in:
  it follows from a current Confirmed Installation.
* **Custody** (`custodian`) and **location** (`argus_location`): their
  history is read back from the ledger — every value, who set it (a person
  or a source), and when it stopped holding.
* **Spares**: a unit flagged `is_designated_spare` is available when it is
  active, in stock and not installed anywhere now. A position's compatible
  spares are those of the product model it expects, or of the unit it holds.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ledger import engine, service
from app.ledger.engine import LedgerError
from app.models.asset import Asset
from app.models.ledger import Claim, ClaimEvent, Decision, IdentityBinding, LedgerStream, SourceRevision
from app.services.visibility import restriction_clause

LIFECYCLE = ("Planned", "Ordered", "In stock", "Installed", "In repair", "Decommissioned", "Scrapped")
TRANSITIONS = {
    None: {"Planned", "Ordered", "In stock", "In repair"},
    "Planned": {"Ordered", "In stock", "Decommissioned"},
    "Ordered": {"In stock", "Decommissioned"},
    "In stock": {"In repair", "Decommissioned", "Scrapped"},
    "Installed": {"In repair", "In stock"},
    "In repair": {"In stock", "Scrapped", "Decommissioned"},
    "Decommissioned": {"Scrapped", "In stock"},
    "Scrapped": set(),
}
NOT_EQUIPMENT = engine.INSTALLABLE | {engine.INSTALLATION, engine.ACCESS_POINT, "IOC", "Control Device",
                                       "Communication Path", "Bus Segment", "Equipment Port", "Location",
                                       "Procurement Record", "Product Model", "Vendor"}


def current_installation(db: Session, uid: str) -> Optional[dict]:
    hits = [h for h in engine.installations_at(db, engine.now(), asset_uid=uid) if h["certainty"] == "definite"]
    return hits[0] if hits else None


def lifecycle(db: Session, record: Asset) -> dict:
    """The effective state: `Installed` whenever the unit is installed now,
    otherwise the recorded one. The allowed next states come with it."""
    recorded = (record.attributes or {}).get("argus_lifecycle")
    recorded = recorded if recorded in LIFECYCLE else None
    installed = current_installation(db, record.uid)
    state = "Installed" if installed and recorded not in ("In repair",) else recorded
    return {"state": state, "recorded": recorded, "installation": installed,
            "allowed": sorted(TRANSITIONS.get(state, set()) - {"Installed"})}


def set_lifecycle(db: Session, workspace_id: str, actor: str, uid: str, state: str,
                  reason: Optional[str] = None) -> dict:
    record = db.get(Asset, uid)
    if record is None or record.workspace_id != workspace_id:
        raise LedgerError("not a record of this workspace")
    if state not in LIFECYCLE or state == "Installed":
        raise LedgerError("Installed follows from a Confirmed Installation; choose another state")
    now_ = lifecycle(db, record)
    if state not in TRANSITIONS.get(now_["state"], set()):
        raise LedgerError(f"{now_['state'] or 'no state'} → {state} is not an allowed transition "
                          f"(allowed: {', '.join(now_['allowed']) or 'none'})")
    if now_["installation"] and state != "In repair":
        raise LedgerError("the unit is installed now; end its installation (or swap it) first")
    service.edit_value(db, workspace_id, actor, uid, "attr:argus_lifecycle", state, reason)
    db.refresh(record)
    return lifecycle(db, record)


def value_history(db: Session, uid: str, name: str) -> dict:
    """Every value an attribute has had, oldest first: from people's
    decisions and from the sources' claims, with who and when."""
    predicate = f"attr:{name}"
    rows: list[dict] = []
    for d in db.scalars(select(Decision).where(Decision.subject_uid == uid, Decision.predicate == predicate,
                                               Decision.kind.in_(("confirm", "supersede", "revoke")))):
        rows.append({"at": d.at, "value": d.value, "by": d.actor, "via": "decision", "kind": d.kind,
                     "reason": d.reason})
    refs = [b.source_ref for b in db.scalars(select(IdentityBinding).where(IdentityBinding.uid == uid))]
    for c in db.scalars(select(Claim).where(Claim.source_ref.in_(refs), Claim.predicate == predicate,
                                            Claim.method != "manual")):
        stream = db.get(LedgerStream, c.stream_id)
        for ev in db.scalars(select(ClaimEvent).where(ClaimEvent.claim_id == c.claim_id,
                                                      ClaimEvent.kind == "appeared")):
            rev = db.get(SourceRevision, ev.revision_id)
            rows.append({"at": rev.observed_at if rev else ev.at, "value": c.value, "by": stream.id if stream else None,
                         "via": stream.kind if stream else "source", "kind": "stated"})
    rows.sort(key=lambda r: r["at"])
    current = (db.get(Asset, uid).attributes or {}).get(name)
    for i, r in enumerate(rows):
        r["until"] = rows[i + 1]["at"] if i + 1 < len(rows) else None
    return {"current": current, "history": rows}


def set_custodian(db: Session, workspace_id: str, actor: str, uid: str, custodian: str,
                  reason: Optional[str] = None) -> None:
    if not custodian:
        raise LedgerError("name the custodian")
    service.edit_value(db, workspace_id, actor, uid, "attr:custodian", custodian, reason)


def _is_spare(a: Asset) -> bool:
    return bool((a.attributes or {}).get("is_designated_spare"))


def spares(db: Session, workspace_ids: list[str], *, product_model: Optional[str] = None,
           type_name: Optional[str] = None) -> list[dict]:
    q = select(Asset).where(Asset.workspace_id.in_(workspace_ids), Asset.record_status == "Active",
                            restriction_clause(Asset))
    if type_name:
        q = q.where(Asset.type == type_name)
    if product_model:
        q = q.where(Asset.attributes["product_model"].astext == product_model)
    out = []
    for a in db.scalars(q):
        if not _is_spare(a) or a.type in NOT_EQUIPMENT:
            continue
        lc = lifecycle(db, a)
        available = lc["state"] in (None, "In stock") and lc["installation"] is None
        out.append({"uid": a.uid, "key": a.key, "name": a.name, "type": a.type, "workspace_id": a.workspace_id,
                    "product_model": (a.attributes or {}).get("product_model"),
                    "location": (a.attributes or {}).get("argus_location"),
                    "custodian": (a.attributes or {}).get("custodian"), "lifecycle": lc["state"],
                    "available": available,
                    "why_not": None if available else ("installed" if lc["installation"] else lc["state"])})
    return sorted(out, key=lambda s: (not s["available"], s["key"] or ""))


def spares_for_position(db: Session, position_uid: str, workspace_ids: list[str]) -> dict:
    """Spares that could go into this position: of the product model it
    expects, or of the unit it holds now; else of that unit's type."""
    position = db.get(Asset, position_uid)
    if position is None:
        raise LedgerError("unknown position")
    held = engine.installations_at(db, engine.now(), position_uid=position_uid)
    unit = db.get(Asset, held[0]["asset_uid"]) if held else None
    model = (position.attributes or {}).get("expected_product_model") or \
        ((unit.attributes or {}).get("product_model") if unit else None)
    if model:
        return {"basis": {"product_model": model}, "spares": spares(db, workspace_ids, product_model=model)}
    if unit is not None:
        return {"basis": {"type": unit.type}, "spares": spares(db, workspace_ids, type_name=unit.type)}
    return {"basis": None, "spares": []}
