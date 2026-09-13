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


def _asset(db, workspace_id, suffix):
    from app.models.asset import Asset
    from app.models.schema import Schema

    db.add(Schema(uid=f"sc-{suffix}", workspace_id=workspace_id, name="Cameras"))
    db.flush()
    db.add(Asset(uid=f"as-{suffix}", workspace_id=workspace_id, schema_uid=f"sc-{suffix}",
                 key=f"LNFT2-{suffix}", name="FI4-B-CAM-VIS-001", type="Cameras"))
    db.commit()
    return f"as-{suffix}"


def test_a_ticket_links_to_objects_and_documents(token):
    """What a ticket is about lives in link tables, not attributes, so the
    graph can be walked from the object or the document too."""
    from app.models.document import Document

    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)

    db = SessionLocal()
    workspace_id = db.scalar(
        select(ApiToken.workspace_id).where(ApiToken.token_hash == hash_token(token))
    )
    asset_uid = _asset(db, workspace_id, suffix)
    db.add(Document(uid=f"doc-{suffix}", workspace_id=workspace_id,
                    code=f"PROC-{suffix}", title="Camera replacement procedure"))
    db.commit()
    db.close()

    linked = client.post(
        f"/v1/issues/{uid}/links/assets",
        json={"asset_uid": asset_uid, "relation": "affects"},
        headers=auth(token),
    )
    assert linked.status_code == 201, linked.text

    doc_linked = client.post(
        f"/v1/issues/{uid}/links/documents",
        json={"document_uid": f"doc-{suffix}", "relation": "procedure"},
        headers=auth(token),
    )
    assert doc_linked.status_code == 201, doc_linked.text

    links = client.get(f"/v1/issues/{uid}/links", headers=auth(token)).json()
    assert [a["name"] for a in links["assets"]] == ["FI4-B-CAM-VIS-001"]
    assert links["assets"][0]["relation"] == "affects"
    assert [d["code"] for d in links["documents"]] == [f"PROC-{suffix}"]
    assert links["documents"][0]["relation"] == "procedure"

    # Linking is a change worth seeing in the timeline.
    entries = client.get(f"/v1/issues/{uid}/history", headers=auth(token)).json()
    assert any(e["field"] == "Linked object" for e in entries)
    assert any(e["field"] == "Linked document" for e in entries)

    # Linking the same thing twice is a conflict, not a duplicate row.
    again = client.post(
        f"/v1/issues/{uid}/links/assets",
        json={"asset_uid": asset_uid},
        headers=auth(token),
    )
    assert again.status_code == 409

    relation_id = links["documents"][0]["relation_id"]
    assert client.delete(
        f"/v1/issues/{uid}/links/documents/{relation_id}", headers=auth(token)
    ).status_code == 204
    assert client.delete(
        f"/v1/issues/{uid}/links/assets/{asset_uid}", headers=auth(token)
    ).status_code == 204

    links = client.get(f"/v1/issues/{uid}/links", headers=auth(token)).json()
    assert links["assets"] == [] and links["documents"] == []


def test_legacy_ticket_attributes_map_onto_argus_keys():
    """The mapping the migration and the importer share."""
    from app.services.ticket_types import migrate_legacy_attributes

    migrated = migrate_legacy_attributes({
        "jiraKey": "LNFDCS-563",
        "jira_status": "To Do",
        "jira_components": ["Olog"],
        "local_note": "keep me",
    })
    assert migrated["argus_source_key"] == "LNFDCS-563"
    assert migrated["argus_source_status"] == "To Do"
    assert migrated["argus_components"] == ["Olog"]
    assert migrated["local_note"] == "keep me"
    assert not any(k.startswith("jira") for k in migrated)

    # Running it twice must not undo the first pass.
    assert migrate_legacy_attributes(migrated) == migrated

    # A value already under the ARGUS key wins over the legacy one.
    both = migrate_legacy_attributes({"jiraKey": "OLD", "argus_source_key": "NEW"})
    assert both["argus_source_key"] == "NEW"


def test_tickets_link_to_each_other_and_read_from_both_ends(token):
    """An epic and its story are one row. Opening either has to show it,
    which is the whole reason it isn't an attribute holding a key."""
    suffix = secrets.token_hex(4)
    epic = _ticket(token, f"epic-{suffix}")
    story = _ticket(token, f"story-{suffix}")

    created = client.post(
        f"/v1/issues/{story}/links/tickets",
        json={"issue_uid": epic, "relation": "epic"},
        headers=auth(token),
    )
    assert created.status_code == 201, created.text
    assert created.json()["outgoing"] is True

    from_story = client.get(f"/v1/issues/{story}/links", headers=auth(token)).json()["tickets"]
    assert [(t["issue_uid"], t["relation"], t["outgoing"]) for t in from_story] == [
        (epic, "epic", True)
    ]

    # The same edge, seen from the epic, points the other way.
    from_epic = client.get(f"/v1/issues/{epic}/links", headers=auth(token)).json()["tickets"]
    assert [(t["issue_uid"], t["relation"], t["outgoing"]) for t in from_epic] == [
        (story, "epic", False)
    ]

    assert client.post(
        f"/v1/issues/{story}/links/tickets",
        json={"issue_uid": epic, "relation": "epic"},
        headers=auth(token),
    ).status_code == 409

    assert client.post(
        f"/v1/issues/{story}/links/tickets",
        json={"issue_uid": story},
        headers=auth(token),
    ).status_code == 422, "a ticket can't link to itself"

    # Either end may remove it — it is one relationship, not two.
    link_id = from_epic[0]["link_id"]
    assert client.delete(
        f"/v1/issues/{epic}/links/tickets/{link_id}", headers=auth(token)
    ).status_code == 204
    assert client.get(f"/v1/issues/{story}/links", headers=auth(token)).json()["tickets"] == []


def test_labels_in_use_are_offered_back(token):
    """So that typing a label reuses the one that exists rather than
    creating "btf" beside "BTF"."""
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)
    client.put(
        f"/v1/issues/{uid}", json={"labels": ["BTF", f"vacuum-{suffix}"]}, headers=auth(token)
    )

    labels = client.get("/v1/issues/labels", headers=auth(token)).json()
    assert "BTF" in labels and f"vacuum-{suffix}" in labels
    # Sorted and distinct, so the list is usable as a vocabulary.
    assert labels == sorted(set(labels))


def test_labels_are_not_shared_between_workspaces(token):
    suffix = secrets.token_hex(4)
    uid = _ticket(token, suffix)
    client.put(f"/v1/issues/{uid}", json={"labels": [f"secret-{suffix}"]}, headers=auth(token))

    db = SessionLocal()
    other_ws = f"other-{suffix}"
    db.add(Workspace(id=other_ws, name="Other"))
    db.flush()
    other_raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=other_ws, token_hash=hash_token(other_raw)))
    db.commit()
    db.close()

    assert f"secret-{suffix}" not in client.get(
        "/v1/issues/labels", headers=auth(other_raw)
    ).json()
