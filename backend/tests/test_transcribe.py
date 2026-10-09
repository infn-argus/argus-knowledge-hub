"""A recording, as text: the workspace's speech-to-text model through the OpenAI-compatible endpoint."""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.llm_config import LLMConfig
from app.models.workspace import Workspace
from app.services import llm
from tests.test_ledger_transition import token

client = TestClient(app)


@pytest.fixture()
def ws():
    w = f"asr-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=w, name=w))
    db.flush()
    db.add(LLMConfig(workspace_id=w, base_url="https://gw.example/v1", model="chat", asr_model="whisper-large",
                     enabled=True, last_check_ok=True))
    headers = token(db, w)
    db.commit()
    db.close()
    yield w, headers
    db = SessionLocal()
    from app.ledger.audit import allow_purge
    allow_purge(db)
    db.delete(db.get(Workspace, w))
    db.commit()
    db.close()


class _Reply:
    status_code = 200
    text = ""

    def json(self):
        return {"text": " Close the gate valve, then vent sector 3. "}


def test_a_recording_is_transcribed_by_the_workspace_model(ws, monkeypatch):
    w, h = ws
    sent = {}

    def fake_post(url, headers=None, data=None, files=None, timeout=None, **_):
        sent.update(url=url, data=data, files=files, headers=headers)
        return _Reply()
    monkeypatch.setattr(llm.requests, "post", fake_post)
    r = client.post("/v1/ai/transcribe", headers=h, params={"language": "it"},
                    files={"file": ("note.m4a", b"\x00\x00\x00\x18ftypM4A ", "audio/mp4")})
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "Close the gate valve, then vent sector 3."}
    assert sent["url"] == "https://gw.example/v1/audio/transcriptions"
    assert sent["data"] == {"model": "whisper-large", "response_format": "json", "language": "it"}
    assert sent["files"]["file"][0] == "note.m4a" and "Content-Type" not in sent["headers"]


def test_without_a_speech_model_it_says_so(ws):
    w, h = ws
    db = SessionLocal()
    db.get(LLMConfig, w).asr_model = None
    db.commit()
    db.close()
    r = client.post("/v1/ai/transcribe", headers=h, files={"file": ("note.m4a", b"x", "audio/mp4")})
    assert r.status_code == 409 and "speech-to-text" in r.text
