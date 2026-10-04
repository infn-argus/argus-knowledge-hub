"""Changes Ask ARGUS proposes, and their application once a person confirms them.

Ask's lookups only retrieve, and that stays so: the model cannot write. What it can do, when somebody asks it
to ("create the six screens and link their cameras"), is propose — create a record, change one, relate two
or unrelate them. A proposal is checked as it is made (the type exists, the record is there, the relation is
one the rules allow between those types), kept in the conversation, and shown under the answer. Nothing
changes until the person applies it, and then it goes through the same code as the forms: their
permissions, the same validation and key allocation, and the ledger, in their name.

A record proposed in the same conversation is referred to as `new:N` before it exists, so "a station composed
of this camera" can be proposed in one go with the station itself.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ask_conversation import AskAction
from app.models.asset import Asset, Relation
from app.models.schema import Schema

# What each kind of change needs, as the forms would.
PERMISSION = {"create": "create", "update": "modify", "relate": "create", "unrelate": "delete"}
SKIPPED_ATTRIBUTES = ("argus_source", "argus_facility")

SYSTEM = (
    "\n\nYou may also propose changes, but only when the person asks for one: propose_create_record, "
    "propose_update_record and propose_relation. A proposal changes nothing: it is shown to the person, who "
    "applies or discards it. Never say a change was made; say it is proposed and waits for their confirmation. "
    "Look the records up first and use their keys. A record you propose to create is referred to as new:N "
    "(N is in the proposal's reply) until it exists, so you can relate it in the same answer. 'A composed of "
    "B' means B is a part of A; 'X part of Y' means X belongs to Y. If a proposal is refused, correct it from "
    "the reason given rather than repeating it."
)


def _relation_names() -> list[str]:
    """The relations the hub knows the meaning of (services/causal_model.py), less the deprecated ones."""
    from app.ledger import registry
    from app.services.causal_model import SEMANTICS
    return sorted((set(SEMANTICS) | set(registry.ENDPOINTS)) - registry.DEPRECATED)


def _relation_guide() -> str:
    from app.services.causal_model import SEMANTICS
    return "; ".join(f"{n}: {SEMANTICS[n].note}" for n in _relation_names() if n in SEMANTICS and SEMANTICS[n].note)


def tool_specs() -> list[dict]:
    record = "A record's key or uid, or new:N for one proposed earlier in this conversation."
    return [
        {"type": "function", "function": {
            "name": "propose_create_record",
            "description": "Propose creating an object (equipment, a screen station, a location…). Changes "
                           "nothing until the person confirms. Call list_types first to pick the type.",
            "parameters": {"type": "object", "properties": {
                "type": {"type": "string", "description": "The object type's name, as list_types gives it."},
                "name": {"type": "string"},
                "key": {"type": "string", "description": "Optional; left out, the workspace's pattern makes one."},
                "attributes": {"type": "object", "description": "Attribute key → value, keys of that type only."},
                "reason": {"type": "string", "description": "Why, from the records looked at."},
            }, "required": ["type", "name"]}}},
        {"type": "function", "function": {
            "name": "propose_update_record",
            "description": "Propose changing an existing object's name or attributes (only those given; null "
                           "clears one). Changes nothing until the person confirms.",
            "parameters": {"type": "object", "properties": {
                "record": {"type": "string", "description": record},
                "name": {"type": "string"},
                "attributes": {"type": "object"},
                "reason": {"type": "string"},
            }, "required": ["record"]}}},
        {"type": "function", "function": {
            "name": "propose_relation",
            "description": "Propose relating two objects (from —relation→ to), or with remove=true removing that "
                           "relation. Changes nothing until the person confirms. What each relation means, "
                           "from → to: " + _relation_guide(),
            "parameters": {"type": "object", "properties": {
                "from": {"type": "string", "description": record},
                "relation_type": {"type": "string", "enum": _relation_names()},
                "to": {"type": "string", "description": record},
                "remove": {"type": "boolean"},
                "reason": {"type": "string"},
            }, "required": ["from", "relation_type", "to"]}}},
    ]


TOOL_NAMES = {"propose_create_record", "propose_update_record", "propose_relation"}


class Refused(ValueError):
    """A proposal that cannot be made as it stands; the reason goes back to the model."""


def _types(db: Session, workspace_id: str) -> dict[str, Schema]:
    from app.intake.assist import _visible_types
    return {s.name.lower(): s for s in _visible_types(db, workspace_id, "objects")}


def _attribute_keys(db: Session, schema: Schema) -> set[str]:
    from app.services.attribute_validation import effective_attributes
    return {a.get("key") or a.get("name") for a in effective_attributes(db, schema)} - {None}


def _check_attributes(db: Session, schema: Schema, attributes) -> dict:
    if attributes in (None, {}):
        return {}
    if not isinstance(attributes, dict):
        raise Refused("attributes must be an object of attribute key → value")
    known = _attribute_keys(db, schema)
    unknown = sorted(k for k in attributes if k not in known)
    if unknown:
        usable = sorted(k for k in known if not k.startswith(SKIPPED_ATTRIBUTES))
        raise Refused(f"{schema.name} has no attribute {', '.join(unknown)}; its attributes are: {', '.join(usable)}")
    return attributes


class Proposer:
    """The write tools of one chat turn: each call checks and keeps one proposal."""

    def __init__(self, db: Session, workspace_id: str, conversation_id: str, turn_seq: int):
        self.db, self.workspace_id = db, workspace_id
        self.conversation_id, self.turn_seq = conversation_id, turn_seq

    # --- resolving what a proposal names ---------------------------------------------------------------

    def _new(self, ref: str) -> AskAction:
        try:
            number = int(ref.split(":", 1)[1])
        except (IndexError, ValueError):
            raise Refused(f"{ref} is not a proposed record (new:N)")
        action = self.db.scalar(select(AskAction).where(
            AskAction.conversation_id == self.conversation_id, AskAction.number == number,
            AskAction.kind == "create"))
        if action is None or action.status in ("discarded", "failed"):
            raise Refused(f"no record proposed in this conversation is new:{number}")
        return action

    def _existing(self, ref: str) -> Optional[Asset]:
        from app.services.visibility import asset_visible_in
        ref = (ref or "").strip()
        asset = self.db.get(Asset, ref) or self.db.scalar(select(Asset).where(Asset.key == ref))
        if asset is None or asset.deleted_at is not None or not asset_visible_in(asset, self.workspace_id):
            return None
        return asset

    def _endpoint(self, ref: str) -> tuple[Optional[Asset], Optional[AskAction], str]:
        """(asset, proposed creation, label) for a from/to."""
        ref = str(ref or "").strip()
        if ref.lower().startswith("new:"):
            action = self._new(ref)
            if action.status == "applied":
                asset = self.db.get(Asset, (action.result or {}).get("uid"))
                if asset is not None:
                    return asset, None, asset.key
            return None, action, f"new:{action.number} ({action.payload['name']})"
        asset = self._existing(ref)
        if asset is None:
            raise Refused(f"no record {ref!r} here: look it up and use its key")
        return asset, None, asset.key

    # --- the tools -----------------------------------------------------------------------------------------

    def __call__(self, name: str, arguments: dict) -> dict:
        handler = {"propose_create_record": self._create, "propose_update_record": self._update,
                   "propose_relation": self._relation}[name]
        kind, payload, summary = handler(arguments or {})
        number = (self.db.scalar(select(AskAction.number).where(AskAction.conversation_id == self.conversation_id)
                                 .order_by(AskAction.number.desc()).limit(1)) or 0) + 1
        reason = str(arguments.get("reason") or "").strip()[:500]
        action = AskAction(id=str(uuid.uuid4()), conversation_id=self.conversation_id, turn_seq=self.turn_seq,
                           number=number, kind=kind, payload={**payload, **({"reason": reason} if reason else {})},
                           summary=summary, status="proposed")
        self.db.add(action)
        # Kept now: the chat's own save rolls back whatever is pending before it writes the answer.
        self.db.commit()
        out = {"proposed": True, "action": f"A{number}", "summary": summary,
               "status": "waiting for the person to confirm: nothing has been changed yet"}
        if kind == "create":
            out["ref"] = f"new:{number}"
        return {**out, "_action": view(action)}

    def _create(self, a: dict) -> tuple[str, dict, str]:
        types = _types(self.db, self.workspace_id)
        schema = types.get(str(a.get("type") or "").strip().lower())
        if schema is None:
            raise Refused(f"there is no object type {a.get('type')!r} here: call list_types and use one of its names")
        name = str(a.get("name") or "").strip()
        if not name:
            raise Refused("a record needs a name")
        key = str(a.get("key") or "").strip() or None
        if key and self.db.scalar(select(Asset.uid).where(Asset.key == key)) is not None:
            raise Refused(f"the key {key} is already taken")
        attributes = _check_attributes(self.db, schema, a.get("attributes"))
        payload = {"schema_uid": schema.uid, "type": schema.name, "name": name, "key": key, "attributes": attributes}
        details = "".join(f", {k} = {v}" for k, v in attributes.items())
        return "create", payload, f"Create {schema.name} “{name}”" + (f" ({key})" if key else "") + details

    def _update(self, a: dict) -> tuple[str, dict, str]:
        ref = str(a.get("record") or "")
        if ref.lower().startswith("new:"):
            raise Refused("a record still to be created is changed by proposing it again with the right values")
        asset = self._existing(ref)
        if asset is None:
            raise Refused(f"no record {ref!r} here: look it up and use its key")
        if asset.workspace_id != self.workspace_id:
            raise Refused(f"{asset.key} belongs to workspace {asset.workspace_id}; it can only be changed there")
        schema = self.db.get(Schema, asset.schema_uid) if asset.schema_uid else None
        attributes = _check_attributes(self.db, schema, a.get("attributes")) if schema else (a.get("attributes") or {})
        current = asset.attributes or {}
        attributes = {k: v for k, v in attributes.items() if current.get(k) != v}
        name = str(a.get("name") or "").strip() or None
        if name == asset.name:
            name = None
        if not attributes and not name:
            raise Refused(f"that changes nothing on {asset.key}")
        parts = ([f"name → {name}"] if name else []) + [
            f"{k} → {'(cleared)' if v is None else v}" for k, v in attributes.items()]
        return "update", {"uid": asset.uid, "key": asset.key, "name": name, "attributes": attributes}, \
            f"Update {asset.key}: " + ", ".join(parts)

    def _relation(self, a: dict) -> tuple[str, dict, str]:
        from app.ledger import registry
        relation = str(a.get("relation_type") or "").strip().lower()
        if relation not in _relation_names():
            raise Refused(f"{relation!r} is not a relation here; use one of: {', '.join(_relation_names())}")
        source, source_new, source_label = self._endpoint(a.get("from"))
        target, target_new, target_label = self._endpoint(a.get("to"))
        if source is not None and source.workspace_id != self.workspace_id:
            raise Refused(f"{source.key} belongs to workspace {source.workspace_id}: relate it from there")
        if source is not None and target is not None and source.uid == target.uid:
            raise Refused("a record cannot be related to itself")
        remove = bool(a.get("remove"))
        if remove:
            if source is None or target is None:
                raise Refused("only a relation that exists can be removed")
            exists = self.db.scalar(select(Relation.id).where(
                Relation.from_asset_uid == source.uid, Relation.to_asset_uid == target.uid,
                Relation.relation_type == relation))
            if exists is None:
                raise Refused(f"{source.key} —{relation}→ {target.key} is not a relation that exists")
        elif source is not None and target is not None:
            problems = registry.edge_violations(self.db, source, relation, target)
            if problems:
                raise Refused("; ".join(problems))
        payload = {"relation_type": relation,
                   "from": {"uid": source.uid} if source is not None else {"new": source_new.number},
                   "to": {"uid": target.uid} if target is not None else {"new": target_new.number}}
        verb = "Remove" if remove else "Relate"
        return ("unrelate" if remove else "relate"), payload, f"{verb} {source_label} —{relation}→ {target_label}"


# --- reading and applying ------------------------------------------------------------------------------------

def view(action: AskAction) -> dict:
    return {"id": action.id, "number": action.number, "turn_seq": action.turn_seq, "kind": action.kind,
            "summary": action.summary, "status": action.status, "result": action.result, "error": action.error,
            "reason": (action.payload or {}).get("reason")}


def of_conversation(db: Session, conversation_id: str) -> list[AskAction]:
    return list(db.scalars(select(AskAction).where(AskAction.conversation_id == conversation_id)
                           .order_by(AskAction.number)))


def context(db: Session, conversation_id: str) -> Optional[str]:
    """What became of the changes proposed so far, for the model's next turn."""
    lines = []
    for a in of_conversation(db, conversation_id):
        what = {"proposed": "waiting for confirmation", "applied": "applied", "failed": f"failed: {a.error}",
                "discarded": "discarded by the person"}[a.status]
        made = f" → {a.result.get('key')}" if a.status == "applied" and (a.result or {}).get("key") else ""
        lines.append(f"A{a.number} ({'new:' + str(a.number) + ', ' if a.kind == 'create' else ''}{a.summary}): "
                     f"{what}{made}")
    return ("Changes proposed earlier in this conversation:\n" + "\n".join(lines)) if lines else None


def _detail(exc: HTTPException) -> str:
    d = exc.detail
    if isinstance(d, dict):
        return str(d.get("error") or d.get("detail") or json.dumps(d, default=str))
    return str(d)


def _resolve(db: Session, conversation_id: str, end: dict) -> str:
    if "uid" in end:
        return end["uid"]
    action = db.scalar(select(AskAction).where(AskAction.conversation_id == conversation_id,
                                               AskAction.number == end["new"]))
    if action is None or action.status != "applied":
        raise HTTPException(status_code=409, detail=f"it needs new:{end['new']}, which has not been created")
    return action.result["uid"]


def _permitted(db: Session, identity, workspace_id: str, kind: str) -> bool:
    from app.auth import OidcIdentity
    from app.services.permissions import resolve_permission
    if not isinstance(identity, OidcIdentity):
        return True          # a token's scope was checked when it reached the workspace
    return resolve_permission(db, identity.user, workspace_id, PERMISSION[kind], "objects")


def _execute(db: Session, identity, workspace_id: str, action: AskAction) -> dict:
    from app.auth import get_current_user_id
    from app.routers import assets as forms
    from app.schemas.asset import AssetCreate, AssetUpdate, RelationCreate
    p = action.payload
    user_id = get_current_user_id(identity)
    if action.kind == "create":
        asset = forms.create_asset(
            AssetCreate(uid=str(uuid.uuid4()), schema_uid=p["schema_uid"], key=p.get("key"), name=p["name"],
                        attributes=dict(p.get("attributes") or {})),
            identity=identity, workspace_id=workspace_id, current_user_id=user_id, db=db)
        return {"uid": asset.uid, "key": asset.key, "name": asset.name}
    if action.kind == "update":
        asset = db.get(Asset, p["uid"])
        if asset is None:
            raise HTTPException(status_code=404, detail=f"{p['key']} no longer exists")
        merged = {k: v for k, v in {**(asset.attributes or {}), **(p.get("attributes") or {})}.items() if v is not None}
        body = AssetUpdate(**({"name": p["name"]} if p.get("name") else {}),
                           **({"attributes": merged} if p.get("attributes") else {}))
        out = forms.update_asset(p["uid"], body, identity=identity, workspace_id=workspace_id,
                                 current_user_id=user_id, db=db, if_match=None)
        return {"uid": out.uid, "key": out.key, "name": out.name}
    source = _resolve(db, action.conversation_id, p["from"])
    target = _resolve(db, action.conversation_id, p["to"])
    if action.kind == "relate":
        relation = forms.create_relation(RelationCreate(from_asset_uid=source, to_asset_uid=target,
                                                        relation_type=p["relation_type"]),
                                         identity=identity, workspace_id=workspace_id, db=db)
        return {"relation_id": relation.id}
    relation = db.scalar(select(Relation).where(Relation.from_asset_uid == source, Relation.to_asset_uid == target,
                                                Relation.relation_type == p["relation_type"]))
    if relation is None:
        raise HTTPException(status_code=404, detail="that relation no longer exists")
    forms.delete_relation(relation.id, identity=identity, workspace_id=workspace_id, db=db)
    return {"removed": True}


def apply(db: Session, identity, workspace_id: str, actor: str, conversation_id: str,
          ids: list[str]) -> list[dict]:
    """Apply the chosen proposals in the order they were made; each one stands or fails on its own (a relation
    to a record whose creation failed fails with it)."""
    now = datetime.now(timezone.utc)
    chosen = [a for a in of_conversation(db, conversation_id) if a.id in set(ids) and a.status == "proposed"]
    for action in chosen:
        try:
            if not _permitted(db, identity, workspace_id, action.kind):
                raise HTTPException(status_code=403, detail=f"you may not {PERMISSION[action.kind]} objects here")
            result = _execute(db, identity, workspace_id, action)
            action.status, action.result, action.error = "applied", result, None
        except HTTPException as exc:
            db.rollback()
            action = db.get(AskAction, action.id)
            action.status, action.error = "failed", _detail(exc)
        except Exception as exc:  # noqa: BLE001 — told to the person, never half-applied silently
            db.rollback()
            action = db.get(AskAction, action.id)
            action.status, action.error = "failed", f"{type(exc).__name__}: {exc}"
        action.decided_by, action.decided_at = actor, now
        db.commit()
    return [view(a) for a in of_conversation(db, conversation_id)]


def discard(db: Session, actor: str, conversation_id: str, ids: list[str]) -> list[dict]:
    now = datetime.now(timezone.utc)
    for action in of_conversation(db, conversation_id):
        if action.id in set(ids) and action.status == "proposed":
            action.status, action.decided_by, action.decided_at = "discarded", actor, now
    db.commit()
    return [view(a) for a in of_conversation(db, conversation_id)]
