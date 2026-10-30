"""A link to a document opened in another of the reader's workspaces says where the document lives."""
import secrets
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth import OidcIdentity, get_identity
from app.db import SessionLocal
from app.main import app
from app.models.role import Role, RoleBinding
from app.models.user import User
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)


def test_a_document_link_names_its_workspace_only_to_who_may_read_documents_there():
    sparc, own = f"links-{secrets.token_hex(3)}", f"links-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add_all([Workspace(id=sparc, name="SPARC"), Workspace(id=own, name="Andrea's own")])
    reader = User(id=f"reader-{sparc}", email=f"reader@{sparc}.example", name="Reader")
    stranger = User(id=f"stranger-{sparc}", email=f"stranger@{sparc}.example", name="Stranger")
    db.add_all([reader, stranger])
    db.flush()
    role = Role(id=f"{sparc}-reader", name="Reader", permissions={"documents": ["read"]})
    db.add(role)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(RoleBinding(workspace_id=sparc, subject_type="user", subject_id=reader.id, role_id=role.id, created_at=now))
    db.add(RoleBinding(workspace_id=own, subject_type="user", subject_id=stranger.id, role_id=role.id, created_at=now))
    sparc_headers, own_headers = token(db, sparc), token(db, own)
    db.commit()
    uid = str(uuid.uuid4())
    assert client.post("/v1/documents", headers=sparc_headers,
                       json={"uid": uid, "title": "Libera boards"}).status_code == 201

    try:
        app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=reader)
        r = client.get(f"/v1/documents/{uid}/workspace", headers={"X-Workspace-Id": own})
        assert r.status_code == 200 and r.json() == {"workspace_id": sparc, "name": "SPARC"}
        assert client.get(f"/v1/documents/{uuid.uuid4()}/workspace").status_code == 404

        # Someone who may not read SPARC's documents learns nothing, not even that it exists.
        app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=stranger)
        hidden, missing = (client.get(f"/v1/documents/{u}/workspace") for u in (uid, uuid.uuid4()))
        assert hidden.status_code == 404 and hidden.json() == missing.json()
    finally:
        app.dependency_overrides.pop(get_identity, None)
        db.close()

    # A workspace's token is bound to its workspace.
    assert client.get(f"/v1/documents/{uid}/workspace", headers=own_headers).status_code == 404
    assert client.get(f"/v1/documents/{uid}/workspace", headers=sparc_headers).json()["name"] == "SPARC"
