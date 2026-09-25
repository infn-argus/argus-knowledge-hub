"""Ledger-only workspaces (asset-model-revision §13 S5): record facts and
relations change only through the fact ledger. The API goes through it;
anything written around it is refused by the database itself."""
import secrets
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.db import SessionLocal
from app.ledger import engine
from app.main import app
from app.models.asset import Asset, Relation
from app.models.ledger import Decision
from app.models.workspace import Workspace
from tests.test_legacy_migration import Legacy
from tests.test_ledger_transition import token

client = TestClient(app)


@pytest.fixture()
def ws():
    w = f"lo-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=w, name=w))
    db.flush()
    schema = engine.ensure_type(db, w, "Ion Pump")
    headers = token(db, w)
    db.commit()
    sid = schema.uid
    db.close()
    r = client.put("/v1/ledger/ledger-only", headers=headers, json={"enabled": True, "reason": "S5 go-live"})
    assert r.status_code == 200 and r.json()["enabled"], r.text
    return w, headers, sid


def create(headers, sid, key, attrs):
    uid = str(uuid.uuid4())
    r = client.post("/v1/assets", headers=headers, json={"uid": uid, "schema_uid": sid, "key": key, "name": key,
                                                          "type": "Ion Pump", "attributes": attrs})
    assert r.status_code == 201, r.text
    return uid, r.json()


def test_the_api_writes_records_and_relations_through_the_ledger(ws):
    w, headers, sid = ws
    uid, created = create(headers, sid, f"{w}-SIP01", {"serial": "S-1", "manufacturer": "Agilent"})
    assert created["attributes"] == {"serial": "S-1", "manufacturer": "Agilent"}
    other, _ = create(headers, sid, f"{w}-SIP02", {})

    edited = client.put(f"/v1/assets/{uid}", headers=headers, json={
        "name": "Gun ion pump", "attributes": {"serial": "S-1b", "notes": "refurbished 2025"}})
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["name"] == "Gun ion pump"
    assert body["attributes"] == {"serial": "S-1b", "notes": "refurbished 2025"}      # manufacturer removed

    rel = client.post("/v1/relations", headers=headers, json={"from_asset_uid": uid, "to_asset_uid": other,
                                                              "relation_type": "connected to"})
    assert rel.status_code == 201, rel.text
    assert rel.json()["derivation"] == "ledger"
    assert client.delete(f"/v1/relations/{rel.json()['id']}", headers=headers).status_code == 204

    # Deleting retires: the record and its history stay.
    assert client.delete(f"/v1/assets/{other}", headers=headers).status_code == 204
    db = SessionLocal()
    assert db.get(Asset, other).record_status == "Retired"
    assert db.query(Relation).filter_by(from_asset_uid=uid, to_asset_uid=other).count() == 0
    # Every change has its author in the ledger.
    kinds = {(d.predicate, d.actor) for d in db.scalars(select(Decision).where(Decision.subject_uid == uid))}
    assert ("attr:serial", "api-token") in kinds and ("name", "api-token") in kinds
    assert ("rel:connected to", "api-token") in kinds
    db.close()
    trail = client.get(f"/v1/ledger/records/{uid}/audit", headers=headers).json()
    assert any(e.get("predicate") == "attr:serial" for e in trail)


def test_writes_around_the_ledger_are_refused_by_the_database(ws):
    w, headers, sid = ws
    uid, _ = create(headers, sid, f"{w}-SIP03", {"serial": "S-3"})
    db = SessionLocal()
    rec = db.get(Asset, uid)
    rec.attributes = {"serial": "typed over"}
    with pytest.raises(DBAPIError) as refused:
        db.commit()
    assert "ledger-only" in str(refused.value)
    db.rollback()
    db.add(Asset(uid=str(uuid.uuid4()), workspace_id=w, schema_uid=sid, key=f"{w}-X", name="x", type="Ion Pump",
                 attributes={}))
    with pytest.raises(DBAPIError):
        db.commit()
    db.rollback()
    db.add(Relation(workspace_id=w, from_asset_uid=uid, to_asset_uid=uid, relation_type="powers"))
    with pytest.raises(DBAPIError):
        db.commit()
    db.rollback()
    # Display and caching fields are not facts.
    rec = db.get(Asset, uid)
    rec.inbound_relations = []
    db.commit()
    # The ledger itself still rebuilds the workspace.
    engine.rebuild(db, w)
    db.commit()
    assert db.get(Asset, uid).attributes == {"serial": "S-3"}
    db.close()


def test_a_workspace_goes_ledger_only_only_once_its_legacy_records_are_migrated():
    L = Legacy()
    refused = client.put("/v1/ledger/ledger-only", headers=L.headers, json={"enabled": True, "reason": "go-live"})
    assert refused.status_code == 409 and refused.json()["detail"]["legacy"]["unplanned"] == 7
    assert client.put("/v1/ledger/ledger-only", headers=L.headers,
                      json={"enabled": True, "reason": " "}).status_code == 422
    status = client.get("/v1/ledger/ledger-only", headers=L.headers).json()
    assert status["enabled"] is False and not status["legacy"]["ok"]
