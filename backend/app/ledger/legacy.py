"""Legacy migration (asset-model-revision §12): ARGUS's own inferred records
become Positions, Equipment and Installations.

    plan      gather the evidence of every inferred record (§12.1), classify it
              (§12.2), and write one item per record with its actions and a
              hash of its pre-image. Nothing is changed.
    override  an owner forces an item's outcome; recorded as a decision, and
              the item is re-planned.
    apply     item by item, in dependency order, each in its own savepoint.
              An item whose record changed since planning is `stale`; one that
              breaks an invariant is `failed` and leaves no trace.
    rollback  item by item in reverse order, until the plan is finalized or
              the domain cut over. Records the migration created are retired
              by ledger decisions; the legacy row gets its pre-image back.
    finalize  after sign-off; rollback is no longer possible.

Scope: records marked `argus_keywords: inferred` that no plan has migrated
yet. The classification checks M-RETIRE before M-POS: a stale inference
with no human evidence would otherwise always read as a pure control
identity, and never be retired.

E-RULE ("the current rules still produce this object") is read from the
importer's snapshots: the object was written by the workspace's latest
import run. A dry-run of the inference gives the same answer at far greater
cost; the snapshot is what that run left behind.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ledger import engine, golden, invariants, lookup, registry, service, temporal
from app.ledger.engine import INSTALLATION, LedgerError, ParsedClaim, canonical
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetComment, AssetHistory, AssetLabel, AssetTicket
from app.models.attachment import Attachment
from app.models.document import DocumentRelation
from app.models.import_snapshot import ImportSnapshot
from app.models.issue import Issue
from app.models.ledger import IdentityBinding, LedgerDomain, MigrationMap
from app.models.legacy_migration import LegacyMigrationItem, LegacyMigrationPlan
from app.ledger.writer import ledger_writer

SOURCE = "epik8s"
POSITION = "Equipment Position"
ELEMENTS = {"Quadrupole", "Dipole", "Corrector", "Solenoid", "Sextupole", "Beam Position Monitor", "Screen Station",
            "Mirror", "RF Gun", "Accelerating Structure", "RF Deflector", "Motion Axis"}
PHYSICAL = ("serial", "inventory_number", "manufacturer", "model", "argus_location", "location", "condition",
            "warranty", "installed_on")
IDENTIFIERS = ("serial", "inventory_number")
STRONG_LABELS = {"serial", "qrcode", "jiraObjectId", "inventory", "inventory_number"}
IMPORTER_AUTHORS = {"system", "importer", "ledger", SOURCE}
ORDER = {"M-BLOCK": 0, "M-FUNC": 0, "M-POS": 1, "M-PHYS": 2, "M-MIXED": 2, "M-EDGE": 3, "M-EDGE-HOLD": 3,
         "M-RETIRE": 4}
CONFIDENCE = {"M-BLOCK": 0.0, "M-FUNC": 1.0, "M-POS": 1.0, "M-PHYS": 0.95, "M-MIXED": 0.5, "M-RETIRE": 0.9,
              "M-EDGE": 1.0, "M-EDGE-HOLD": 0.0}
OUTCOMES = ("M-BLOCK", "M-FUNC", "M-POS", "M-PHYS", "M-MIXED", "M-RETIRE")      # a record's; edges have their own
EDGE_OUTCOMES = ("M-EDGE", "M-EDGE-HOLD")
# §12.3 step 4 and §6.2: the deprecated verbs, and what a person must do where no rewrite is mechanical.
HOLD_REASONS = {
    "on line": "a Serial Line becomes a Bus Segment behind its IOC's Communication Path (§9.1, §9.3); build the "
               "path, then remove this edge, or accept it as a registry exception",
    "carried by": "a Serial Line becomes a Bus Segment behind a Communication Path (§9.1, §9.3); build the path, "
                  "then remove this edge, or accept it as a registry exception",
    "port of": "a Serial Line's port becomes an advisory required_port on its Bus Segment (§9.3, §12.4)",
    "replaced": "a replacement is an Installation swap with its date (§8.4); record the swap, then remove this edge",
    "spare for": "a Position is not a spare: name the unit that is, then remove this edge",
}


class MigrationError(LedgerError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def _photo(label: AssetLabel) -> bool:
    issuer = (label.issuer or "").lower()
    return any(w in issuer for w in ("photo", "vision", "ai")) or bool((label.metadata_json or {}).get("attachment_uid"))


def _person(author: Optional[str]) -> bool:
    a = (author or "").lower()
    return bool(a) and a not in IMPORTER_AUTHORS and not a.startswith("import")


def _active(q):
    return q.where(Asset.deleted_at.is_(None), Asset.merged_into_uid.is_(None), Asset.record_status != "Retired")


# --------------------------------------------------------------------------- pre-image

def pre_image(db: Session, r: Asset) -> dict:
    """Everything an item may change, as it is now."""
    rels = [{"id": x.id, "from": x.from_asset_uid, "to": x.to_asset_uid, "type": x.relation_type,
             "derivation": x.derivation, "workspace_id": x.workspace_id}
            for x in db.scalars(select(Relation).where(or_(Relation.from_asset_uid == r.uid,
                                                           Relation.to_asset_uid == r.uid)).order_by(Relation.id))]
    return {
        "asset": {"key": r.key, "name": r.name, "type": r.type, "schema_uid": r.schema_uid,
                  "record_status": r.record_status, "attributes": r.attributes or {}},
        "labels": [{"uid": l.uid, "type": l.type, "value": l.value, "verified": l.verified}
                   for l in db.scalars(select(AssetLabel).where(AssetLabel.asset_uid == r.uid).order_by(AssetLabel.uid))],
        "attachments": sorted(db.scalars(select(Attachment.uid).where(Attachment.asset_uid == r.uid))),
        "relations": rels,
        "counts": dependents(db, [r.uid]),
    }


def _current_hash(db: Session, r: Asset, removed: dict[int, dict]) -> str:
    """The pre-image hash now, counting relations this run removed with a
    retired record as still there: they are the plan's own doing."""
    image = pre_image(db, r)
    back = [rel for rel in removed.values() if r.uid in (rel["from"], rel["to"])]
    image["relations"] = sorted(image["relations"] + back, key=lambda x: x["id"])
    return hash_image(image)


def hash_image(image: dict) -> str:
    return hashlib.sha256(canonical(image).encode()).hexdigest()


def dependents(db: Session, uids: list[str]) -> dict:
    """What hangs off these records, by kind (I-MIG-1)."""
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery())) or 0
    return {
        "tickets": count(select(AssetTicket.uid).where(AssetTicket.asset_uid.in_(uids)))
        + count(select(Issue.uid).where(Issue.asset_uid.in_(uids), Issue.deleted_at.is_(None))),
        "documents": count(select(DocumentRelation.id).where(DocumentRelation.to_type == "asset",
                                                             DocumentRelation.to_uid.in_(uids))),
        "comments": count(select(AssetComment.uid).where(AssetComment.asset_uid.in_(uids))),
        "attachments": count(select(Attachment.uid).where(Attachment.asset_uid.in_(uids))),
        "labels": count(select(AssetLabel.uid).where(AssetLabel.asset_uid.in_(uids),
                                                     AssetLabel.type != "former_key")),
        "history": count(select(AssetHistory.uid).where(AssetHistory.asset_uid.in_(uids))),
    }


# --------------------------------------------------------------------------- evidence (§12.1)

def _latest_ref(db: Session, workspace_id: str) -> Optional[str]:
    return db.scalar(select(ImportSnapshot.source_ref).join(Asset, Asset.uid == ImportSnapshot.asset_uid)
                     .where(Asset.workspace_id == workspace_id, ImportSnapshot.source == SOURCE)
                     .order_by(ImportSnapshot.updated_at.desc()).limit(1))


def _holders(db: Session, r: Asset, field: str, value: str) -> list[Asset]:
    by_attr = select(Asset).where(Asset.uid != r.uid, Asset.attributes.contains({field: value}))
    by_label = select(Asset).join(AssetLabel, AssetLabel.asset_uid == Asset.uid).where(
        Asset.uid != r.uid, AssetLabel.type == field, AssetLabel.value == value)
    seen = {}
    for q in (by_attr, by_label):
        for a in db.scalars(_active(q)):
            seen[a.uid] = a
    return list(seen.values())


def evidence(db: Session, r: Asset, inventory_ws: str, latest_ref: Optional[str]) -> dict:
    attrs = r.attributes or {}
    snap = db.get(ImportSnapshot, (r.uid, SOURCE))
    prev = snap.values if snap is not None else None

    def by_person(k: str) -> bool:
        return prev is None or k not in prev or prev.get(k) != attrs.get(k)

    labels = list(db.scalars(select(AssetLabel).where(AssetLabel.asset_uid == r.uid)))
    ser = [{"field": k, "value": str(attrs[k]), "author": "person" if by_person(k) else "importer"}
           for k in IDENTIFIERS if attrs.get(k)]
    lbl = [{"uid": l.uid, "type": l.type, "value": l.value, "verified": bool(l.verified), "issuer": l.issuer,
            "photo": _photo(l)} for l in labels if l.type in STRONG_LABELS]

    url = None
    raw_url = attrs.get("inventory_url")
    if raw_url:
        parsed = lookup.parse(str(raw_url))
        object_id = parsed.get("object_id") or (parsed.get("key") if str(parsed.get("key", "")).isdigit() else None)
        if object_id:
            matches = set()
            b = db.get(IdentityBinding, f"insight:object:{object_id}")
            if b is not None:
                survivor = lookup._survivor(db, db.get(Asset, b.uid))
                if survivor is not None and survivor.uid != r.uid:
                    matches.add(survivor.uid)
            matches |= {a.uid for a in _holders(db, r, "jiraObjectId", str(object_id))}
            url = {"object_id": str(object_id), "matches": sorted(matches)}

    # The same identifier on another record: the inventory's record of this
    # unit, or a collision.
    identifier_matches, collisions = set(), []
    for field, value in [(s["field"], s["value"]) for s in ser] + [(l["type"], l["value"]) for l in lbl if l["verified"]]:
        for other in _holders(db, r, field, value):
            if url and other.uid in url["matches"]:
                continue
            m1, m2 = (attrs.get("manufacturer") or "").lower(), ((other.attributes or {}).get("manufacturer") or "").lower()
            if other.workspace_id == inventory_ws and not (m1 and m2 and m1 != m2):
                identifier_matches.add(other.uid)
            else:
                collisions.append({"field": field, "value": value, "held_by": other.uid, "key": other.key})

    attachments = list(db.scalars(select(Attachment.uid).where(Attachment.asset_uid == r.uid)))
    deps = dependents(db, [r.uid])
    from_photos = {(l.metadata_json or {}).get("attachment_uid") for l in labels if _photo(l)} - {None}
    edits = {"physical": [], "functional": []}
    if prev is not None:
        for k, v in attrs.items():
            if k.startswith("argus_source") or k in ("argus_facility", "argus_keywords"):
                continue
            if (k in prev and prev[k] != v) or (k not in prev):
                edits["physical" if k in PHYSICAL else "functional"].append(k)
        if prev.get("__name__") not in (None, r.name):
            edits["functional"].append("name")
    history = list(db.scalars(select(AssetHistory).where(AssetHistory.asset_uid == r.uid)
                              .order_by(AssetHistory.timestamp)))
    contradiction = sorted({s["value"] for s in ser if s["field"] == "serial"}
                           ^ {l["value"] for l in lbl if l["type"] == "serial" and l["verified"]}) \
        if any(l["type"] == "serial" and l["verified"] for l in lbl) and any(s["field"] == "serial" for s in ser) else []
    return {
        "E-SER": ser, "E-LBL": lbl, "E-URL": url,
        "E-ATT": {"count": len(attachments), "with_identifier": sorted(from_photos & set(attachments))},
        "E-TKT": deps["tickets"],
        "E-DOC": deps["documents"] + deps["comments"],
        "E-EDIT": edits,
        "E-HIST": {"person": sum(1 for h in history if _person(h.author)),
                   "created_by": "importer" if attrs.get("argus_source") else "person",
                   "first": history[0].timestamp.isoformat() if history else None},
        "E-RULE": None if snap is None or latest_ref is None else snap.source_ref == latest_ref,
        "E-COLL": collisions,
        "identifier_matches": sorted(identifier_matches),
        "contradiction": contradiction,
    }


# --------------------------------------------------------------------------- classification (§12.2)

def classify(r: Asset, ev: dict) -> str:
    if ev["E-COLL"]:
        return "M-BLOCK"
    if r.type in ELEMENTS:
        return "M-FUNC"
    edits = ev["E-EDIT"]
    human = (ev["E-TKT"] or ev["E-DOC"] or ev["E-ATT"]["count"] or edits["physical"] or edits["functional"]
             or ev["E-HIST"]["person"])
    if ev["E-RULE"] is False and not human:
        return "M-RETIRE"
    url_matches = (ev["E-URL"] or {}).get("matches", [])
    physical = (ev["E-SER"] or ev["E-LBL"] or ev["E-URL"] or edits["physical"] or ev["E-ATT"]["with_identifier"])
    if ev["E-HIST"]["created_by"] == "importer" and not physical:
        return "M-POS"
    strong = (any(s["author"] == "person" for s in ev["E-SER"]) or any(l["verified"] for l in ev["E-LBL"])
              or len(url_matches) == 1)
    if strong and not ev["contradiction"] and len(url_matches) <= 1:
        return "M-PHYS"
    return "M-MIXED"


def _initials(type_name: str) -> str:
    return "".join(w[0] for w in type_name.split() if w).upper() or "X"


def _position_key(db: Session, r: Asset, taken: set[str]) -> str:
    fac = (r.attributes or {}).get("argus_facility") or r.key.split(":")[0]
    tag = r.key.rsplit(":", 1)[-1]
    for candidate in (f"{fac}:POS:{tag}", f"{fac}:POS:{tag}/{_initials(r.type)}", f"{fac}:POS:{tag}/{r.uid[:8]}"):
        if candidate in taken:
            continue
        holder = db.scalar(select(Asset.uid).where(Asset.key == candidate))
        if holder is None or holder == r.uid:
            taken.add(candidate)
            return candidate
    raise MigrationError(f"no free position key for {r.key}")


def actions_for(db: Session, r: Asset, ev: dict, outcome: str, inventory_ws: str, taken: set[str]) -> list[dict]:
    attrs = r.attributes or {}
    if outcome in ("M-BLOCK", "M-FUNC"):
        return [{"do": "keep"}]
    if outcome == "M-RETIRE":
        return [{"do": "retire"}]
    out = [{"do": "retype", "to": POSITION, "key": _position_key(db, r, taken), "equipment_class": r.type}]
    if outcome == "M-POS":
        return out
    matches = (ev["E-URL"] or {}).get("matches") or ev["identifier_matches"]
    match = matches[0] if outcome == "M-PHYS" and len(set(matches)) == 1 else None
    physical = {k: attrs[k] for k in PHYSICAL if attrs.get(k) not in (None, "")}
    by_person = sorted({s["field"] for s in ev["E-SER"] if s["author"] == "person"} | set(ev["E-EDIT"]["physical"]))
    out.append({"do": "equipment", "match": match, "workspace": inventory_ws, "type": r.type,
                "status": "Active" if outcome == "M-PHYS" else "Provisional",
                "attributes": {} if match else physical, "person_fields": by_person,
                "confirmed": by_person if outcome == "M-PHYS" else []})
    installed_on = attrs.get("installed_on")
    if installed_on and "installed_on" in by_person:
        valid_from = temporal.instant(installed_on, "day")
    else:
        valid_from = {"kind": "before_records", "bound": ev["E-HIST"]["first"] or now().isoformat()}
    out.append({"do": "installation", "status": "Confirmed" if outcome == "M-PHYS" else "Proposed",
                "valid_from": valid_from})
    labels = [l["uid"] for l in ev["E-LBL"]]
    if labels:
        out.append({"do": "move_labels", "labels": labels})
    if ev["E-ATT"]["with_identifier"]:
        out.append({"do": "move_attachments", "attachments": ev["E-ATT"]["with_identifier"]})
    return out


def _warnings(outcome: str, ev: dict) -> list[str]:
    w = []
    if outcome == "M-BLOCK":
        w += [f"{c['field']} {c['value']} is also held by {c['key']}" for c in ev["E-COLL"]]
    if outcome == "M-MIXED":
        if ev["contradiction"]:
            w.append("the serial and a verified serial label disagree")
        if ev["E-URL"] and len(ev["E-URL"]["matches"]) != 1:
            w.append(f"inventory objectId {ev['E-URL']['object_id']} matches {len(ev['E-URL']['matches'])} records")
        w.append("a reviewer confirms the Provisional Equipment and the Proposed Installation")
    if ev["E-RULE"] is None:
        w.append("no importer snapshot: whether the rules still produce it is unknown")
    return w


# --------------------------------------------------------------------------- plan (§12.3)

def _scope(db: Session, workspace_id: str) -> list[Asset]:
    # Applied by a plan and not rolled back (the map itself is append-only).
    migrated = select(LegacyMigrationItem.legacy_uid).where(LegacyMigrationItem.status == "applied")
    q = _active(select(Asset).where(Asset.workspace_id == workspace_id,
                                    Asset.attributes.contains({"argus_keywords": ["inferred"]}),
                                    Asset.uid.not_in(migrated)))
    return list(db.scalars(q.order_by(Asset.key)))


def _plan_item(db: Session, plan: LegacyMigrationPlan, r: Asset, latest: Optional[str], taken: set[str],
               forced: Optional[str] = None) -> LegacyMigrationItem:
    ev = evidence(db, r, plan.inventory_workspace_id, latest)
    outcome = forced or classify(r, ev)
    image = pre_image(db, r)
    return LegacyMigrationItem(plan_id=plan.id, legacy_uid=r.uid, legacy_key=r.key, legacy_type=r.type,
                               outcome=outcome, confidence=CONFIDENCE[outcome] if not forced else 1.0, evidence=ev,
                               actions=actions_for(db, r, ev, outcome, plan.inventory_workspace_id, taken),
                               warnings=_warnings(outcome, ev), pre_image=image, pre_image_hash=hash_image(image),
                               status="planned", updated_at=now())


def _edge_image(db: Session, rel: Relation, attrs: tuple = ()) -> dict:
    a = db.get(Asset, rel.from_asset_uid)
    return {"relation": {"id": rel.id, "from": rel.from_asset_uid, "to": rel.to_asset_uid, "type": rel.relation_type,
                         "derivation": rel.derivation, "workspace_id": rel.workspace_id},
            "attrs": {k: (a.attributes or {}).get(k) for k in attrs} if a is not None else {}}


def edge_action(db: Session, rel: Relation) -> tuple[str, dict, list[str]]:
    """The rewrite of one deprecated edge (§12.3 step 4), or why a person must decide."""
    a, b = db.get(Asset, rel.from_asset_uid), db.get(Asset, rel.to_asset_uid)
    name = rel.relation_type
    if name == "assigned to" and b.type == "Work Package":
        return "M-EDGE", {"do": "edge_to_attribute", "set": {"work_package": b.uid},
                          "label": f"work_package = {b.key}",
                          "note": "the work package becomes an attribute; `in work package` is derived from it"}, []
    if name == "spare for" and a.type not in engine.INSTALLABLE and b.type not in engine.INSTALLABLE:
        values = {"is_designated_spare": True}
        if (b.attributes or {}).get("product_model"):
            values["product_model"] = b.attributes["product_model"]
        return "M-EDGE", {"do": "edge_to_attribute", "set": values,
                          "label": "designated spare" + (f", product model {values['product_model']}"
                                                         if "product_model" in values else ""),
                          "note": "the unit becomes a designated spare for the product model"}, []
    return "M-EDGE-HOLD", {"do": "hold_edge"}, [HOLD_REASONS.get(name, "no mechanical rewrite")]


def _plan_edges(db: Session, p: LegacyMigrationPlan, retiring: set[str]) -> None:
    from app.ledger.registry import DEPRECATED
    q = (select(Relation).join(Asset, Asset.uid == Relation.from_asset_uid)
         .where(Asset.workspace_id == p.workspace_id, Relation.derivation.is_(None),
                or_(Relation.relation_type.in_(DEPRECATED), Relation.relation_type == "assigned to"))
         .order_by(Relation.id))
    for rel in db.scalars(q):
        a, b = db.get(Asset, rel.from_asset_uid), db.get(Asset, rel.to_asset_uid)
        if a is None or b is None or {a.uid, b.uid} & retiring:
            continue                     # retiring a record takes its edges with it
        if rel.relation_type == "assigned to" and b.type != "Work Package":
            continue                     # the current `assigned to` (Access Point → Position)
        if rel.relation_type == "port of" and a.type != "Serial Line":
            continue                     # only a Serial Line's `port of` is deprecated
        outcome, action, warnings = edge_action(db, rel)
        image = _edge_image(db, rel, tuple(action.get("set", {})))
        db.add(LegacyMigrationItem(plan_id=p.id, legacy_uid=f"edge:{rel.id}",
                                   legacy_key=f"{a.key} —{rel.relation_type}→ {b.key}", legacy_type=rel.relation_type,
                                   outcome=outcome, confidence=CONFIDENCE[outcome], evidence={"from": a.uid, "to": b.uid},
                                   actions=[action], warnings=warnings, pre_image=image,
                                   pre_image_hash=hash_image(image), status="planned", updated_at=now()))


def plan(db: Session, workspace_id: str, actor: str, inventory_workspace_id: Optional[str] = None) -> LegacyMigrationPlan:
    p = LegacyMigrationPlan(id=f"MIG-{engine.ulid()}", workspace_id=workspace_id,
                            inventory_workspace_id=inventory_workspace_id or workspace_id, status="planned",
                            created_by=actor, created_at=now())
    db.add(p)
    db.flush()
    latest, taken = _latest_ref(db, workspace_id), set()
    retiring = set()
    for r in _scope(db, workspace_id):
        item = _plan_item(db, p, r, latest, taken)
        db.add(item)
        if item.outcome == "M-RETIRE":
            retiring.add(r.uid)
    db.flush()
    _plan_edges(db, p, retiring)
    db.flush()
    p.report_hash = hashlib.sha256(canonical(report(db, p)).encode()).hexdigest()
    engine._record_decision(db, "migration_plan", actor, workspace_id, target={"plan": p.id},
                            value={"items": len(items(db, p.id)), "report_hash": p.report_hash})
    db.flush()
    return p


def items(db: Session, plan_id: str) -> list[LegacyMigrationItem]:
    return list(db.scalars(select(LegacyMigrationItem).where(LegacyMigrationItem.plan_id == plan_id)
                           .order_by(LegacyMigrationItem.id)))


def _plan(db: Session, plan_id: str) -> LegacyMigrationPlan:
    p = db.get(LegacyMigrationPlan, plan_id)
    if p is None:
        raise MigrationError(f"unknown plan {plan_id}")
    return p


def override(db: Session, plan_id: str, item_id: int, outcome: str, actor: str, reason: str) -> LegacyMigrationItem:
    p = _plan(db, plan_id)
    item = db.get(LegacyMigrationItem, item_id)
    if item is None or item.plan_id != p.id:
        raise MigrationError("unknown item")
    if item.status not in ("planned", "failed", "stale"):
        raise MigrationError("only an item not yet applied can be overridden")
    if item.outcome in EDGE_OUTCOMES:
        raise MigrationError("an edge's rewrite follows the registry; fix or accept the edge instead")
    if outcome not in OUTCOMES or (outcome == "M-FUNC") != (item.legacy_type in ELEMENTS):
        raise MigrationError(f"{outcome} is not a possible outcome for a {item.legacy_type}")
    if not reason.strip():
        raise MigrationError("an override needs a reason")
    r = db.get(Asset, item.legacy_uid)
    decision = engine._record_decision(db, "migration_override", actor, p.workspace_id, subject_uid=r.uid,
                                       target={"plan": p.id, "item": item.id}, value={"from": item.outcome, "to": outcome},
                                       reason=reason)
    fresh = _plan_item(db, p, r, _latest_ref(db, p.workspace_id), set(), forced=outcome)
    for field in ("outcome", "confidence", "evidence", "actions", "warnings", "pre_image", "pre_image_hash"):
        setattr(item, field, getattr(fresh, field))
    item.override = {"outcome": outcome, "by": actor, "reason": reason, "decision_id": decision.decision_id}
    item.status, item.reason = "planned", None
    db.flush()
    return item


# --------------------------------------------------------------------------- report (§12.5)

def report_row(item: LegacyMigrationItem) -> dict:
    return {"item": item.id, "legacy_uid": item.legacy_uid, "legacy_key": item.legacy_key,
            "legacy_type": item.legacy_type, "outcome": item.outcome, "confidence": item.confidence,
            "evidence": item.evidence, "actions": item.actions, "warnings": item.warnings,
            "reviewer_required": item.outcome in ("M-MIXED", "M-BLOCK"), "override": item.override,
            "status": item.status, "reason": item.reason, "applied": item.applied,
            "dependents": item.pre_image.get("counts")}


def report(db: Session, p: LegacyMigrationPlan) -> dict:
    rows = [report_row(i) for i in items(db, p.id)]
    counts: dict = {}
    for r in rows:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return {"plan": p.id, "workspace_id": p.workspace_id, "inventory_workspace_id": p.inventory_workspace_id,
            "outcomes": counts, "rows": rows}


def evidence_codes(ev: dict) -> str:
    parts = [f"E-SER({s['field']}={s['value']}, {s['author']})" for s in ev.get("E-SER", [])]
    parts += [f"E-LBL({l['type']}={l['value']}{', verified' if l['verified'] else ''})" for l in ev.get("E-LBL", [])]
    if ev.get("E-URL"):
        parts.append(f"E-URL(objectId={ev['E-URL']['object_id']} → {len(ev['E-URL']['matches'])} match)")
    if ev.get("E-ATT", {}).get("count"):
        parts.append(f"E-ATT({ev['E-ATT']['count']})")
    for kind in ("physical", "functional"):
        if ev.get("E-EDIT", {}).get(kind):
            parts.append(f"E-EDIT({kind}: {', '.join(ev['E-EDIT'][kind])})")
    if ev.get("E-TKT"):
        parts.append(f"E-TKT({ev['E-TKT']})")
    if ev.get("E-RULE") is False:
        parts.append("E-RULE(false)")
    if ev.get("E-COLL"):
        parts.append(f"E-COLL({len(ev['E-COLL'])})")
    return "; ".join(parts)


def report_csv(db: Session, p: LegacyMigrationPlan) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["legacy_uid", "legacy_key", "legacy_type", "workspace", "outcome", "confidence", "evidence",
                "planned_records", "warnings", "reviewer_required", "override", "status"])
    for i in items(db, p.id):
        planned = "; ".join(
            f"position {a['key']}" if a["do"] == "retype" else
            f"equipment {'matched ' + a['match'] if a['match'] else a['status'] + ' in ' + a['workspace']}"
            if a["do"] == "equipment" else f"installation {a['status']}" if a["do"] == "installation" else a["do"]
            for a in i.actions)
        w.writerow([i.legacy_uid, i.legacy_key, i.legacy_type, p.workspace_id, i.outcome, i.confidence,
                    evidence_codes(i.evidence), planned, " | ".join(i.warnings),
                    i.outcome in ("M-MIXED", "M-BLOCK"), (i.override or {}).get("reason", ""), i.status])
    return buf.getvalue()


# --------------------------------------------------------------------------- apply (§12.3, §12.4)

def _assert_open(db: Session, p: LegacyMigrationPlan) -> None:
    if p.finalized_at is not None:
        raise MigrationError("the plan is finalized")
    cut = db.scalar(select(LedgerDomain.id).where(LedgerDomain.workspace_id == p.workspace_id,
                                                  LedgerDomain.exited_at.isnot(None)).limit(1))
    if cut is not None:
        raise MigrationError(f"the workspace's domain {cut} has cut over; migrate before the cutover (D11)")


def _new_equipment(db: Session, actor: str, a: dict, r: Asset) -> str:
    # §12.4: what a person wrote is `manual`; what the importer wrote is `stated`. The unit
    # itself is the migration's inference when the evidence is mixed, so it stays Provisional.
    ref = f"person:eq:{engine.ulid()}"
    exists = "manual" if a["status"] == "Active" else "inferred"
    claims = [ParsedClaim(ref, "exists", {"type": a["type"], "name": r.name}, method=exists)]
    claims += [ParsedClaim(ref, f"attr:{k}", v, method="manual" if k in a.get("person_fields", []) else "stated")
               for k, v in sorted(a["attributes"].items())]
    stream = engine.person_stream(db, a["workspace"], actor)
    engine.add_manual_claims(db, stream, claims, cause=f"migration {actor}")
    uid = engine.resolve_ref(db, ref)
    engine.project_subject(db, uid, f"migration {actor}")
    return uid


def _apply_item(db: Session, p: LegacyMigrationPlan, item: LegacyMigrationItem, actor: str) -> dict:
    r = db.get(Asset, item.legacy_uid)
    if r is None:
        raise MigrationError("the legacy record is gone")
    done: dict = {"position": None, "equipment": None, "equipment_created": False, "installation": None,
                  "moved_labels": [], "moved_attachments": [], "former_key_label": None, "removed_relations": []}
    roles = []
    for a in item.actions:
        if a["do"] == "keep":
            roles.append(("position", r.uid))
        elif a["do"] == "retire":
            for rel in item.pre_image["relations"]:
                row = db.get(Relation, rel["id"])
                if row is not None:
                    db.delete(row)
                    done["removed_relations"].append(rel)
            r.record_status = "Retired"
            roles.append(("position", r.uid))
        elif a["do"] == "retype":
            label = AssetLabel(uid=str(uuid.uuid4()), asset_uid=r.uid, type="former_key", value=r.key,
                               issuer=f"migration:{p.id}", verified=True, created_at=now(), updated_at=now())
            db.add(label)
            done["former_key_label"] = label.uid
            r.type, r.key = POSITION, a["key"]
            r.schema_uid = engine.ensure_type(db, r.workspace_id, POSITION).uid
            r.attributes = {**(r.attributes or {}), "equipment_class": a["equipment_class"]}
            done["position"] = r.uid
            roles.append(("position", r.uid))
        elif a["do"] == "equipment":
            # §12.4: physical fields belong to the Equipment, functional ones stay on the Position.
            r.attributes = {k: v for k, v in (r.attributes or {}).items() if k not in PHYSICAL}
            if a["match"]:
                target = lookup._survivor(db, db.get(Asset, a["match"]))
                if target is None:
                    raise MigrationError("the matched inventory record is gone")
                done["equipment"] = target.uid
            else:
                done["equipment"] = _new_equipment(db, actor, a, r)
                done["equipment_created"] = True
                batch = []
                if a["status"] == "Active":
                    batch.append(service.confirm_value(done["equipment"], "exists", "present"))
                    for k in a["confirmed"]:
                        if k in a["attributes"]:
                            batch.append(service.confirm_value(done["equipment"], f"attr:{k}", a["attributes"][k]))
                if batch:
                    done.setdefault("decisions", []).extend(
                        d.decision_id for d in engine.apply_decisions(db, a["workspace"], actor, batch))
            roles.append(("equipment", done["equipment"]))
        elif a["do"] == "installation":
            inst = service.new_installation_claims(db, r.workspace_id, actor, r.uid, done["equipment"],
                                                   a["valid_from"])
            if a["status"] == "Confirmed":
                service.confirm_installation(db, r.workspace_id, actor, inst)
            done["installation"] = inst
            roles.append(("installation", inst))
        elif a["do"] == "move_labels":
            for uid in a["labels"]:
                label = db.get(AssetLabel, uid)
                if label is not None and label.asset_uid == r.uid:
                    label.asset_uid = done["equipment"]
                    done["moved_labels"].append(uid)
        elif a["do"] == "move_attachments":
            for uid in a["attachments"]:
                att = db.get(Attachment, uid)
                if att is not None and att.asset_uid == r.uid:
                    att.asset_uid = done["equipment"]
                    done["moved_attachments"].append(uid)
    for role, uid in roles:
        db.add(MigrationMap(legacy_uid=r.uid, new_uid=uid, role=role, plan_id=p.id))
    db.flush()
    return done


def _item_invariants(db: Session, item: LegacyMigrationItem, done: dict) -> list[str]:
    """I-MIG-1 (nothing lost) and I-MIG-2 (traceable) for one item."""
    problems = []
    uids = [item.legacy_uid] + ([done["equipment"]] if done.get("equipment_created") else [])
    after = dependents(db, uids)
    before = dict(item.pre_image["counts"])
    if done.get("equipment") and not done.get("equipment_created"):
        # Matched inventory records keep their own dependents; count only what moved to them.
        after["labels"] = dependents(db, [item.legacy_uid])["labels"] + len(done["moved_labels"])
        after["attachments"] = dependents(db, [item.legacy_uid])["attachments"] + len(done["moved_attachments"])
    for kind, n in before.items():
        if kind == "history":
            continue
        if after.get(kind) != n:
            problems.append(f"I-MIG-1: {kind} {n} before, {after.get(kind)} after")
    if db.scalar(select(func.count()).select_from(MigrationMap).where(MigrationMap.legacy_uid == item.legacy_uid)) == 0:
        problems.append("I-MIG-2: the legacy uid is not in migration_map")
    r = db.get(Asset, item.legacy_uid)
    if r.key != item.legacy_key and db.scalar(select(AssetLabel.uid).where(
            AssetLabel.asset_uid == r.uid, AssetLabel.type == "former_key", AssetLabel.value == item.legacy_key)) is None:
        problems.append("I-MIG-2: the legacy key no longer resolves")
    return problems


@ledger_writer
def apply(db: Session, plan_id: str, actor: str) -> LegacyMigrationPlan:
    p = _plan(db, plan_id)
    _assert_open(db, p)
    if p.status in ("rolled_back",):
        raise MigrationError("a rolled-back plan is not applied again; plan afresh")
    if "registry_before" not in (p.invariants or {}):
        # I-MIG-5's baseline: the registry report before the first item moves.
        before = registry.report(db, {p.workspace_id, p.inventory_workspace_id})
        p.invariants = {**(p.invariants or {}),
                        "registry_before": {"total": before["total"], "counts": before["counts"]},
                        # I-MIG-7's baseline: the golden incidents walked before anything moves.
                        "golden_before": golden.run(db, p.workspace_id)}
    todo = [i for i in items(db, p.id) if i.status in ("planned", "failed")]
    removed: dict[int, dict] = {}         # relations this run removed with retired records
    for item in sorted(todo, key=lambda i: (ORDER[i.outcome], i.id)):
        if item.outcome in EDGE_OUTCOMES:
            _apply_edge(db, p, item, actor)
            continue
        r = db.get(Asset, item.legacy_uid)
        if r is None or _current_hash(db, r, removed) != item.pre_image_hash:
            item.status, item.reason = "stale", "the record changed after planning; plan it again"
            continue
        if item.outcome == "M-BLOCK":
            item.status, item.reason = "failed", "blocked: resolve the collision, then override or re-plan"
            continue
        savepoint = db.begin_nested()
        try:
            done = _apply_item(db, p, item, actor)
            problems = _item_invariants(db, item, done)
            if problems:
                raise MigrationError("; ".join(problems))
            savepoint.commit()
            item.status, item.reason, item.applied = "applied", None, done
            removed.update({rel["id"]: rel for rel in done["removed_relations"]})
        except (LedgerError, ValueError) as exc:
            savepoint.rollback()
            item.status, item.reason = "failed", str(exc)
        item.updated_at = now()
    db.flush()
    p.applied_at = now()
    p.invariants = {**(p.invariants or {}), **verify(db, p)}
    p.status = "verified" if p.invariants["ok"] else "needs_attention"
    engine._record_decision(db, "migration_apply", actor, p.workspace_id, target={"plan": p.id},
                            value={"status": p.status, "invariants": p.invariants["summary"]})
    db.flush()
    return p


def _apply_edge(db: Session, p: LegacyMigrationPlan, item: LegacyMigrationItem, actor: str) -> None:
    rel = db.get(Relation, item.pre_image["relation"]["id"])
    if rel is None or hash_image(_edge_image(db, rel, tuple(item.pre_image["attrs"]))) != item.pre_image_hash:
        item.status, item.reason = "stale", "the edge or its record changed after planning; plan it again"
        return
    action = item.actions[0]
    if action["do"] == "hold_edge":
        item.status, item.applied = "applied", {"held": True, "from": rel.from_asset_uid}
        item.reason = None                        # the warning already says what the person must do
        item.updated_at = now()
        return
    savepoint = db.begin_nested()
    try:
        service.edit_values(db, p.workspace_id, actor, rel.from_asset_uid,
                            {f"attr:{k}": v for k, v in action["set"].items()},
                            reason=f"{rel.relation_type} rewritten by {p.id}")
        snapshot = dict(item.pre_image["relation"])
        service.remove_legacy_edge(db, p.workspace_id, actor, rel, reason=f"rewritten by {p.id}")
        savepoint.commit()
        item.status, item.reason = "applied", None
        item.applied = {"from": snapshot["from"], "set": action["set"], "removed_relations": [snapshot]}
    except (LedgerError, ValueError) as exc:
        savepoint.rollback()
        item.status, item.reason = "failed", str(exc)
    item.updated_at = now()


def _rollback_edge(db: Session, p: LegacyMigrationPlan, item: LegacyMigrationItem, actor: str) -> None:
    from app.ledger.writer import writing
    done = item.applied or {}
    if not done.get("held"):
        service.edit_values(db, p.workspace_id, actor, done["from"],
                            {f"attr:{k}": v for k, v in item.pre_image["attrs"].items()},
                            reason=f"rollback of {p.id}")
        with writing(db):
            for rel in done.get("removed_relations", []):
                db.add(Relation(workspace_id=rel["workspace_id"], from_asset_uid=rel["from"], to_asset_uid=rel["to"],
                                relation_type=rel["type"], derivation=rel["derivation"]))
            engine._record_decision(db, "restore_legacy_edge", actor, p.workspace_id, subject_uid=done["from"],
                                    target={"plan": p.id, "item": item.id}, reason=f"rollback of {p.id}")
    item.status, item.reason, item.updated_at = "rolled_back", f"rollback of {p.id}", now()
    db.flush()


def verify(db: Session, p: LegacyMigrationPlan) -> dict:
    """Plan-wide invariants. I-MIG-1 and I-MIG-2 were checked per item as it
    was applied; I-MIG-3 needs the whole plan."""
    all_items = items(db, p.id)
    applied = [i for i in all_items if i.status == "applied"]
    retired = {i.legacy_uid for i in applied if i.outcome == "M-RETIRE"}
    dangling = db.scalar(select(func.count()).select_from(Relation).where(
        or_(Relation.from_asset_uid.in_(retired), Relation.to_asset_uid.in_(retired)))) if retired else 0
    untraced = [i.legacy_uid for i in applied if i.outcome not in EDGE_OUTCOMES and not db.scalar(
        select(func.count()).select_from(MigrationMap).where(MigrationMap.legacy_uid == i.legacy_uid,
                                                            MigrationMap.plan_id == p.id))]
    open_items = [i.id for i in all_items if i.status in ("failed", "stale", "planned")]
    checks = {"I-MIG-2": not untraced, "I-MIG-3": dangling == 0, "all_items_applied": not open_items}
    return {"ok": all(checks.values()), "checks": checks,
            "summary": {"applied": len(applied), "open": len(open_items), "dangling_relations": dangling,
                        "untraced": len(untraced)},
            "deep": "I-MIG-4 to I-MIG-7 run in the deep verification, required before finalizing",
            "not_automated": []}


def _state(db: Session, uids: list[str]) -> dict:
    """What the projection says about these records: identity, status,
    attributes and the edges the ledger wrote."""
    out = {}
    for uid in sorted(set(uids)):
        a = db.get(Asset, uid)
        if a is None:
            out[uid] = None
            continue
        edges = sorted((r.relation_type, r.to_asset_uid, r.derivation) for r in db.scalars(
            select(Relation).where(Relation.from_asset_uid == uid, Relation.derivation.isnot(None))))
        out[uid] = {"key": a.key, "type": a.type, "record_status": a.record_status,
                    "attributes": json.loads(canonical(a.attributes or {})), "edges": [list(e) for e in edges]}
    return out


def deep_verify(db: Session, plan_id: str, actor: str) -> LegacyMigrationPlan:
    """I-MIG-4 (the data invariants hold), I-MIG-5 (the registry report
    does not get worse) and I-MIG-6 (a
    rebuild of the workspaces from the ledger gives exactly the migrated
    state). The rebuild runs in a savepoint and is rolled back."""
    p = _plan(db, plan_id)
    if p.applied_at is None:
        raise MigrationError("apply the plan first")
    workspaces = sorted({p.workspace_id, p.inventory_workspace_id})
    after = registry.report(db, workspaces)
    baseline = (p.invariants or {}).get("registry_before")
    mig5 = registry.compare(baseline, after) if baseline else {"ok": False, "reason": "no baseline was taken"}

    touched = []
    for i in items(db, p.id):
        if i.status == "applied":
            done = i.applied or {}
            if i.outcome in EDGE_OUTCOMES:
                touched += [done["from"]] if done.get("from") else []
            else:
                touched += [u for u in (i.legacy_uid, done.get("equipment"), done.get("installation")) if u]
    before_state = _state(db, touched)
    savepoint = db.begin_nested()
    try:
        for w in workspaces:
            engine.rebuild(db, w)
        rebuilt = _state(db, touched)
    finally:
        savepoint.rollback()
    differences = []
    for uid, was in before_state.items():
        now_ = rebuilt.get(uid)
        if was != now_:
            fields = sorted(k for k in (was or {}) if (now_ or {}).get(k) != (was or {}).get(k))
            differences.append({"uid": uid, "fields": fields})
    mig6 = {"ok": not differences, "records": len(before_state), "differences": differences[:50]}
    inv = invariants.report(db, workspaces)
    mig4 = {"ok": inv["ok"], "failing": inv["failing"],
            "examples": {c: inv["invariants"][c]["examples"][:3] for c in inv["failing"]}}
    golden_before = (p.invariants or {}).get("golden_before")
    if golden_before and golden_before["incidents"]:
        mig7 = golden.compare(golden_before, golden.run(db, p.workspace_id))
    else:
        mig7 = {"ok": None, "reason": "no golden incidents were recorded for this workspace before the plan was "
                                      "applied; finalizing needs a waiver"}
    deep = {"at": now().isoformat(), "ok": mig4["ok"] and mig5["ok"] and mig6["ok"] and mig7["ok"] is not False,
            "I-MIG-4": mig4, "I-MIG-5": mig5, "I-MIG-6": mig6, "I-MIG-7": mig7}
    p.invariants = {**(p.invariants or {}), "deep_verification": deep}
    engine._record_decision(db, "migration_verify", actor, p.workspace_id, target={"plan": p.id},
                            value={"ok": deep["ok"], "I-MIG-4": mig4["ok"], "I-MIG-5": mig5["ok"],
                                   "I-MIG-6": mig6["ok"], "I-MIG-7": mig7["ok"]})
    db.flush()
    return p


# --------------------------------------------------------------------------- rollback and finalize

def _retire_by_decision(db: Session, workspace_id: str, actor: str, uid: str, reason: str) -> None:
    engine.apply_decisions(db, workspace_id, actor, [service.confirm_value(
        uid, "exists", "absent", replaces=service._active(db, uid, "exists"), reason=reason)])


@ledger_writer
def rollback(db: Session, plan_id: str, actor: str, item_ids: Optional[list[int]] = None) -> LegacyMigrationPlan:
    p = _plan(db, plan_id)
    _assert_open(db, p)
    chosen = [i for i in items(db, p.id) if i.status == "applied" and (item_ids is None or i.id in item_ids)]
    for item in sorted(chosen, key=lambda i: (-ORDER[i.outcome], -i.id)):
        if item.outcome in EDGE_OUTCOMES:
            _rollback_edge(db, p, item, actor)
            continue
        done = item.applied or {}
        r = db.get(Asset, item.legacy_uid)
        eq = done.get("equipment") if done.get("equipment_created") else None
        if eq:
            gained = dependents(db, [eq])
            expected_labels, expected_atts = len(done["moved_labels"]), len(done["moved_attachments"])
            if gained["tickets"] or gained["documents"] or gained["comments"] \
                    or gained["labels"] > expected_labels or gained["attachments"] > expected_atts:
                raise MigrationError(f"{item.legacy_key}: the Equipment it created has gained its own dependents; "
                                     "correct it with decisions instead")
        reason = f"rollback of {p.id}"
        if done.get("installation"):
            service.reject_installation(db, r.workspace_id, actor, done["installation"], reason)
        for uid in done.get("moved_labels", []):
            label = db.get(AssetLabel, uid)
            if label is not None:
                label.asset_uid = r.uid
        for uid in done.get("moved_attachments", []):
            att = db.get(Attachment, uid)
            if att is not None:
                att.asset_uid = r.uid
        if eq:
            _retire_by_decision(db, db.get(Asset, eq).workspace_id, actor, eq, reason)
        if done.get("former_key_label"):
            label = db.get(AssetLabel, done["former_key_label"])
            if label is not None:
                db.delete(label)
        for rel in done.get("removed_relations", []):
            db.add(Relation(workspace_id=rel["workspace_id"], from_asset_uid=rel["from"], to_asset_uid=rel["to"],
                            relation_type=rel["type"], derivation=rel["derivation"]))
        before = item.pre_image["asset"]
        r.key, r.name, r.type, r.schema_uid = before["key"], before["name"], before["type"], before["schema_uid"]
        r.record_status, r.attributes = before["record_status"], before["attributes"]
        # migration_map is append-only: its rows stay as history, pointing at retired records.
        item.status, item.reason, item.updated_at = "rolled_back", reason, now()
        db.flush()
    if not any(i.status == "applied" for i in items(db, p.id)):
        p.status = "rolled_back"
    engine._record_decision(db, "migration_rollback", actor, p.workspace_id, target={"plan": p.id},
                            value={"items": [i.id for i in chosen]})
    db.flush()
    return p


def finalize(db: Session, plan_id: str, actor: str, golden_waiver: Optional[str] = None) -> LegacyMigrationPlan:
    p = _plan(db, plan_id)
    if p.finalized_at is not None:
        raise MigrationError("already finalized")
    if p.status != "verified":
        raise MigrationError("only a verified plan is finalized; resolve the open items or roll back")
    deep = (p.invariants or {}).get("deep_verification")
    if not deep or datetime.fromisoformat(deep["at"]) < p.applied_at:
        raise MigrationError("run the deep verification (I-MIG-4, I-MIG-5, I-MIG-6) after the last apply")
    if not deep["ok"]:
        raise MigrationError("the deep verification failed: " + ", ".join(
            k for k in ("I-MIG-4", "I-MIG-5", "I-MIG-6", "I-MIG-7") if deep.get(k, {"ok": False})["ok"] is False))
    if deep.get("I-MIG-7", {}).get("ok") is None and not (golden_waiver or "").strip():
        raise MigrationError("I-MIG-7 was not checked (no golden incidents); finalizing needs a waiver with a reason")
    p.finalized_at, p.status = now(), "finalized"
    engine._record_decision(db, "migration_finalize", actor, p.workspace_id, target={"plan": p.id},
                            value={"report_hash": p.report_hash, "golden_waiver": golden_waiver})
    db.flush()
    return p


def view(db: Session, p: LegacyMigrationPlan, rows: bool = True) -> dict:
    out = {"id": p.id, "workspace_id": p.workspace_id, "inventory_workspace_id": p.inventory_workspace_id,
           "status": p.status, "created_by": p.created_by, "created_at": p.created_at, "applied_at": p.applied_at,
           "finalized_at": p.finalized_at, "report_hash": p.report_hash, "invariants": p.invariants}
    rep = report(db, p)
    out["outcomes"] = rep["outcomes"]
    statuses: dict = {}
    for r in rep["rows"]:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    out["statuses"] = statuses
    if rows:
        out["rows"] = rep["rows"]
    return out


def gate(db: Session, workspace_id: str) -> dict:
    """§17.4 criterion 4 for a workspace: no item is M-BLOCK, and every
    M-MIXED item is resolved or accepted as Provisional (its plan applied)."""
    blocked, mixed_open, planned_uids = [], [], set()
    for p in db.scalars(select(LegacyMigrationPlan).where(LegacyMigrationPlan.workspace_id == workspace_id,
                                                          LegacyMigrationPlan.status != "rolled_back")):
        for i in items(db, p.id):
            if i.status == "rolled_back":
                continue
            planned_uids.add(i.legacy_uid)
            if i.outcome == "M-BLOCK":
                blocked.append(i.legacy_key)
            elif i.outcome == "M-MIXED" and i.status != "applied":
                mixed_open.append(i.legacy_key)
    unplanned = len([r for r in _scope(db, workspace_id) if r.uid not in planned_uids])
    return {"ok": not blocked and not mixed_open and unplanned == 0, "blocked": blocked, "mixed_open": mixed_open,
            "unplanned": unplanned}
