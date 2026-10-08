"""Browsing equipment a page at a time (the field app's Assets tab): searched by key or name, sorted, narrowed
to a type and everything below it — and, without a page asked for, the list exactly as before."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.schema import Schema
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)


@pytest.fixture()
def ws():
    t = secrets.token_hex(3)
    ws = f"browse-{t}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Browse"))
    db.flush()
    db.add_all([Schema(uid=f"{ws}:vacuum", workspace_id=ws, name="Vacuum", applies_to="objects", is_concrete=False),
                Schema(uid=f"{ws}:pump", workspace_id=ws, name="Ion Pump", applies_to="objects",
                       parent_schema_uid=f"{ws}:vacuum"),
                Schema(uid=f"{ws}:magnet", workspace_id=ws, name="Magnet", applies_to="objects")])
    db.flush()
    now = datetime.now(timezone.utc)
    for i, (key, name, schema, age) in enumerate([("IP-01", "Pump gun", "pump", 3), ("IP-02", "Pump linac", "pump", 1),
                                                   ("QF-01", "Quad arc", "magnet", 2)]):
        db.add(Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=f"{ws}:{schema}", key=f"{t}-{key}",
                     name=name, type=schema, created_at=now - timedelta(days=age),
                     updated_at=now - timedelta(days=10 - age)))
    db.add(Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=f"{ws}:pump", key=f"{t}-IP-99", name="Pump gone",
                 type="pump", deleted_at=now))
    headers = token(db, ws)
    db.commit()
    db.close()
    yield ws, headers
    db = SessionLocal()
    from app.ledger.audit import allow_purge
    allow_purge(db)
    db.delete(db.get(Workspace, ws))
    db.commit()
    db.close()


def names(r):
    return [a["name"] for a in r.json()]


def test_a_page_is_sorted_counted_and_leaves_out_what_was_deleted(ws):
    w, h = ws
    r = client.get("/v1/assets", headers=h, params={"limit": 2, "sort": "name"})
    assert names(r) == ["Pump gun", "Pump linac"] and r.headers["X-Total-Count"] == "3"
    r = client.get("/v1/assets", headers=h, params={"limit": 2, "offset": 2, "sort": "name"})
    assert names(r) == ["Quad arc"]
    newest = client.get("/v1/assets", headers=h, params={"limit": 10, "sort": "created", "order": "desc"})
    assert names(newest) == ["Pump linac", "Quad arc", "Pump gun"]
    changed = client.get("/v1/assets", headers=h, params={"limit": 10, "sort": "updated", "order": "desc"})
    assert names(changed) == ["Pump gun", "Quad arc", "Pump linac"]


def test_search_and_a_type_with_everything_below_it(ws):
    w, h = ws
    assert names(client.get("/v1/assets", headers=h, params={"limit": 10, "q": "LINAC"})) == ["Pump linac"]
    assert names(client.get("/v1/assets", headers=h, params={"limit": 10, "q": "ip-0"})) == ["Pump gun", "Pump linac"]
    below = client.get("/v1/assets", headers=h, params={"limit": 10, "schema_uid": f"{w}:vacuum", "include_subtypes": True})
    assert names(below) == ["Pump gun", "Pump linac"]
    only = client.get("/v1/assets", headers=h, params={"limit": 10, "schema_uid": f"{w}:vacuum"})
    assert names(only) == [], "a type alone holds only its own records"


def test_without_a_page_the_list_is_as_it_always_was(ws):
    w, h = ws
    r = client.get("/v1/assets", headers=h)
    assert len(r.json()) == 4 and "X-Total-Count" not in r.headers


def test_each_type_counts_its_own_records(ws):
    w, h = ws
    counts = client.get("/v1/assets/type-counts", headers=h).json()
    assert counts[f"{w}:pump"] == 2 and counts[f"{w}:magnet"] == 1 and f"{w}:vacuum" not in counts


def test_a_bad_sort_or_page_is_refused(ws):
    _w, h = ws
    assert client.get("/v1/assets", headers=h, params={"sort": "colour"}).status_code == 422
    assert client.get("/v1/assets", headers=h, params={"limit": 0}).status_code == 422
    assert client.get("/v1/assets", headers=h, params={"limit": 501}).status_code == 422
