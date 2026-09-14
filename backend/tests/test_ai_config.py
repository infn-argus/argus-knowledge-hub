"""Configuring where AI features send their requests.

The behaviour that matters is the gate: nothing is available until an
endpoint has been checked, and the check has to fail for the three reasons
that actually occur — unreachable, key rejected, model not served — rather
than just pinging the host.
"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.workspace import Workspace
from app.services.llm import Endpoint, check

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def token():
    db = SessionLocal()
    workspace_id = f"ai-{secrets.token_hex(4)}"
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace_id, token_hash=hash_token(raw)))
    db.commit()
    db.close()
    return raw


def auth(raw: str) -> dict:
    return {"Authorization": f"Bearer {raw}"}


def test_a_workspace_starts_with_no_endpoint(token):
    assert client.get("/v1/ai/config", headers=auth(token)).json() is None

    status = client.get("/v1/ai/status", headers=auth(token)).json()
    assert status["configured"] is False
    assert status["validated"] is False
    assert "No AI endpoint" in status["reason"]


def test_the_api_key_is_never_returned(token):
    """It is stored encrypted and only decrypted to make a request. A form
    needs to know whether one is set, and nothing more."""
    resp = client.put(
        "/v1/ai/config",
        json={
            "base_url": "https://gateway.invalid/v1",
            "model": "some-model",
            "api_key": "sk-secret-value",
            "enabled": True,
        },
        headers=auth(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_api_key"] is True
    assert "api_key" not in body
    assert "sk-secret-value" not in resp.text


def test_the_stored_key_survives_an_edit_that_omits_it(token):
    client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "m", "api_key": "sk-keep-me"},
        headers=auth(token),
    )
    # A later edit that changes the model shouldn't wipe the credential.
    resp = client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "m2"},
        headers=auth(token),
    )
    assert resp.json()["has_api_key"] is True


def test_an_empty_key_clears_it(token):
    """Some endpoints on the internal network take no key at all."""
    client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "m", "api_key": "sk-x"},
        headers=auth(token),
    )
    resp = client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "m", "api_key": ""},
        headers=auth(token),
    )
    assert resp.json()["has_api_key"] is False


def test_changing_the_settings_invalidates_the_last_check(token):
    """What a check proved was about the configuration it ran against. A
    new model name has not been checked, whatever the old result said."""
    client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "m", "enabled": True},
        headers=auth(token),
    )
    client.post("/v1/ai/config/check", headers=auth(token))

    resp = client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "different", "enabled": True},
        headers=auth(token),
    )
    assert resp.json()["last_check_ok"] is None
    assert client.get("/v1/ai/status", headers=auth(token)).json()["validated"] is False


def test_features_stay_unavailable_until_a_check_passes(token):
    """Enabling is not the same as working. An endpoint whose key has since
    been rotated must read as unavailable, not offer suggestions that fail."""
    client.put(
        "/v1/ai/config",
        json={"base_url": "https://gateway.invalid/v1", "model": "m", "enabled": True},
        headers=auth(token),
    )
    status = client.get("/v1/ai/status", headers=auth(token)).json()
    assert status["enabled"] is True
    assert status["validated"] is False
    assert "not been checked" in status["reason"]


def test_checking_an_unconfigured_workspace_says_so(token):
    assert client.post("/v1/ai/config/check", headers=auth(token)).status_code == 404


def test_an_unreachable_endpoint_is_reported_not_raised():
    ok, error, models = check(
        Endpoint(base_url="http://127.0.0.1:9/v1", model="anything")
    )
    assert ok is False
    assert "Could not reach" in error
    assert models == []


def test_a_model_the_endpoint_does_not_serve_is_caught(monkeypatch):
    """The failure that passes every other health check and then breaks on
    the first real request."""
    monkeypatch.setattr(
        "app.services.llm.list_models", lambda endpoint: ["qwen36-27b", "gemma-4-31b-it"]
    )
    ok, error, models = check(Endpoint(base_url="https://x/v1", model="minimax-m27"))
    assert ok is False
    assert "does not serve" in error and "minimax-m27" in error
    assert "qwen36-27b" in error, "and it should say what is on offer"
    assert models == ["qwen36-27b", "gemma-4-31b-it"]


def test_a_missing_embedding_model_is_caught(monkeypatch):
    monkeypatch.setattr("app.services.llm.list_models", lambda endpoint: ["chat-model"])
    ok, error, _models = check(
        Endpoint(base_url="https://x/v1", model="chat-model", embedding_model="nope")
    )
    assert ok is False
    assert "embedding model" in error
