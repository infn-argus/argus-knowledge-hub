"""Personal access tokens, robot tokens, and the caller's profile."""
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import OidcIdentity, get_identity, hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.group import Group, GroupMember
from app.models.role import RoleBinding
from app.models.user import User
from app.models.workspace import Workspace
from app.services.roles import ensure_system_roles

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    ensure_system_roles(db)
    db.commit()
    db.close()
    yield


@pytest.fixture()
def world():
    """A facility workspace, a viewer reached through a group, an owner, and an administrator."""
    t = secrets.token_hex(4)
    db = SessionLocal()
    ws, other = f"tok-{t}", f"tok-other-{t}"
    db.add_all([Workspace(id=ws, name="Facility"), Workspace(id=other, name="Other")])
    viewer = User(id=f"v-{t}", email=f"viewer-{t}@argus.test", name="Vera Viewer")
    owner = User(id=f"o-{t}", email=f"owner-{t}@argus.test", name="Otto Owner")
    admin = User(id=f"a-{t}", email=f"admin-{t}@argus.test", name="Ada Admin", is_admin=True)
    db.add_all([viewer, owner, admin, Group(uid=f"g-{t}", name="Operators", source="local")])
    db.flush()
    db.add(GroupMember(group_uid=f"g-{t}", user_id=viewer.id))
    now = datetime.now(timezone.utc)
    db.add(RoleBinding(workspace_id=ws, subject_type="group", subject_id=f"g-{t}", role_id="viewer", created_at=now))
    db.add(RoleBinding(workspace_id=ws, subject_type="user", subject_id=owner.id, role_id="owner", created_at=now))
    db.commit()
    out = {"ws": ws, "other": other, "viewer": viewer.id, "owner": owner.id, "admin": admin.id}
    db.close()
    yield out
    app.dependency_overrides.pop(get_identity, None)


def signed_in(user_id: str):
    """Act as this person, signed in (a token cannot make tokens)."""
    def identity():
        db = SessionLocal()
        user = db.get(User, user_id)
        db.expunge(user)
        db.close()
        return OidcIdentity(user=user, claims={"iss": "https://keycloak/realms/argus", "sub": user_id,
                                               "auth_time": 1, "realm_access": {"roles": ["argus-user"]}})
    app.dependency_overrides[get_identity] = identity


def as_token():
    app.dependency_overrides.pop(get_identity, None)


def bearer(raw: str, ws: str = None) -> dict:
    return {"Authorization": f"Bearer {raw}", **({"X-Workspace-Id": ws} if ws else {})}


def test_a_robot_uploads_a_daily_logbook_and_can_do_nothing_else(world):
    signed_in(world["owner"])
    made = client.post(f"/v1/workspaces/{world['ws']}/robot-tokens", json={
        "name": "Logbook uploader — SPARC", "scopes": ["read", "create", "modify"], "resources": ["documents"],
        "expires_in_days": 365})
    assert made.status_code == 201, made.text
    raw = made.json()["token"]
    assert raw.startswith("argus_bot_") and made.json()["prefix"] == raw[:14]
    listed = client.get(f"/v1/workspaces/{world['ws']}/robot-tokens").json()
    assert [t["name"] for t in listed] == ["Logbook uploader — SPARC"] and "token" not in listed[0]
    as_token()
    entry = client.post("/v1/documents", headers=bearer(raw), json={
        "uid": f"log-{secrets.token_hex(3)}", "title": "Logbook 2026-10-05", "body_markdown": "Beam on at 08:12."})
    assert entry.status_code == 201, entry.text
    assert client.get(f"/v1/documents/{entry.json()['uid']}", headers=bearer(raw)).status_code == 200
    uid = entry.json()["uid"]
    attached = client.post(f"/v1/documents/{uid}/revisions/{uid}-r1/attachments", headers=bearer(raw),
                           files={"file": ("logbook-2026-10-05.txt", b"08:12 beam on\n09:40 RF trip", "text/plain")})
    assert attached.status_code == 201, attached.text
    # Nothing outside what it was made for.
    assert client.post("/v1/schemas", headers=bearer(raw), json={"uid": f"s-{secrets.token_hex(3)}",
                                                                 "name": "x"}).status_code == 403
    assert client.delete(f"/v1/documents/{entry.json()['uid']}", headers=bearer(raw)).status_code == 403
    assert client.get(f"/v1/workspaces/{world['ws']}/robot-tokens", headers=bearer(raw)).status_code == 403
    # Its writes are attributed to it by name.
    db = SessionLocal()
    assert db.scalar(__import__("sqlalchemy").select(ApiToken.last_used_at).where(
        ApiToken.token_hash == hash_token(raw))) is not None
    db.close()


def test_only_a_workspace_owner_makes_robot_tokens(world):
    signed_in(world["viewer"])
    assert client.post(f"/v1/workspaces/{world['ws']}/robot-tokens",
                       json={"name": "x", "scopes": ["read"]}).status_code == 403
    signed_in(world["admin"])
    assert client.post(f"/v1/workspaces/{world['ws']}/robot-tokens",
                       json={"name": "x", "scopes": ["read"], "expires_in_days": None}).status_code == 201


def test_a_personal_token_never_exceeds_its_owner(world):
    signed_in(world["viewer"])
    made = client.post("/v1/me/tokens", json={"name": "my scripts", "scopes": ["read", "create"],
                                              "expires_in_days": 30})
    assert made.status_code == 201, made.text
    raw = made.json()["token"]
    assert raw.startswith("argus_pat_")
    assert client.post("/v1/me/tokens", json={"name": "forever", "scopes": ["read"],
                                              "expires_in_days": None}).status_code == 422
    assert client.post("/v1/me/tokens", json={"name": "too long", "scopes": ["read"],
                                              "expires_in_days": 400}).status_code == 422
    assert client.post("/v1/me/tokens", json={"name": "admin", "scopes": ["admin"]}).status_code == 422
    as_token()
    assert client.get("/v1/documents", headers=bearer(raw, world["ws"])).status_code == 200
    # The viewer may not create, whatever the token's scopes say.
    assert client.post("/v1/documents", headers=bearer(raw, world["ws"]),
                       json={"uid": "nope", "title": "x"}).status_code == 403
    # Nor read a workspace the person has no role in.
    assert client.get("/v1/documents", headers=bearer(raw, world["other"])).status_code == 403
    # A token cannot make another token.
    assert client.post("/v1/me/tokens", headers=bearer(raw),
                       json={"name": "child", "scopes": ["read"]}).status_code == 403


def test_a_read_only_token_reads_and_a_workspace_fixed_token_stays_there(world):
    signed_in(world["owner"])
    ro = client.post("/v1/me/tokens", json={"name": "dashboards", "scopes": ["read"],
                                            "workspace_id": world["ws"]}).json()["token"]
    assert client.post("/v1/me/tokens", json={"name": "elsewhere", "scopes": ["read"],
                                              "workspace_id": world["other"]}).status_code == 403
    as_token()
    # No X-Workspace-Id needed: the token is fixed to its workspace.
    assert client.get("/v1/documents", headers=bearer(ro)).status_code == 200
    assert client.get("/v1/documents", headers=bearer(ro, world["other"])).status_code == 403
    denied = client.post("/v1/documents", headers=bearer(ro), json={"uid": "nope2", "title": "x"})
    assert denied.status_code == 403 and "only read" in denied.json()["detail"]


def test_an_administrators_token_is_no_administrator_without_the_admin_scope(world):
    signed_in(world["admin"])
    plain = client.post("/v1/me/tokens", json={"name": "plain", "scopes": ["read"]}).json()["token"]
    full = client.post("/v1/me/tokens", json={"name": "ops", "scopes": ["read", "admin"]}).json()["token"]
    as_token()
    assert client.get("/v1/admin/ai/config", headers=bearer(plain)).status_code == 403
    assert client.get("/v1/admin/ai/config", headers=bearer(full)).status_code == 200
    # Still not a way to manage tokens.
    assert client.get("/v1/admin/tokens", headers=bearer(full)).status_code == 403


def test_expired_and_revoked_tokens_stop_working(world):
    signed_in(world["owner"])
    made = client.post("/v1/me/tokens", json={"name": "short", "scopes": ["read"]}).json()
    db = SessionLocal()
    db.get(ApiToken, made["id"]).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()
    as_token()
    assert client.get("/v1/documents", headers=bearer(made["token"], world["ws"])).status_code == 401
    signed_in(world["owner"])
    assert client.get("/v1/me/tokens").json()[0]["status"] == "expired"
    other = client.post("/v1/me/tokens", json={"name": "revoke me", "scopes": ["read"]}).json()
    assert client.delete(f"/v1/me/tokens/{other['id']}").status_code == 204
    as_token()
    assert client.get("/v1/documents", headers=bearer(other["token"], world["ws"])).status_code == 401
    # An administrator sees every token and may revoke any.
    signed_in(world["admin"])
    ids = {t["id"]: t for t in client.get("/v1/admin/tokens").json()}
    assert ids[other["id"]]["status"] == "revoked" and ids[other["id"]]["owner_email"].startswith("owner-")


def test_a_token_made_before_kinds_existed_still_does_everything_in_its_workspace(world):
    raw = secrets.token_urlsafe(16)
    db = SessionLocal()
    db.add(ApiToken(workspace_id=world["ws"], token_hash=hash_token(raw)))
    db.commit()
    db.close()
    as_token()
    uid = f"legacy-{secrets.token_hex(3)}"
    assert client.post("/v1/documents", headers=bearer(raw), json={"uid": uid, "title": "x"}).status_code == 201
    assert client.delete(f"/v1/documents/{uid}", headers=bearer(raw)).status_code in (204, 200)


def test_the_profile_shows_the_account_the_session_the_groups_and_what_each_role_allows(world):
    signed_in(world["viewer"])
    p = client.get("/v1/me/profile").json()
    assert p["auth_type"] == "oidc" and p["user"]["name"] == "Vera Viewer"
    assert p["session"]["issuer"].endswith("/argus") and p["session"]["realm_roles"] == ["argus-user"]
    assert [g["name"] for g in p["groups"]] == ["Operators"]
    ws = {w["id"]: w for w in p["workspaces"]}[world["ws"]]
    assert ws["roles"] == [{"id": "viewer", "name": "Viewer", "via": "group:Operators"}]
    assert ws["permissions"]["documents"] == ["read"] and world["other"] not in {w["id"] for w in p["workspaces"]}
    raw = client.post("/v1/me/tokens", json={"name": "cli", "scopes": ["read"]}).json()["token"]
    as_token()
    via_token = client.get("/v1/me/profile", headers=bearer(raw)).json()
    assert via_token["auth_type"] == "personal_token" and via_token["token"]["name"] == "cli"
