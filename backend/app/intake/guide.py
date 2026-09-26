"""Guiding a person to a correct entry, with no model involved (§23.4, §23.11).

Each check says what is wrong or worth knowing, on which field, and how to
fix it; `next` is the one question worth asking now. The checks are the
rules the save would enforce anyway (required fields, identifier
uniqueness, the incident time) and the ones it cannot enforce but a
careful colleague would point out (a channel name typed as equipment, a
ticket that has probably been reported already).

Only what the person may read is ever named. A duplicate they cannot see
is reported as taken, never shown (I-ACL-1).
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.intake import secrets
from app.models.asset import Asset
from app.models.schema import Schema

ERROR, WARNING, INFO, OK = "error", "warning", "info", "ok"
# What a control channel or PV looks like: LNF device codes (GUNSIP01,
# QUATB002, AC1HCR01) and colon-separated PV names (SPARC:VAC:GUNSIP01).
CHANNEL = re.compile(r"^(?=.*\d)[A-Z][A-Z0-9]{3,11}\d{2,3}$")
PV = re.compile(r"^[A-Z0-9_-]+(:[A-Z0-9_-]+){2,}$", re.I)
EQUIPMENT_ROOT, FUNCTIONAL_ROOT, CONTROL_ROOT = "Asset", "Functional Element", "Control Item"


def _check(level: str, message: str, field: Optional[str] = None, *, fix: Optional[dict] = None,
           links: Optional[list] = None, id: Optional[str] = None) -> dict:
    out = {"id": id or (field or "general"), "level": level, "message": message, "field": field}
    if fix:
        out["fix"] = fix
    if links:
        out["links"] = links
    return out


def _result(kind: str, checks: list[dict], steps: list[dict], questions: dict) -> dict:
    blocking = [c for c in checks if c["level"] == ERROR]
    nxt = None
    for c in blocking + [c for c in checks if c["level"] == WARNING]:
        if c.get("field") in questions:
            nxt = {"field": c["field"], "question": questions[c["field"]]}
            break
    return {"kind": kind, "ready": not blocking, "checks": checks, "steps": steps, "next": nxt}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z0-9]{4,}", text or "")][:6]


def _similarity(a: str, b: str) -> float:
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    ta, tb = set(re.findall(r"\w+", a)), set(re.findall(r"\w+", b))
    jaccard = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(SequenceMatcher(None, a, b).ratio(), jaccard)


def _similar(rows, text: str, attr: str, threshold: float = 0.6, limit: int = 5) -> list:
    scored = [(r, _similarity(text, getattr(r, attr))) for r in rows]
    return [r for r, s in sorted(scored, key=lambda x: -x[1]) if s >= threshold][:limit]


# --------------------------------------------------------------------------- assets

def lineage(db: Session, schema: Schema) -> list[str]:
    names, seen, cur = [], set(), schema
    while cur is not None and cur.uid not in seen:
        seen.add(cur.uid)
        names.append(cur.name)
        cur = db.get(Schema, cur.parent_schema_uid) if cur.parent_schema_uid else None
    return names


def nature(db: Session, schema: Schema) -> str:
    """equipment | position | control | other: what a record of this type is."""
    names = lineage(db, schema)
    if EQUIPMENT_ROOT in names:
        return "equipment"
    if FUNCTIONAL_ROOT in names:
        return "position"
    if CONTROL_ROOT in names:
        return "control"
    return "other"


def _usable(schema: Optional[Schema], workspace_id: str) -> bool:
    return schema is not None and schema.applies_to == "objects" and (
        schema.workspace_id == workspace_id or schema.is_global)


def _concrete_kinds(db: Session, schema: Schema, workspace_id: str, limit: int = 8) -> list[dict]:
    rows = [s for s in db.scalars(select(Schema).where(
        Schema.applies_to == "objects", Schema.is_concrete.is_(True),
        or_(Schema.workspace_id == workspace_id, Schema.is_global.is_(True))))]
    out = [s for s in rows if schema.name in lineage(db, s)[1:]]
    return [{"uid": s.uid, "name": s.name} for s in sorted(out, key=lambda s: s.name)[:limit]]


def _link(a: Asset) -> dict:
    return {"uid": a.uid, "key": a.key, "name": a.name, "path": f"/assets/{a.uid}"}


def guide_asset(db: Session, workspace_id: str, draft: dict, grants=None) -> dict:
    from app.ledger.cutover import authoritative
    from app.ledger.identity import _holders, strong_identifiers
    from app.services.attribute_validation import check_attributes, effective_attributes
    from app.services.visibility import asset_visible_in, visible_assets_clause
    checks: list[dict] = []
    questions = {
        "schema_uid": "What is it? For example an ion pump, a power supply, or a place in the machine.",
        "name": "What do people call it?",
        "key": "What identifier does it carry? The label on it, or a new unique key.",
        "attributes.serial": "What is its serial number? It is usually on the nameplate.",
        "attributes.manufacturer": "Who made it?",
        "attributes.equipment_class": "What kind of equipment is it, in a word or two?",
    }
    name, key = (draft.get("name") or "").strip(), (draft.get("key") or "").strip()
    own = draft.get("uid")                       # editing: the record is not its own duplicate
    attrs = dict(draft.get("attributes") or {})
    schema = db.get(Schema, draft.get("schema_uid")) if draft.get("schema_uid") else None
    kind = None
    steps = {"type": False, "identity": False, "identifiers": None, "details": False, "duplicates": True}

    # 1. What it is.
    if schema is None:
        checks.append(_check(ERROR, "Choose what this is.", "schema_uid"))
    elif not _usable(schema, workspace_id):
        checks.append(_check(ERROR, "This type cannot be used in this workspace.", "schema_uid"))
        schema = None
    elif not schema.is_concrete:
        kinds = _concrete_kinds(db, schema, workspace_id)
        checks.append(_check(ERROR, f"{schema.name} is a category. Choose one of its kinds"
                             + (f": {', '.join(k['name'] for k in kinds)}." if kinds else "."),
                             "schema_uid", fix={"field": "schema_uid", "options": kinds} if kinds else None))
    else:
        steps["type"] = True
        kind = nature(db, schema)
        explain = {
            "equipment": f"{schema.name}: a physical unit, the box with a serial number. Where it is "
                         "installed is recorded separately, as an Installation at a Position, so the "
                         "unit keeps its history when it moves.",
            "position": f"{schema.name}: a place or function in the machine. It stays when the "
                        "equipment filling it is swapped.",
            "control": f"{schema.name}: a control-system record, not a physical unit.",
        }.get(kind)
        if explain:
            checks.append(_check(INFO, explain, "schema_uid", id="nature"))

    # 2. Name and key.
    if not name:
        checks.append(_check(ERROR, "Give it a name.", "name"))
    if not key:
        checks.append(_check(ERROR, "Give it a key: a unique identifier, such as the label on it.", "key"))
    else:
        taken = db.scalar(select(Asset).where(Asset.key == key))
        if taken is not None and taken.uid != own:
            if asset_visible_in(taken, workspace_id, grants):
                checks.append(_check(ERROR, f"The key {key} already belongs to {taken.name}. Is this the same "
                                     "thing? Open it instead of creating a second record.", "key",
                                     links=[_link(taken)]))
            else:
                checks.append(_check(ERROR, f"The key {key} is already taken.", "key"))
    if name and key and not any(c["field"] in ("name", "key") for c in checks):
        steps["identity"] = True

    # A channel or PV typed as a physical unit (§23.5).
    if kind == "equipment":
        for label, value in (("name", name), ("key", key)):
            if value and (CHANNEL.match(value) or PV.match(value)):
                channel = db.scalar(select(Asset).where(Asset.key == value, Asset.type.in_(
                    ("Control Device", "IOC")), visible_assets_clause(workspace_id, grants)))
                checks.append(_check(
                    WARNING, f"“{value}” looks like a control-channel name. A channel names a place in the "
                    "machine (a Position), not the unit installed there. Give the unit its own name or "
                    "label, and record where it is installed separately.", label, id=f"channel-{label}",
                    links=[_link(channel)] if channel else None))
                break

    # 3. Other Equipment needs a class (I-CAT-1).
    if schema is not None and schema.name == "Other Equipment":
        from app.services import equipment_classes as ec
        cls = attrs.get("equipment_class")
        if not cls or cls == ec.UNCLASSIFIED:
            options = [c.name for c in ec.vocabulary(db) if c.status == "active" and c.name != ec.UNCLASSIFIED]
            checks.append(_check(WARNING, "Say what kind of equipment it is. Unclassified equipment is hard "
                                 "to find and counts against the catalogue.", "attributes.equipment_class",
                                 fix={"field": "attributes.equipment_class", "options": options[:20]} if options else None))

    # 4. Required and invalid attributes.
    if schema is not None and schema.is_concrete:
        required_missing = []
        for attr in effective_attributes(db, schema):
            k = attr.get("key") or attr.get("name")
            if attr.get("required") and attrs.get(k) in (None, "", []):
                required_missing.append(k)
                questions.setdefault(f"attributes.{k}", f"What is its {attr.get('name') or k}?")
                checks.append(_check(ERROR, f"{attr.get('name') or k} is required.", f"attributes.{k}"))
        for msg in check_attributes(db, schema, {k: v for k, v in attrs.items() if v not in (None, "")},
                                    workspace_id, Asset, exclude_uid=own, skip_unique=False):
            if not msg.endswith("is required"):
                checks.append(_check(ERROR, msg, None, id=f"attr-{len(checks)}"))
        steps["details"] = not required_missing

    # 5. Identifiers: normalized, and not held by another record (I-ID-1, D4).
    if kind == "equipment":
        steps["identifiers"] = False
        mac = attrs.get("mac")
        if isinstance(mac, str) and mac.strip() and mac != mac.strip().lower().replace("-", ":"):
            checks.append(_check(INFO, "MAC addresses are stored lower case with colons.", "attributes.mac",
                                 fix={"field": "attributes.mac", "value": mac.strip().lower().replace("-", ":")}))
        for field in ("serial", "inventory_number"):
            v = attrs.get(field)
            if isinstance(v, str) and v != v.strip():
                checks.append(_check(INFO, "Leading or trailing spaces removed.", f"attributes.{field}",
                                     fix={"field": f"attributes.{field}", "value": v.strip()}))
        ids = strong_identifiers(attrs)
        if attrs.get("serial") and not attrs.get("manufacturer"):
            checks.append(_check(WARNING, "A serial number identifies a unit only together with its "
                                 "manufacturer. Add the manufacturer.", "attributes.manufacturer"))
        if not ids:
            checks.append(_check(WARNING, "No serial number or inventory number yet. Without one, this unit "
                                 "cannot be told apart from others of the same model. Add it if the unit has "
                                 "a label.", "attributes.serial", id="identifiers"))
        strict = authoritative(db, workspace_id, "objects")
        for ident, value in ids:
            holders = _holders(db, ident, value, exclude=own)
            if not holders:
                continue
            seen = [h for h in holders if asset_visible_in(h, workspace_id, grants)]
            label = ident.replace("_", " ")
            shown = value.split("|")[-1]
            if seen:
                checks.append(_check(ERROR if strict else WARNING,
                                     f"{seen[0].name} already has {label} {shown}. If it is the same unit, open "
                                     "it; a unit has one record." + ("" if strict else " Saving anyway opens a "
                                     "duplicate review."), f"attributes.{ident}", links=[_link(h) for h in seen[:3]],
                                     id=f"ident-{ident}"))
            else:
                checks.append(_check(ERROR if strict else WARNING, f"The {label} {shown} is already recorded "
                                     "on a record you cannot see. Ask its owner before creating another.",
                                     f"attributes.{ident}", id=f"ident-{ident}"))
        steps["identifiers"] = bool(ids) and not any(c["id"].startswith("ident-") for c in checks)

    # 6. Probably already recorded.
    if name and schema is not None:
        rows = list(db.scalars(select(Asset).where(
            visible_assets_clause(workspace_id, grants), Asset.type == schema.name,
            Asset.record_status.notin_(("Retired", "Merged")),
            or_(*[Asset.name.ilike(f"%{w}%") for w in _words(name)] or [Asset.name.ilike(name)])).limit(200)))
        rows = [r for r in rows if r.key != key and r.uid != own]
        similar = _similar(rows, name, "name", threshold=0.75)
        if similar:
            steps["duplicates"] = False
            checks.append(_check(WARNING, "Similar records already exist. Check it is not one of these.",
                                 "name", links=[_link(a) for a in similar], id="similar"))

    order = [("type", "What it is"), ("identity", "Name and key"), ("identifiers", "Serial or inventory number"),
             ("details", "Required details"), ("duplicates", "Not already recorded")]
    step_list = [{"id": i, "label": label, "done": steps[i]} for i, label in order if steps[i] is not None]
    return _result("asset", checks, step_list, questions)


# --------------------------------------------------------------------------- tickets

def guide_ticket(db: Session, workspace_id: str, draft: dict, grants=None) -> dict:
    from app.ledger.tickets import OccurrenceRequired, is_incident_type, validate_occurrence
    from app.models.issue import Issue
    from app.services.attribute_validation import check_attributes
    from app.services.visibility import asset_visible_in, visible_issues_clause
    checks: list[dict] = []
    questions = {
        "title": "In one line, what is wrong?",
        "description": "What did you see, when, and what have you already tried?",
        "asset_uid": "Which equipment or place is affected?",
        "attributes.occurred_from": "When did it happen? The day is enough if you do not know the time.",
        "schema_uid": "What kind of ticket is it: a fault, a request, a task?",
    }
    title, description = (draft.get("title") or "").strip(), (draft.get("description") or "").strip()
    attrs = dict(draft.get("attributes") or {})
    schema = db.get(Schema, draft.get("schema_uid")) if draft.get("schema_uid") else None
    steps = {"what": bool(title), "detail": len(description) >= 20, "subject": bool(draft.get("asset_uid")),
             "when": True, "duplicates": True}

    if not title:
        checks.append(_check(ERROR, "Say in one line what is wrong.", "title"))
    if len(description) < 20:
        checks.append(_check(WARNING, "Describe what you saw, when it started, and what you already tried. "
                             "It is what the person picking this up needs first.", "description"))
    kinds = db.scalar(select(Schema.uid).where(Schema.applies_to == "tickets", or_(
        Schema.workspace_id == workspace_id, Schema.is_global.is_(True))).limit(1))
    if schema is None and kinds:
        checks.append(_check(WARNING, "Choose the kind of ticket, so it follows the right workflow.",
                             "schema_uid"))
    if schema is not None and is_incident_type(db, schema.uid):
        steps["when"] = False
        try:
            validate_occurrence(db, schema.uid, attrs)
            steps["when"] = True
        except OccurrenceRequired as exc:
            checks.append(_check(ERROR, f"An operational incident says when it happened: {exc}",
                                 "attributes.occurred_from"))
    if schema is not None:
        for msg in check_attributes(db, schema, {k: v for k, v in attrs.items() if v not in (None, "")},
                                    workspace_id, Issue, skip_unique=True):
            if not msg.endswith("is required"):
                checks.append(_check(ERROR, msg, None, id=f"attr-{len(checks)}"))

    if not draft.get("asset_uid"):
        from app.services.text_links import objects_mentioned
        found = objects_mentioned(db, workspace_id, title, description)
        links = []
        for f in found[:5]:
            a = db.get(Asset, f["uid"])
            if a is not None and asset_visible_in(a, workspace_id, grants):
                links.append({**_link(a), "matched_on": f["matched_on"]})
        checks.append(_check(WARNING, "Say which equipment or place is affected, so the ticket appears on its "
                             "record and in its history." + (" The report mentions:" if links else ""),
                             "asset_uid", links=links or None,
                             fix={"field": "asset_uid", "options": links} if links else None))
    else:
        a = db.get(Asset, draft["asset_uid"])
        if a is None or not asset_visible_in(a, workspace_id, grants):
            checks.append(_check(ERROR, "The affected record does not exist here.", "asset_uid"))
            steps["subject"] = False

    if title:
        rows = list(db.scalars(select(Issue).where(
            Issue.workspace_id == workspace_id, visible_issues_clause(grants), Issue.deleted_at.is_(None),
            Issue.closed_at.is_(None),
            or_(*[Issue.title.ilike(f"%{w}%") for w in _words(title)] or [Issue.title.ilike(title)])).limit(200)))
        if draft.get("asset_uid"):
            same = [r for r in rows if r.asset_uid == draft["asset_uid"]]
            rows = same + [r for r in rows if r not in same]
        rows = [r for r in rows if r.uid != draft.get("uid")]
        similar = _similar(rows, title, "title", threshold=0.6)
        if similar:
            steps["duplicates"] = False
            checks.append(_check(WARNING, "Open tickets look similar. If one is the same problem, add to it "
                                 "instead of opening another.", "title", id="similar",
                                 links=[{"uid": i.uid, "key": i.uid[:8], "name": i.title,
                                         "path": f"/tickets/{i.uid}"} for i in similar]))

    found = secrets.scan(f"{title}\n{description}")
    if found:
        checks.append(_check(ERROR, "The text contains what looks like a password or key. Remove it: "
                             "secrets are never stored in tickets.", "description", id="secret"))

    order = [("what", "What is wrong"), ("detail", "What you saw"), ("subject", "What is affected"),
             ("when", "When it happened"), ("duplicates", "Not already reported")]
    return _result("ticket", checks, [{"id": i, "label": l, "done": steps[i]} for i, l in order], questions)


# --------------------------------------------------------------------------- documents

def guide_document(db: Session, workspace_id: str, draft: dict, grants=None) -> dict:
    from app.models.document import Document
    from app.services.document_codes import next_code
    checks: list[dict] = []
    questions = {
        "title": "What is the document called?",
        "document_type_uid": "What kind of document is it: a procedure, a drawing, a report?",
        "body_markdown": "What should it say? Describe it and a draft can be written for you.",
    }
    title = (draft.get("title") or "").strip()
    body = draft.get("body_markdown") or ""
    type_uid, code = draft.get("document_type_uid"), (draft.get("code") or "").strip()
    steps = {"title": bool(title), "type": bool(type_uid), "content": bool(body.strip()), "duplicates": True,
             "safe": True}

    if not title:
        checks.append(_check(ERROR, "Give the document a title.", "title"))
    if not type_uid:
        checks.append(_check(WARNING, "Choose the kind of document. It sets its code, its approval route and "
                             "how long it is kept.", "document_type_uid"))
    elif db.get(Schema, type_uid) is None:
        checks.append(_check(ERROR, "That document type does not exist.", "document_type_uid"))
    if code:
        if db.scalar(select(Document.uid).where(Document.code == code, Document.uid != (draft.get("uid") or ""))):
            checks.append(_check(ERROR, f"The code {code} is already used. Leave it empty to get the next "
                                 "free one.", "code"))
    else:
        checks.append(_check(INFO, f"It will be numbered {next_code(db, workspace_id, type_uid)}.", "code",
                             id="code-preview"))
    if not body.strip():
        checks.append(_check(INFO, "The document has no content yet.", "body_markdown"))

    if title:
        rows = list(db.scalars(select(Document).where(
            Document.workspace_id == workspace_id, Document.confidentiality != "riservato",
            or_(*[Document.title.ilike(f"%{w}%") for w in _words(title)] or [Document.title.ilike(title)])
        ).limit(200)))
        rows = [r for r in rows if r.uid != draft.get("uid")]
        similar = _similar(rows, title, "title", threshold=0.7)
        if similar:
            steps["duplicates"] = False
            checks.append(_check(WARNING, "Documents with similar titles exist. If one of them is this "
                                 "document, add a revision to it instead.", "title", id="similar",
                                 links=[{"uid": d.uid, "key": d.code, "name": d.title,
                                         "path": f"/documents/{d.uid}"} for d in similar]))

    if secrets.scan(f"{title}\n{body}"):
        steps["safe"] = False
        checks.append(_check(ERROR, "The document contains what looks like a password or key. Remove it: "
                             "secrets are never stored in documents.", "body_markdown", id="secret"))
    if body.strip():
        from app.services.text_links import objects_mentioned
        from app.services.visibility import asset_visible_in
        links = []
        for f in objects_mentioned(db, workspace_id, title, body)[:8]:
            a = db.get(Asset, f["uid"])
            if a is not None and asset_visible_in(a, workspace_id, grants):
                links.append(_link(a))
        if links:
            checks.append(_check(INFO, "It mentions these records. Link the ones it describes.", None,
                                 id="mentions", links=links))

    order = [("title", "Title"), ("type", "Kind of document"), ("content", "Content"),
             ("duplicates", "Not already recorded"), ("safe", "No secrets")]
    return _result("document", checks, [{"id": i, "label": l, "done": steps[i]} for i, l in order], questions)


GUIDES = {"asset": guide_asset, "ticket": guide_ticket, "document": guide_document}
