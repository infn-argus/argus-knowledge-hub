"""Bulk delete for assets, documents and issues — the /bulk-delete endpoints
backing the multi-select "Delete" action on each list page."""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import OidcIdentity, get_identity
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.asset import Asset
from app.models.document import Document
from app.models.issue import Issue
from app.models.membership import Membership
from app.models.schema import Schema
from app.models.user import User
from app.models.workspace import Workspace

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def as_identity(identity):
    app.dependency_overrides[get_identity] = lambda: identity


@pytest.fixture()
def world():
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    user_id = f"u-{suffix}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.add(User(id=user_id, email=f"{user_id}@test.invalid"))
    db.flush()
    db.add(Membership(workspace_id=ws, user_id=user_id, can_read=True, can_create=True, can_modify=True,
                       can_delete=True, can_read_documents=True, can_create_documents=True,
                       can_modify_documents=True, can_delete_documents=True, can_read_tickets=True,
                       can_create_tickets=True, can_modify_tickets=True, can_delete_tickets=True))
    db.commit()
    db.close()
    yield {"ws": ws, "user_id": user_id, "suffix": suffix}
    app.dependency_overrides.pop(get_identity, None)


def _login(user_id: str):
    db = SessionLocal()
    user = db.get(User, user_id)
    as_identity(OidcIdentity(user=user))
    return db


def test_bulk_delete_assets(world):
    suffix = world["suffix"]
    setup = SessionLocal()
    setup.add(Schema(uid=f"sch-{suffix}", workspace_id=world["ws"], name="Camera"))
    setup.flush()
    keep_uid, gone1_uid, gone2_uid = f"keep-{suffix}", f"gone1-{suffix}", f"gone2-{suffix}"
    setup.add(Asset(uid=keep_uid, workspace_id=world["ws"], schema_uid=f"sch-{suffix}", key=f"K-{suffix}", name="Keep", type="Camera"))
    setup.add(Asset(uid=gone1_uid, workspace_id=world["ws"], schema_uid=f"sch-{suffix}", key=f"G1-{suffix}", name="Gone1", type="Camera"))
    setup.add(Asset(uid=gone2_uid, workspace_id=world["ws"], schema_uid=f"sch-{suffix}", key=f"G2-{suffix}", name="Gone2", type="Camera"))
    setup.commit()
    setup.close()

    db = _login(world["user_id"])
    resp = client.post(
        "/v1/assets/bulk-delete",
        json={"uids": [gone1_uid, gone2_uid, "does-not-exist"]},
        headers={"X-Workspace-Id": world["ws"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["deleted"] == 2
    assert body["not_found"] == ["does-not-exist"]
    assert db.get(Asset, keep_uid) is not None
    assert db.get(Asset, gone1_uid) is None
    assert db.get(Asset, gone2_uid) is None
    db.close()


def test_bulk_delete_documents(world):
    suffix = world["suffix"]
    setup = SessionLocal()
    keep_uid, gone_uid = f"keep-{suffix}", f"gone-{suffix}"
    setup.add(Document(uid=keep_uid, workspace_id=world["ws"], code=f"DOC-KEEP-{suffix}", title="Keep"))
    setup.add(Document(uid=gone_uid, workspace_id=world["ws"], code=f"DOC-GONE-{suffix}", title="Gone"))
    setup.commit()
    setup.close()

    db = _login(world["user_id"])
    resp = client.post(
        "/v1/documents/bulk-delete",
        json={"uids": [gone_uid]},
        headers={"X-Workspace-Id": world["ws"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"deleted": 1, "not_found": []}
    assert db.get(Document, keep_uid) is not None
    assert db.get(Document, gone_uid) is None
    db.close()


def test_bulk_delete_issues(world):
    suffix = world["suffix"]
    setup = SessionLocal()
    keep_uid, gone_uid = f"keep-{suffix}", f"gone-{suffix}"
    setup.add(Issue(uid=keep_uid, workspace_id=world["ws"], title="Keep"))
    setup.add(Issue(uid=gone_uid, workspace_id=world["ws"], title="Gone"))
    setup.commit()
    setup.close()

    db = _login(world["user_id"])
    resp = client.post(
        "/v1/issues/bulk-delete",
        json={"uids": [gone_uid]},
        headers={"X-Workspace-Id": world["ws"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"deleted": 1, "not_found": []}
    assert db.get(Issue, keep_uid) is not None
    assert db.get(Issue, gone_uid) is None
    db.close()


def test_bulk_delete_skips_items_outside_the_workspace(world):
    suffix = world["suffix"]
    setup = SessionLocal()
    other_ws = f"other-{suffix}"
    setup.add(Workspace(id=other_ws, name="Other"))
    setup.flush()
    foreign_uid = f"foreign-{suffix}"
    setup.add(Issue(uid=foreign_uid, workspace_id=other_ws, title="Not yours"))
    setup.commit()
    setup.close()

    db = _login(world["user_id"])
    resp = client.post(
        "/v1/issues/bulk-delete",
        json={"uids": [foreign_uid]},
        headers={"X-Workspace-Id": world["ws"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"deleted": 0, "not_found": [foreign_uid]}
    assert db.get(Issue, foreign_uid) is not None
    db.close()
