import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.workspace import Workspace

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def token():
    db = SessionLocal()
    workspace_id = f"test-{secrets.token_hex(4)}"
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace_id, token_hash=hash_token(raw)))
    db.commit()
    db.close()
    return raw


def auth(raw_token: str) -> dict:
    return {"Authorization": f"Bearer {raw_token}"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_requires_auth():
    assert client.get("/v1/schemas").status_code == 401
    assert client.get("/v1/schemas", headers=auth("bogus")).status_code == 401


def test_schema_crud(token):
    created = client.post(
        "/v1/schemas",
        json={"uid": "s-1", "name": "Magnet", "metadata": {"a": 1}},
        headers=auth(token),
    )
    assert created.status_code == 201
    assert created.json()["metadata"] == {"a": 1}

    dup = client.post(
        "/v1/schemas", json={"uid": "s-1", "name": "dup"}, headers=auth(token)
    )
    assert dup.status_code == 409

    fetched = client.get("/v1/schemas/s-1", headers=auth(token))
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Magnet"

    deleted = client.delete("/v1/schemas/s-1", headers=auth(token))
    assert deleted.status_code == 204
    assert client.get("/v1/schemas/s-1", headers=auth(token)).status_code == 404


def test_asset_and_sync(token):
    client.post(
        "/v1/schemas", json={"uid": "s-2", "name": "Pump"}, headers=auth(token)
    )
    created = client.post(
        "/v1/assets",
        json={
            "uid": "a-1",
            "schema_uid": "s-2",
            "key": f"PUMP-{secrets.token_hex(3)}",
            "name": "Pump 1",
            "type": "Pump",
            "attributes": {"flow": 3.5},
        },
        headers=auth(token),
    )
    assert created.status_code == 201

    synced = client.get(
        "/v1/sync", params={"since": "1970-01-01T00:00:00Z"}, headers=auth(token)
    )
    assert synced.status_code == 200
    body = synced.json()
    assert any(a["uid"] == "a-1" for a in body["assets"])
    assert any(s["uid"] == "s-2" for s in body["schemas"])


def test_workspace_isolation(token):
    client.post("/v1/schemas", json={"uid": "s-3", "name": "Iso"}, headers=auth(token))

    db = SessionLocal()
    other_ws = f"other-{secrets.token_hex(4)}"
    db.add(Workspace(id=other_ws, name="Other"))
    db.flush()
    other_raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=other_ws, token_hash=hash_token(other_raw)))
    db.commit()
    db.close()

    resp = client.get("/v1/schemas/s-3", headers=auth(other_raw))
    assert resp.status_code == 404
