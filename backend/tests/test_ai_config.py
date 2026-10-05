"""The shared AI endpoint.

With a workspace per beamline, configuring the same gateway eight times is
eight chances to get it wrong. A workspace with no endpoint of its own uses
the one in the global workspace — except for the two things that must not
travel with it.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.llm_config import LLMConfig
from app.models.workspace import Workspace
from app.services.ai_config import resolve


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _only_this_tests_global_workspace():
    """The shared default is installation-wide by definition, so a global
    workspace left behind by another test would answer for this one."""
    db = SessionLocal()
    db.query(Workspace).filter(Workspace.is_global.is_(True)).update(
        {Workspace.is_global: False}, synchronize_session=False
    )
    db.query(LLMConfig).filter(LLMConfig.workspace_id == "__installation__").delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(LLMConfig).filter(LLMConfig.workspace_id == "__installation__").delete()
    db.commit()
    db.close()


def make(is_global=False, **config):
    """A workspace, optionally with an endpoint configured in it."""
    ws = f"ws-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws, is_global=is_global))
    db.flush()
    if config:
        db.add(LLMConfig(workspace_id=ws, **{
            "base_url": "https://shared/v1", "model": "minimax-m27",
            "enabled": True, "last_check_ok": True, **config,
        }))
    db.commit()
    db.close()
    return ws


def test_a_workspace_with_no_endpoint_uses_the_shared_default():
    make(is_global=True, base_url="https://gw.infn.it/v1", model="minimax-m27",
         vision_model="gemma-4-31b-it", asr_model="whisper-3", tts_model="kokoro-1")
    beamline = make()
    db = SessionLocal()
    config, inherited_from = resolve(db, beamline)
    assert config is not None and inherited_from is not None
    assert config.base_url == "https://gw.infn.it/v1"
    assert config.vision_model == "gemma-4-31b-it"
    assert (config.asr_model, config.tts_model) == ("whisper-3", "kokoro-1")
    db.close()


def test_its_own_endpoint_wins_over_the_default():
    make(is_global=True, base_url="https://shared/v1", model="shared-model")
    beamline = make(base_url="https://own/v1", model="own-model")
    db = SessionLocal()
    config, inherited_from = resolve(db, beamline)
    assert (config.base_url, inherited_from) == ("https://own/v1", None)
    db.close()


def test_permission_to_send_confidential_text_never_travels():
    """It is a decision about this workspace's documents, and nobody made it
    by ticking a box in another workspace."""
    make(is_global=True, allow_confidential=True)
    beamline = make()
    db = SessionLocal()
    config, _ = resolve(db, beamline)
    assert config.allow_confidential is False
    db.close()


def test_a_default_that_has_not_been_checked_is_not_inherited():
    """Inheriting a broken endpoint only moves the failure to the point of
    use, which is what checking exists to prevent."""
    make(is_global=True, last_check_ok=False)
    beamline = make()
    db = SessionLocal()
    assert resolve(db, beamline) == (None, None)
    db.close()


def test_a_disabled_default_is_not_inherited():
    make(is_global=True, enabled=False)
    beamline = make()
    db = SessionLocal()
    assert resolve(db, beamline) == (None, None)
    db.close()


def test_inheriting_never_writes_to_the_shared_configuration():
    """The borrowed settings are a copy; a caller that touches them must not
    reconfigure every other beamline."""
    global_ws = make(is_global=True, base_url="https://shared/v1")
    beamline = make()
    db = SessionLocal()
    config, _ = resolve(db, beamline)
    config.base_url = "https://tampered/v1"
    db.commit()
    db.close()

    db = SessionLocal()
    assert db.get(LLMConfig, global_ws).base_url == "https://shared/v1"
    assert db.get(LLMConfig, beamline) is None, "no row should have been created"
    db.close()


def test_with_no_global_workspace_there_is_simply_nothing():
    beamline = make()
    db = SessionLocal()
    assert resolve(db, beamline) == (None, None)
    db.close()



# --- the installation's own settings (Administration → AI) -------------------------------------------

def test_the_installation_settings_are_what_every_workspace_without_its_own_uses():
    from fastapi.testclient import TestClient
    from app.auth import OidcIdentity, get_identity
    from app.main import app
    from app.models.user import User
    from app.routers.ai import endpoint_for
    client = TestClient(app)
    admin = User(id=f"adm-{secrets.token_hex(3)}", email="adm@argus.test", is_admin=True)
    plain = User(id=f"usr-{secrets.token_hex(3)}", email="usr@argus.test", is_admin=False)
    body = {"base_url": "https://gw.infn.it/v1", "model": "qwen36-27b", "embedding_model": "qwen3-embedding-8b",
            "rerank_model": "bge-reranker-v2-m3", "enabled": True, "allow_confidential": True}
    try:
        app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=plain)
        assert client.put("/v1/admin/ai/config", json=body).status_code == 403
        app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=admin)
        saved = client.put("/v1/admin/ai/config", json=body).json()
        assert saved["rerank_model"] == "bge-reranker-v2-m3" and saved["allow_confidential"] is False
        db = SessionLocal()
        db.get(LLMConfig, "__installation__").last_check_ok = True          # as a passed check leaves it
        db.commit()
        beamline = make()
        config, inherited_from = resolve(db, beamline)
        assert inherited_from == "__installation__" and config.model == "qwen36-27b"
        assert config.allow_confidential is False                      # never inherited
        assert endpoint_for(config).rerank_model == "bge-reranker-v2-m3"
        # Its own settings come first; removing them goes back to the installation's.
        own = make(base_url="https://own/v1", model="own-model")
        assert resolve(db, own) == (db.get(LLMConfig, own), None)
        db.delete(db.get(LLMConfig, own))
        db.commit()
        assert resolve(db, own)[1] == "__installation__"
        db.close()
    finally:
        app.dependency_overrides.pop(get_identity, None)


def test_the_installation_settings_come_before_a_global_workspaces():
    make(is_global=True, base_url="https://old-global/v1", model="old")
    db = SessionLocal()
    db.add(LLMConfig(workspace_id="__installation__", base_url="https://installation/v1", model="new",
                     enabled=True, last_check_ok=True))
    db.commit()
    config, inherited_from = resolve(db, make())
    assert config.base_url == "https://installation/v1" and inherited_from == "__installation__"
    db.close()


def test_a_reranker_orders_by_relevance_and_falls_back_to_v1(monkeypatch):
    from app.services import llm
    seen = []

    class R:
        def __init__(self, status, body):
            self.status_code, self._b, self.text = status, body, ""

        def json(self):
            return self._b

    def post(url, headers=None, json=None, timeout=None):
        seen.append(url)
        if url.endswith("/v1/rerank") and not url.endswith("/v1/v1/rerank") and "gw2" in url:
            return R(200, {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.2}]})
        if "gw2" in url:
            return R(404, {})
        return R(200, {"results": [{"index": 0, "relevance_score": 0.1}, {"index": 1, "relevance_score": 0.8}]})
    monkeypatch.setattr(llm.requests, "post", post)
    ep = llm.Endpoint("https://gw/v1", "m", rerank_model="bge")
    assert llm.rerank(ep, "q", ["a", "b"]) == [(1, 0.8), (0, 0.1)]
    ep2 = llm.Endpoint("https://gw2", "m", rerank_model="bge")      # no /rerank at the root: /v1/rerank
    assert llm.rerank(ep2, "q", ["a", "b"])[0] == (1, 0.9) and seen[-1] == "https://gw2/v1/rerank"
    assert llm.rerank(llm.Endpoint("https://gw/v1", "m"), "q", ["a", "b"]) == [(0, 0.0), (1, 0.0)]  # none set


def test_a_workspace_is_told_why_the_installation_settings_do_not_reach_it():
    """Saved but switched off, or never checked, the installation's settings are not shared, and the workspace
    is told which, not that nothing is configured."""
    from fastapi.testclient import TestClient
    from app.auth import OidcIdentity, get_identity
    from app.main import app
    from app.models.user import User
    client = TestClient(app)
    db = SessionLocal()
    db.add(LLMConfig(workspace_id="__installation__", base_url="https://gw/v1", model="m", enabled=False))
    db.commit()
    beamline = make()
    app.dependency_overrides[get_identity] = lambda: OidcIdentity(
        user=User(id="adm-why", email="adm-why@argus.test", is_admin=True))
    try:
        reason = client.get("/v1/ai/status", headers={"X-Workspace-Id": beamline}).json()["reason"]
        assert "switched off" in reason
        config = db.get(LLMConfig, "__installation__")
        config.enabled, config.last_check_ok = True, None
        db.commit()
        assert "not been checked" in client.get("/v1/ai/status", headers={"X-Workspace-Id": beamline}).json()["reason"]
        config.last_check_ok, config.last_check_error = False, "401 from the gateway"
        db.commit()
        assert "401 from the gateway" in client.get("/v1/ai/status", headers={"X-Workspace-Id": beamline}).json()["reason"]
        config.last_check_ok = True
        db.commit()
        status = client.get("/v1/ai/status", headers={"X-Workspace-Id": beamline}).json()
        assert status["configured"] and status["inherited_from"].startswith("the installation")
    finally:
        app.dependency_overrides.pop(get_identity, None)
        db.close()
