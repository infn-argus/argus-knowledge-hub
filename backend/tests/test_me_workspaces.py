"""Coverage for GET /v1/me/workspaces — the call the web app makes right
after sign-in to list the workspaces you can enter.

It builds MyWorkspaceOut by hand in four separate branches (PAT, admin,
explicit membership, workspace default access), so any field added to
WorkspaceOut/MyWorkspaceOut has to be wired into all four. Missing one
breaks sign-in outright, which is exactly what happened when `is_global`
was introduced — hence a test per branch.
"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import OidcIdentity, PatIdentity, get_identity
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.membership import Membership
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import MyWorkspaceOut

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def world():
    """Three workspaces and two users: a plain member and an admin."""
    suffix = secrets.token_hex(4)
    ids = {
        "member_ws": f"member-{suffix}",
        "default_ws": f"default-{suffix}",
        "other_ws": f"other-{suffix}",
        "user": f"user-{suffix}",
        "admin": f"admin-{suffix}",
    }
    db = SessionLocal()
    db.add(Workspace(id=ids["member_ws"], name="Member WS", is_global=True))
    # No membership here, but default access is open to any authenticated user.
    db.add(Workspace(id=ids["default_ws"], name="Default WS", default_can_read=True))
    # Neither a membership nor default access — must stay invisible to the user.
    db.add(Workspace(id=ids["other_ws"], name="Other WS"))
    db.add(User(id=ids["user"], email=f"{ids['user']}@test.local", name="Member"))
    db.add(User(id=ids["admin"], email=f"{ids['admin']}@test.local", name="Admin", is_admin=True))
    db.flush()
    db.add(Membership(
        workspace_id=ids["member_ws"], user_id=ids["user"],
        can_read=True, can_create=True, can_modify=False, can_delete=False,
    ))
    db.commit()
    db.close()
    yield ids
    app.dependency_overrides.pop(get_identity, None)


def as_identity(identity):
    app.dependency_overrides[get_identity] = lambda: identity


def fetch_workspaces():
    resp = client.get("/v1/me/workspaces")
    assert resp.status_code == 200, resp.text
    return {w["id"]: w for w in resp.json()}


def assert_fully_populated(workspace: dict):
    """Every field the schema declares must come back — a field added to
    WorkspaceOut but forgotten in one of the hand-built branches would
    otherwise only surface as a 500 in production."""
    assert set(workspace) == set(MyWorkspaceOut.model_fields), (
        f"missing/extra fields: {set(MyWorkspaceOut.model_fields) ^ set(workspace)}"
    )


def test_pat_sees_only_its_own_workspace(world):
    as_identity(PatIdentity(workspace_id=world["member_ws"]))
    found = fetch_workspaces()

    assert set(found) == {world["member_ws"]}
    ws = found[world["member_ws"]]
    assert_fully_populated(ws)
    assert ws["is_global"] is True
    # A PAT is unscoped by design: full rights on its own workspace.
    assert ws["can_read"] and ws["can_create"] and ws["can_modify"] and ws["can_delete"]


def test_admin_sees_every_workspace(world):
    db = SessionLocal()
    admin = db.get(User, world["admin"])
    as_identity(OidcIdentity(user=admin))
    found = fetch_workspaces()
    db.close()

    assert {world["member_ws"], world["default_ws"], world["other_ws"]} <= set(found)
    assert_fully_populated(found[world["member_ws"]])
    assert found[world["member_ws"]]["is_global"] is True
    assert found[world["other_ws"]]["is_global"] is False


def test_member_sees_membership_and_default_access_workspaces(world):
    db = SessionLocal()
    user = db.get(User, world["user"])
    as_identity(OidcIdentity(user=user))
    found = fetch_workspaces()
    db.close()

    # Membership branch: flags come from the membership row.
    assert world["member_ws"] in found
    member_ws = found[world["member_ws"]]
    assert_fully_populated(member_ws)
    assert member_ws["is_global"] is True
    assert member_ws["can_read"] and member_ws["can_create"]
    assert not member_ws["can_modify"] and not member_ws["can_delete"]

    # Default-access branch: no membership, flags come from the workspace.
    assert world["default_ws"] in found
    default_ws = found[world["default_ws"]]
    assert_fully_populated(default_ws)
    assert default_ws["is_global"] is False
    assert default_ws["can_read"] and not default_ws["can_create"]

    # Neither membership nor default access.
    assert world["other_ws"] not in found
