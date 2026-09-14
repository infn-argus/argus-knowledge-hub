"""Proposing a type for a document, and keeping it a proposal.

The parsing tests are the ones that matter: the first real run against
INFN's gateway came back as a reasoning model's `<think>` block and no
JSON at all, which is not an exception — it is what these models answer
with, and a batch must survive it.
"""
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.ai_suggestion import AISuggestion
from app.models.api_token import ApiToken
from app.models.document import Document
from app.models.llm_config import LLMConfig
from app.models.workspace import Workspace
from app.services.ai_suggestions import parse_classifications, suggest_document_types
from app.services.document_types import ensure_document_types, type_uid
from app.services.llm import Endpoint

client = TestClient(app)

TYPES = {"Procedure", "Runbook", "Note", "Specification"}


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


# --- parsing the reply --------------------------------------------------

def test_plain_json_is_read():
    reply = '[{"id": "a", "type": "Procedure"}, {"id": "b", "type": "Note"}]'
    assert parse_classifications(reply, TYPES) == {"a": "Procedure", "b": "Note"}


def test_a_reasoning_models_think_block_is_stripped():
    """What INFN's minimax-m27 actually returns. Without this the whole
    batch is lost to text that was never meant to be the answer."""
    reply = (
        "<think>Let me analyse each document. The first looks like a step-by-step\n"
        'operation, so Procedure. The second is a landing page.</think>\n'
        '[{"id": "a", "type": "Procedure"}, {"id": "b", "type": "Note"}]'
    )
    assert parse_classifications(reply, TYPES) == {"a": "Procedure", "b": "Note"}


def test_a_code_fence_is_stripped():
    reply = '```json\n[{"id": "a", "type": "Runbook"}]\n```'
    assert parse_classifications(reply, TYPES) == {"a": "Runbook"}


def test_prose_around_the_json_is_ignored():
    reply = 'Here is the classification:\n[{"id": "a", "type": "Note"}]\nLet me know if...'
    assert parse_classifications(reply, TYPES) == {"a": "Note"}


def test_a_type_that_does_not_exist_is_dropped():
    """A model inventing a plausible-sounding type must not invent it into
    the data."""
    reply = '[{"id": "a", "type": "Procedure"}, {"id": "b", "type": "Technical Manual"}]'
    assert parse_classifications(reply, TYPES) == {"a": "Procedure"}


def test_an_answer_with_no_json_yields_nothing_rather_than_raising():
    assert parse_classifications("I could not decide, sorry.", TYPES) == {}
    assert parse_classifications("", TYPES) == {}
    assert parse_classifications("<think>only thinking, no answer</think>", TYPES) == {}


def test_malformed_json_yields_nothing_rather_than_raising():
    assert parse_classifications('[{"id": "a", "type": ', TYPES) == {}


# --- proposing ----------------------------------------------------------

@pytest.fixture()
def workspace():
    workspace_id = f"sug-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace_id, token_hash=hash_token(raw)))
    ensure_document_types(db, workspace_id)
    db.add(LLMConfig(
        workspace_id=workspace_id, base_url="https://x/v1", model="test-model",
        enabled=True, last_check_ok=True, allow_confidential=False,
    ))
    db.commit()
    db.close()
    return workspace_id, raw


def auth(raw: str) -> dict:
    return {"Authorization": f"Bearer {raw}"}


def _document(db, workspace_id, title, confidentiality="interno", type_name="Note"):
    uid = f"d-{secrets.token_hex(4)}"
    db.add(Document(
        uid=uid, workspace_id=workspace_id, code=f"C-{uid}", title=title,
        document_type_uid=type_uid(workspace_id, type_name),
        confidentiality=confidentiality, source="confluence",
    ))
    return uid


def test_a_proposal_is_not_applied_to_the_document(workspace, monkeypatch):
    """The whole point: a suggestion is not a value until somebody makes
    it one."""
    workspace_id, raw = workspace
    db = SessionLocal()
    uid = _document(db, workspace_id, "Vacuum recovery after an interlock trip")
    db.commit()

    monkeypatch.setattr(
        "app.services.ai_suggestions.complete",
        lambda endpoint, system, user, max_tokens=0: f'[{{"id": "{uid}", "type": "Procedure"}}]',
    )
    config = db.get(LLMConfig, workspace_id)
    result = suggest_document_types(
        db, workspace_id, Endpoint(base_url="https://x/v1", model="test-model"), config
    )
    assert result["proposed"] == 1

    document = db.get(Document, uid)
    assert document.document_type_uid.endswith(":note"), "the document is untouched"
    suggestion = db.scalar(select(AISuggestion).where(AISuggestion.target_uid == uid))
    assert suggestion.suggested_label == "Procedure"
    assert suggestion.status == "proposed"
    assert suggestion.model == "test-model"
    db.close()


def test_accepting_is_what_changes_the_document(workspace, monkeypatch):
    workspace_id, raw = workspace
    db = SessionLocal()
    uid = _document(db, workspace_id, "Camera offline: first actions")
    db.commit()
    monkeypatch.setattr(
        "app.services.ai_suggestions.complete",
        lambda endpoint, system, user, max_tokens=0: f'[{{"id": "{uid}", "type": "Runbook"}}]',
    )
    config = db.get(LLMConfig, workspace_id)
    suggest_document_types(
        db, workspace_id, Endpoint(base_url="https://x/v1", model="test-model"), config
    )
    suggestion_id = db.scalar(select(AISuggestion.id).where(AISuggestion.target_uid == uid))
    db.close()

    resp = client.post(
        "/v1/ai/suggestions/accept", json={"ids": [suggestion_id]}, headers=auth(raw)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["applied"] == 1

    db = SessionLocal()
    assert db.get(Document, uid).document_type_uid.endswith(":runbook")
    assert db.get(AISuggestion, suggestion_id).status == "accepted"
    db.close()


def test_a_rejected_proposal_leaves_the_document_alone(workspace, monkeypatch):
    workspace_id, raw = workspace
    db = SessionLocal()
    uid = _document(db, workspace_id, "Something ambiguous")
    db.commit()
    monkeypatch.setattr(
        "app.services.ai_suggestions.complete",
        lambda endpoint, system, user, max_tokens=0: f'[{{"id": "{uid}", "type": "Specification"}}]',
    )
    config = db.get(LLMConfig, workspace_id)
    suggest_document_types(
        db, workspace_id, Endpoint(base_url="https://x/v1", model="test-model"), config
    )
    suggestion_id = db.scalar(select(AISuggestion.id).where(AISuggestion.target_uid == uid))
    db.close()

    client.post("/v1/ai/suggestions/reject", json={"ids": [suggestion_id]}, headers=auth(raw))
    db = SessionLocal()
    assert db.get(Document, uid).document_type_uid.endswith(":note")
    assert db.get(AISuggestion, suggestion_id).status == "rejected"
    db.close()


def test_confidential_documents_are_left_out_unless_allowed(workspace, monkeypatch):
    """Where their text goes is a decision somebody makes deliberately."""
    workspace_id, _raw = workspace
    db = SessionLocal()
    open_uid = _document(db, workspace_id, "An ordinary page")
    secret_uid = _document(db, workspace_id, "A restricted page", confidentiality="riservato")
    db.commit()

    seen: list[str] = []

    def fake(endpoint, system, user, max_tokens=0):
        seen.append(user)
        return "[]"

    monkeypatch.setattr("app.services.ai_suggestions.complete", fake)
    config = db.get(LLMConfig, workspace_id)
    suggest_document_types(
        db, workspace_id, Endpoint(base_url="https://x/v1", model="test-model"), config
    )
    prompt = "\n".join(seen)
    assert open_uid in prompt
    assert secret_uid not in prompt, "a riservato document must not be sent"
    db.close()


def test_a_failed_batch_is_counted_not_raised(workspace, monkeypatch):
    workspace_id, _raw = workspace
    db = SessionLocal()
    _document(db, workspace_id, "A page")
    db.commit()
    monkeypatch.setattr(
        "app.services.ai_suggestions.complete",
        lambda endpoint, system, user, max_tokens=0: "the model rambled and never answered",
    )
    config = db.get(LLMConfig, workspace_id)
    result = suggest_document_types(
        db, workspace_id, Endpoint(base_url="https://x/v1", model="test-model"), config
    )
    assert result["failed_batches"] == 1
    assert result["proposed"] == 0
    db.close()


def test_suggesting_is_refused_until_the_endpoint_checks_out(workspace):
    workspace_id, raw = workspace
    db = SessionLocal()
    db.get(LLMConfig, workspace_id).last_check_ok = False
    db.commit()
    db.close()

    resp = client.post("/v1/ai/suggest/document-types", json={}, headers=auth(raw))
    assert resp.status_code == 409


def test_a_document_already_proposed_is_not_asked_about_again(workspace, monkeypatch):
    """A proposal does not change the document, so without this a caller
    working through a backlog would be handed the same page for ever."""
    workspace_id, _raw = workspace
    db = SessionLocal()
    uid = _document(db, workspace_id, "A page needing a type")
    db.commit()

    calls: list[str] = []

    def fake(endpoint, system, user, max_tokens=0):
        calls.append(user)
        return f'[{{"id": "{uid}", "type": "Procedure"}}]'

    monkeypatch.setattr("app.services.ai_suggestions.complete", fake)
    config = db.get(LLMConfig, workspace_id)
    endpoint = Endpoint(base_url="https://x/v1", model="test-model")

    first = suggest_document_types(db, workspace_id, endpoint, config)
    assert first["proposed"] == 1

    second = suggest_document_types(db, workspace_id, endpoint, config)
    assert second["considered"] == 0, "nothing left to ask about"
    assert len(calls) == 1, "and no second request was made"
    db.close()
