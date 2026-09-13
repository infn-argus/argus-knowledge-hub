"""Ticket history and ticket-owned attachments.

A ticket previously had neither: attachments hung off assets only, so a
screenshot of a fault had to be filed against whatever object the ticket
mentioned, and nothing recorded what had changed.
"""
import secrets

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.models.api_token import ApiToken
from app.models.issue import IssueHistory
from app.models.workspace import Workspace
from app.main import app

client = TestClient(app)

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def token(tmp_path_factory, monkeypatch):
    monkeypatch.setattr("app.routers.issues.ATTACHMENTS_DIR",
                        str(tmp_path_factory.mktemp("attachments")))
    db = SessionLocal()
    workspace_id = f"test-{secrets.token_hex(4)}"
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace_id, token_hash=hash_token(raw)))
    db.commit()
    db.close()
    return raw


def auth(raw: str) -> dict:
    return {"Authorization": f"Bearer {raw}"}


def _ticket(token: str, suffix: str) -> str:
    resp = client.post(
        "/v1/issues",
        json={"uid": f"tk-{suffix}", "title": "Camera offline", "attributes": {}},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return f"tk-{suffix}"


def test_creating_and_changing_a_ticket_is_recorded(token):
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)

    entries = client.get(f"/v1/issues/{uid}/history", headers=auth(token)).json()
    assert [e["type"] for e in entries] == ["created"]

    client.put(
        f"/v1/issues/{uid}",
        json={"state": "in_progress", "priority": "high"},
        headers=auth(token),
    )
    entries = client.get(f"/v1/issues/{uid}/history", headers=auth(token)).json()
    changed = {e["field"]: (e["from_value"], e["to_value"]) for e in entries if e["field"]}
    assert changed["Status"] == ("new", "in_progress")
    assert changed["Priority"] == (None, "high")
    # Newest first, so the timeline reads the way a person scans it.
    assert entries[0]["timestamp"] >= entries[-1]["timestamp"]


def test_an_unchanged_field_is_not_recorded(token):
    """Saving a form re-sends every field; recording all of them would bury
    the one thing that actually changed."""
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)
    client.put(f"/v1/issues/{uid}", json={"state": "in_progress"}, headers=auth(token))
    before = len(client.get(f"/v1/issues/{uid}/history", headers=auth(token)).json())

    client.put(
        f"/v1/issues/{uid}",
        json={"state": "in_progress", "title": "Camera offline"},
        headers=auth(token),
    )
    after = client.get(f"/v1/issues/{uid}/history", headers=auth(token)).json()
    assert len(after) == before


def test_a_ticket_owns_its_attachments(token):
    """A screenshot of a fault belongs to the ticket, not to whatever object
    the ticket happens to mention."""
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)

    resp = client.post(
        f"/v1/issues/{uid}/attachments",
        files={"file": ("screenshot.png", PNG, "image/png")},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["filename"] == "screenshot.png"

    listed = client.get(f"/v1/issues/{uid}/attachments", headers=auth(token)).json()
    assert [a["filename"] for a in listed] == ["screenshot.png"]

    # Uploading a file is a change worth seeing in the timeline.
    entries = client.get(f"/v1/issues/{uid}/history", headers=auth(token)).json()
    assert any(e["field"] == "Attachment" and e["to_value"] == "screenshot.png" for e in entries)


def test_history_and_attachments_go_with_a_deleted_ticket(token):
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)
    client.post(
        f"/v1/issues/{uid}/attachments",
        files={"file": ("s.png", PNG, "image/png")},
        headers=auth(token),
    )
    assert client.delete(f"/v1/issues/{uid}", headers=auth(token)).status_code == 204

    db = SessionLocal()
    assert db.scalars(
        select(IssueHistory).where(IssueHistory.issue_uid == uid)
    ).all() == []
    db.close()


def test_history_of_another_workspaces_ticket_is_not_readable(token):
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)

    db = SessionLocal()
    other_ws = f"other-{suffix}"
    db.add(Workspace(id=other_ws, name="Other"))
    db.flush()
    other_raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=other_ws, token_hash=hash_token(other_raw)))
    db.commit()
    db.close()

    assert client.get(f"/v1/issues/{uid}/history", headers=auth(other_raw)).status_code == 404
    assert client.get(f"/v1/issues/{uid}/attachments", headers=auth(other_raw)).status_code == 404
