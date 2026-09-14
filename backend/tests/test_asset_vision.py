"""Reading a photograph into a draft object.

What matters is the restraint: the model proposes, and anything it claims
that this workspace cannot support — a type that does not exist, an object
key that matches nothing — is not allowed to become data.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.asset_vision import identify, parse_identification

TYPES = {"Cameras", "Magnets", "Power Supplies"}


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def workspace():
    """Returns (workspace_id, the key of the one object in it).

    Asset keys are unique across the installation, so each test's object
    needs its own — reusing a literal collides on the second test.
    """
    workspace_id = f"vis-{secrets.token_hex(4)}"
    key = f"LNFT2-{secrets.randbelow(900000) + 100000}"
    db = SessionLocal()
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    for name in TYPES:
        db.add(Schema(
            uid=f"{workspace_id}:{name.lower().replace(' ', '-')}",
            workspace_id=workspace_id, name=name, applies_to="objects",
        ))
    db.flush()
    db.add(Asset(
        uid=f"a-{workspace_id}", workspace_id=workspace_id,
        schema_uid=f"{workspace_id}:cameras", key=key,
        name="FI4-B-CAM-VIS-001", type="Cameras",
    ))
    db.commit()
    db.close()
    return workspace_id, key


# --- reading the reply --------------------------------------------------

def test_a_normal_answer_is_read():
    reply = (
        '{"type": "Cameras", "name": "Basler area-scan camera", '
        '"manufacturer": "Basler", "model": "acA1300", "serial": null, '
        '"visible_text": ["LNFT2-101"], "description": "A camera on a rack.", '
        '"confidence": "high"}'
    )
    data = parse_identification(reply, TYPES)
    assert data["type"] == "Cameras"
    assert data["manufacturer"] == "Basler"
    assert data["visible_text"] == ["LNFT2-101"]
    assert data["confidence"] == "high"


def test_a_reasoning_models_think_block_is_stripped():
    reply = (
        "<think>This looks like a camera mounted on a rail.</think>\n"
        '{"type": "Cameras", "name": "A camera", "confidence": "medium"}'
    )
    assert parse_identification(reply, TYPES)["type"] == "Cameras"


def test_a_type_this_workspace_does_not_have_is_refused():
    """The model may name a perfectly sensible piece of equipment that is
    not one of this inventory's types. That is not a type."""
    reply = '{"type": "Oscilloscope", "name": "A scope", "confidence": "high"}'
    data = parse_identification(reply, TYPES)
    assert data["type"] is None
    assert data["name"] == "A scope", "what it saw is still worth keeping"


def test_an_unreadable_answer_is_reported_not_raised():
    assert parse_identification("I cannot tell what this is.", TYPES) is None
    assert parse_identification("", TYPES) is None


def test_confidence_is_never_invented():
    data = parse_identification('{"type": "Cameras", "confidence": "certain"}', TYPES)
    assert data["confidence"] == "low", "an unrecognised confidence is not a high one"


# --- the draft ----------------------------------------------------------

def test_a_key_read_from_a_label_becomes_a_link_to_the_real_object(workspace, monkeypatch):
    """The point of photographing the label: the object is already
    recorded, and this is what ties the picture to it."""
    workspace_id, key = workspace
    monkeypatch.setattr(
        "app.services.asset_vision.look",
        lambda *a, **k: '{"type": "Cameras", "name": "Camera on rack", '
                        f'"visible_text": ["{key}", "Basler"], "confidence": "high"}}',
    )
    db = SessionLocal()
    result = identify(db, workspace_id, None, b"fake-image", "image/jpeg")
    assert [m["key"] for m in result["matches"]] == [key]
    assert result["matches"][0]["name"] == "FI4-B-CAM-VIS-001"
    assert result["unmatched_keys"] == []
    assert result["type_uid"].endswith(":cameras")
    db.close()


def test_a_key_matching_nothing_is_shown_not_linked(workspace, monkeypatch):
    """A plausible-looking code that is not in the inventory must not
    become a relation to something that does not exist."""
    workspace_id, _key = workspace
    monkeypatch.setattr(
        "app.services.asset_vision.look",
        lambda *a, **k: '{"type": "Magnets", "name": "A magnet", '
                        '"visible_text": ["LNFM-999"], "confidence": "medium"}',
    )
    db = SessionLocal()
    result = identify(db, workspace_id, None, b"fake-image", "image/jpeg")
    assert result["matches"] == []
    assert result["unmatched_keys"] == ["LNFM-999"]
    db.close()


def test_an_unreadable_reply_yields_an_empty_draft_with_a_reason(workspace, monkeypatch):
    workspace_id, _key = workspace
    monkeypatch.setattr("app.services.asset_vision.look", lambda *a, **k: "no idea, sorry")
    db = SessionLocal()
    result = identify(db, workspace_id, None, b"fake-image", "image/jpeg")
    assert result["type_uid"] is None
    assert result["error"] is not None
    db.close()


def test_the_model_is_told_only_this_workspaces_types(workspace, monkeypatch):
    seen = {}

    def fake(endpoint, image, mime, system, user, max_tokens=0):
        seen["user"] = user
        return '{"type": null, "name": null, "confidence": "low"}'

    workspace_id, _key = workspace
    monkeypatch.setattr("app.services.asset_vision.look", fake)
    db = SessionLocal()
    identify(db, workspace_id, None, b"fake-image", "image/jpeg")
    db.close()
    for name in TYPES:
        assert name in seen["user"]
