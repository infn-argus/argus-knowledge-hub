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
    db.commit()
    db.close()
    yield


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
