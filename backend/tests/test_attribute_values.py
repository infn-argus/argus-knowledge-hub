"""The vocabulary an indexed attribute offers.

The point of the feature is that the same term gets reused instead of
re-typed, so what matters is that every value already in the workspace
comes back — whichever shape it was stored in — and that nothing stale
does.
"""
import secrets
import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.asset import Asset
from app.models.document import Document, DocumentRevision
from app.models.issue import Issue
from app.models.schema import Schema
from app.models.workspace import Workspace

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def workspace():
    db = SessionLocal()
    workspace_id = f"av-{secrets.token_hex(4)}"
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace_id, token_hash=hash_token(raw)))
    db.commit()
    db.close()
    return workspace_id, raw


def auth(raw_token: str) -> dict:
    return {"Authorization": f"Bearer {raw_token}"}


def values(raw_token: str, applies_to: str, key: str, **params) -> list[str]:
    resp = client.get(
        "/v1/attribute-values",
        params={"applies_to": applies_to, "key": key, **params},
        headers=auth(raw_token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_single_and_multi_value_shapes_are_both_read(workspace):
    """One attribute's definition can go from single to multi, and the older
    records keep the shape they were written in. Reading only one shape
    would hide half the vocabulary."""
    workspace_id, token = workspace
    db = SessionLocal()
    db.add(Issue(uid=f"i1-{workspace_id}", workspace_id=workspace_id, title="A",
                 state="new", attributes={"argus_components": "Vacuum"}))
    db.add(Issue(uid=f"i2-{workspace_id}", workspace_id=workspace_id, title="B",
                 state="new", attributes={"argus_components": ["Diagnostics", "RF"]}))
    db.commit()
    db.close()

    assert values(token, "tickets", "argus_components") == ["Diagnostics", "RF", "Vacuum"]


def test_the_same_term_is_offered_once(workspace):
    workspace_id, token = workspace
    db = SessionLocal()
    for i in range(3):
        db.add(Issue(uid=f"dup{i}-{workspace_id}", workspace_id=workspace_id, title="X",
                     state="new", attributes={"argus_system": "Vacuum"}))
    db.commit()
    db.close()

    assert values(token, "tickets", "argus_system") == ["Vacuum"]


def test_typing_narrows_the_list(workspace):
    workspace_id, token = workspace
    db = SessionLocal()
    db.add(Issue(uid=f"q1-{workspace_id}", workspace_id=workspace_id, title="A", state="new",
                 attributes={"argus_components": ["Vacuum", "Diagnostics", "Cryogenics"]}))
    db.commit()
    db.close()

    # Matching is case-insensitive: someone typing "vac" is looking for
    # "Vacuum", and making them match the capitalisation defeats the point.
    assert values(token, "tickets", "argus_components", q="vac") == ["Vacuum"]
    assert values(token, "tickets", "argus_components", q="cry") == ["Cryogenics"]


def test_blank_and_missing_values_are_not_offered(workspace):
    """An empty string is not a term. Offering one puts a blank row in the
    suggestion list that silently sets the field to nothing."""
    workspace_id, token = workspace
    db = SessionLocal()
    db.add(Issue(uid=f"b1-{workspace_id}", workspace_id=workspace_id, title="A", state="new",
                 attributes={"argus_system": "   "}))
    db.add(Issue(uid=f"b2-{workspace_id}", workspace_id=workspace_id, title="B", state="new",
                 attributes={"argus_system": ""}))
    db.add(Issue(uid=f"b3-{workspace_id}", workspace_id=workspace_id, title="C", state="new",
                 attributes={}))
    db.add(Issue(uid=f"b4-{workspace_id}", workspace_id=workspace_id, title="D", state="new",
                 attributes={"argus_system": "Vacuum"}))
    db.commit()
    db.close()

    assert values(token, "tickets", "argus_system") == ["Vacuum"]


def test_documents_read_the_current_revision_only(workspace):
    """A term dropped three revisions ago is not part of the vocabulary any
    more — offering it would resurrect words nobody uses."""
    workspace_id, token = workspace
    db = SessionLocal()
    document = Document(uid=f"d-{workspace_id}", workspace_id=workspace_id,
                        code=f"DOC-{workspace_id}", title="Procedure")
    db.add(document)
    db.flush()
    old = DocumentRevision(uid=str(uuid.uuid4()), document_uid=document.uid,
                           revision_number=1, state="superseded",
                           attributes={"argus_keywords": ["obsolete-term"]})
    new = DocumentRevision(uid=str(uuid.uuid4()), document_uid=document.uid,
                           revision_number=2, state="published",
                           attributes={"argus_keywords": ["vacuum", "interlock"]})
    db.add_all([old, new])
    db.flush()
    document.current_revision_uid = new.uid
    db.commit()
    db.close()

    assert values(token, "documents", "argus_keywords") == ["interlock", "vacuum"]


def test_another_workspaces_vocabulary_is_not_offered(workspace):
    workspace_id, token = workspace
    other = f"other-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=other, name="Other"))
    db.flush()
    db.add(Issue(uid=f"o1-{other}", workspace_id=other, title="A", state="new",
                 attributes={"argus_system": "SomebodyElsesSystem"}))
    db.add(Issue(uid=f"m1-{workspace_id}", workspace_id=workspace_id, title="B", state="new",
                 attributes={"argus_system": "Vacuum"}))
    db.commit()
    db.close()

    assert values(token, "tickets", "argus_system") == ["Vacuum"]


def test_objects_have_a_vocabulary_too(workspace):
    workspace_id, token = workspace
    db = SessionLocal()
    db.add(Schema(uid=f"sc-{workspace_id}", workspace_id=workspace_id, name="Cameras"))
    db.flush()
    db.add(Asset(uid=f"a1-{workspace_id}", workspace_id=workspace_id,
                 schema_uid=f"sc-{workspace_id}", key=f"K-{workspace_id}", name="Cam",
                 type="Cameras", attributes={"manufacturer": "Basler"}))
    db.commit()
    db.close()

    assert values(token, "objects", "manufacturer") == ["Basler"]


def test_an_attribute_nobody_has_filled_in_returns_nothing(workspace):
    _workspace_id, token = workspace
    assert values(token, "tickets", "argus_nothing_here") == []
