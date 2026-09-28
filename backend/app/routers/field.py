"""What the field client needs from the server beyond the ordinary API
(asset-model-revision §24.3, flutter-app-design §3, §7).

* `/v1/devices`: register the device a person signs in on, list one's
  devices, revoke one. A revoked device's next request answers 401
  `revoked` and the client wipes itself (A71).
* `/v1/links/resolve`: the stable universal links (`/asset/<uid>`,
  `/position/<uid>`, `/installation/<uid>`, `/document/<uid>`,
  `/ticket/<key>`, `/review/<uid>`, `/lookup/<key>`) as the record they
  open, for the web application and the field client alike. A record the
  caller may not read answers exactly as a missing one (I-ACL-1).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import PatIdentity, get_grants, get_identity
from app.db import get_db
from app.models.asset import Asset
from app.models.device import Device

devices_router = APIRouter(prefix="/v1/devices", tags=["field client"])
links_router = APIRouter(prefix="/v1/links", tags=["field client"])


def principal_of(identity) -> str:
    if isinstance(identity, PatIdentity):
        return f"pat:{identity.workspace_id}"
    return identity.user.id


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceIn(BaseModel):
    installation_id: str
    platform: str
    app_version: str
    name: Optional[str] = None


def _view(d: Device) -> dict:
    return {"id": d.id, "platform": d.platform, "app_version": d.app_version, "name": d.name,
            "registered_at": d.registered_at, "last_seen_at": d.last_seen_at, "last_sync_at": d.last_sync_at,
            "revoked_at": d.revoked_at, "revoked_by": d.revoked_by, "revoke_reason": d.revoke_reason}


@devices_router.post("", status_code=201)
def register_device(body: DeviceIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Register (or re-register) this installation for the signed-in person."""
    if not body.installation_id.strip() or not body.platform.strip():
        raise HTTPException(status_code=422, detail={"error": "installation_id and platform are required",
                                                     "code": "invalid"})
    who = principal_of(identity)
    d = db.scalar(select(Device).where(Device.principal == who, Device.installation_id == body.installation_id,
                                       Device.revoked_at.is_(None)))
    if d is None:
        d = Device(id=str(uuid.uuid4()), principal=who, installation_id=body.installation_id.strip(),
                   platform=body.platform.strip().lower(), app_version=body.app_version.strip(), name=body.name)
        db.add(d)
    else:
        d.app_version, d.name = body.app_version.strip(), body.name or d.name
    d.last_seen_at = _now()
    db.commit()
    return _view(d)


@devices_router.get("")
def my_devices(identity=Depends(get_identity), db: Session = Depends(get_db)):
    """The devices registered for the signed-in person (all of them, for an administrator)."""
    q = select(Device).order_by(Device.registered_at.desc())
    if isinstance(identity, PatIdentity) or not identity.user.is_admin:
        q = q.where(Device.principal == principal_of(identity))
    return [_view(d) for d in db.scalars(q)]


class RevokeIn(BaseModel):
    reason: str


@devices_router.post("/{device_id}/revoke")
def revoke_device(device_id: str, body: RevokeIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Revoke a device: its next request answers 401 `revoked`, and it wipes itself."""
    d = db.get(Device, device_id)
    admin = not isinstance(identity, PatIdentity) and identity.user.is_admin
    if d is None or (d.principal != principal_of(identity) and not admin):
        raise HTTPException(status_code=404, detail={"error": "no such device", "code": "not_found"})
    if not body.reason.strip():
        raise HTTPException(status_code=422, detail={"error": "say why", "code": "invalid"})
    if d.revoked_at is None:
        d.revoked_at, d.revoked_by, d.revoke_reason = _now(), principal_of(identity), body.reason.strip()
    db.commit()
    return _view(d)


def device_refusal(db: Session, device_id: Optional[str]) -> Optional[dict]:
    """The 401 body when the request comes from a revoked device, else None. Marks it seen."""
    if not device_id:
        return None
    d = db.get(Device, device_id)
    if d is None:
        return None
    if d.revoked_at is not None:
        return {"error": "This device was signed out of ARGUS. Its local data has to be removed.",
                "code": "revoked"}
    now = _now()
    if d.last_seen_at is None or (now - d.last_seen_at).total_seconds() > 60:
        d.last_seen_at = now
        db.commit()
    return None


# --------------------------------------------------------------------------- universal links

KINDS = ("asset", "position", "installation", "document", "ticket", "review", "lookup")


def _not_found():
    raise HTTPException(status_code=404, detail={"error": "Not found, or not visible to you.", "code": "not_found"})


def _asset_link(db: Session, uid: str, workspace_id: str, grants, kind: str) -> dict:
    from app.intake.guide import nature
    from app.models.schema import Schema
    from app.services.visibility import asset_visible_in
    a = db.get(Asset, uid)
    if a is None or not asset_visible_in(a, workspace_id, grants):
        _not_found()
    schema = db.get(Schema, a.schema_uid)
    is_position = schema is not None and nature(db, schema) == "position"
    return {"kind": "position" if is_position else "asset", "uid": a.uid, "key": a.key, "name": a.name,
            "type": a.type, "workspace_id": a.workspace_id, "web_path": f"/assets/{a.uid}"}


@links_router.get("/resolve")
def resolve_link(path: str = Query(..., description="e.g. /asset/<uid> or https://host/ticket/SPARC-123"),
                 identity=Depends(get_identity), grants=Depends(get_grants), db: Session = Depends(get_db),
                 workspace_id: Optional[str] = Query(None)):
    """The record a universal link opens, if the caller may read it."""
    from urllib.parse import unquote, urlparse
    from app.routers.ledger import _readable_workspaces, _resolve_one
    raw = urlparse(path).path if "://" in path else path
    parts = [p for p in unquote(raw).split("/") if p]
    if len(parts) < 2 or parts[0] not in KINDS:
        raise HTTPException(status_code=422, detail={"error": "not an ARGUS link", "code": "invalid"})
    kind, ident = parts[0], "/".join(parts[1:])
    readable = _readable_workspaces(db, identity)
    ws = workspace_id if workspace_id in readable else (readable[0] if len(readable) == 1 else workspace_id)
    if kind in ("asset", "position"):
        a = db.get(Asset, ident)
        if a is None or a.workspace_id not in readable and not a.is_global:
            _not_found()
        return _asset_link(db, ident, a.workspace_id if a.workspace_id in readable else (ws or ""), grants, kind)
    if kind == "installation":
        from app.ledger import engine
        inst = db.get(Asset, ident)
        if inst is None or inst.type != engine.INSTALLATION or inst.workspace_id not in readable:
            _not_found()
        view = engine.installation_view(db, inst)
        return {"kind": "installation", "uid": inst.uid, "key": inst.key, "position_uid": view.get("position_uid"),
                "asset_uid": view.get("asset_uid"), "workspace_id": inst.workspace_id,
                "web_path": f"/assets/{view.get('position_uid') or inst.uid}"}
    if kind == "document":
        from app.models.document import Document
        d = db.get(Document, ident) or db.scalar(select(Document).where(Document.code == ident))
        if d is None or (d.workspace_id not in readable and not (d.is_global and d.confidentiality != "riservato")):
            _not_found()
        return {"kind": "document", "uid": d.uid, "key": d.code, "name": d.title, "workspace_id": d.workspace_id,
                "web_path": f"/documents/{d.uid}"}
    if kind == "ticket":
        from app.models.issue import Issue
        from app.services.visibility import can_see
        issue = db.get(Issue, ident)
        if issue is None:
            hit = _resolve_one(db, ident, readable)
            issue = db.get(Issue, hit.get("uid")) if hit.get("status") == "migrated" and hit.get("kind") == "ticket" else None
        if issue is None or issue.workspace_id not in readable or not can_see(issue) or issue.deleted_at is not None:
            _not_found()
        return {"kind": "ticket", "uid": issue.uid, "name": issue.title, "workspace_id": issue.workspace_id,
                "web_path": f"/tickets/{issue.uid}"}
    if kind == "review":
        from app.ledger import engine
        from app.models.ledger import Claim, Conflict
        subject = None
        c = db.get(Conflict, ident)
        if c is not None:
            subject = c.subject_uid
        else:
            claim = db.get(Claim, ident)
            subject = engine.resolve_ref(db, claim.source_ref) if claim is not None else None
        a = db.get(Asset, subject) if subject else None
        from app.services.visibility import can_see
        if a is None or a.workspace_id not in readable or not can_see(a):
            _not_found()
        return {"kind": "review", "uid": ident, "record_uid": a.uid, "workspace_id": a.workspace_id,
                "web_path": "/review"}
    # lookup: an external key (Jira, Insight, a former key), else a label value
    hit = _resolve_one(db, ident, readable)
    if hit.get("status") == "migrated":
        target = "ticket" if hit.get("kind") == "ticket" else "asset"
        return resolve_link(f"/{target}/{hit['uid']}", identity, grants, db, workspace_id)
    holders = _label_holders(db, ident, readable, grants)
    if len(holders) == 1:
        a = holders[0]
        return _asset_link(db, a.uid, a.workspace_id if a.workspace_id in readable else (ws or ""), grants, "asset")
    if len(holders) > 1:
        # A serial held by two units opens neither: the person chooses (A67).
        raise HTTPException(status_code=409, detail={
            "error": "This label matches more than one record. Choose the one in front of you.",
            "code": "ambiguous",
            "candidates": [{"uid": a.uid, "key": a.key, "name": a.name, "type": a.type,
                            "attributes": {k: (a.attributes or {}).get(k) for k in LABEL_FIELDS
                                           if (a.attributes or {}).get(k)}} for a in holders[:20]]})
    raise HTTPException(status_code=404, detail={"error": "Not found, or not visible to you.", "code": "not_found",
                                                 "archive": hit.get("archive")})


LABEL_FIELDS = ("serial", "inventory_number", "mac", "manufacturer")


def _label_holders(db: Session, value: str, readable: list[str], grants) -> list[Asset]:
    """Active records this person may see whose serial, inventory number or MAC is the value."""
    from sqlalchemy import or_
    from app.ledger.identity import INACTIVE
    from app.services.visibility import can_see
    v = value.strip()
    if not v:
        return []
    col = Asset.attributes
    q = select(Asset).where(
        or_(Asset.workspace_id.in_(readable), Asset.is_global.is_(True)),
        Asset.record_status.notin_(INACTIVE),
        or_(col["serial"].astext == v, col["inventory_number"].astext == v,
            col["mac"].astext == v.lower().replace("-", ":"))).order_by(Asset.key).limit(50)
    return [a for a in db.scalars(q) if can_see(a, grants)]
