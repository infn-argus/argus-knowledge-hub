"""Avatars, type icons and labels — the pieces a person manages by hand,
plus the QR code the Jira import brings in for free.
"""
import os
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.asset import Asset
from app.models.asset_subresources import AssetLabel
from app.models.icon import Icon
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.jira_import import _import_object_qrcode

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
    # Uploads write to disk; keep them out of the real attachments volume.
    directory = tmp_path_factory.mktemp("attachments")
    monkeypatch.setattr("app.routers.assets.ATTACHMENTS_DIR", str(directory))
    monkeypatch.setattr("app.routers.schemas.ATTACHMENTS_DIR", str(directory))
    monkeypatch.setattr("app.routers.icons.ATTACHMENTS_DIR", str(directory))

    db = SessionLocal()
    workspace_id = f"test-{secrets.token_hex(4)}"
    db.add(Workspace(id=workspace_id, name="Test"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace_id, token_hash=hash_token(raw)))
    db.commit()
    db.close()
    return raw


def auth(raw_token: str) -> dict:
    return {"Authorization": f"Bearer {raw_token}"}


def _make_asset(token: str, suffix: str) -> str:
    client.post("/v1/schemas", json={"uid": f"sc-{suffix}", "name": "Camera"}, headers=auth(token))
    resp = client.post(
        "/v1/assets",
        json={
            "uid": f"as-{suffix}", "schema_uid": f"sc-{suffix}", "key": f"K-{suffix}",
            "name": "Camera 1", "type": "Camera", "attributes": {},
        },
        headers=auth(token),
    )
    assert resp.status_code == 201
    return f"as-{suffix}"


def test_avatar_upload_promote_and_clear(token):
    suffix = secrets.token_hex(4)
    asset_uid = _make_asset(token, suffix)

    uploaded = client.post(
        f"/v1/assets/{asset_uid}/avatar",
        files={"file": ("face.png", PNG, "image/png")},
        headers=auth(token),
    )
    assert uploaded.status_code == 200
    first_avatar = uploaded.json()["avatar_icon_uid"]
    assert first_avatar

    # The uploaded picture is a normal attachment of the object, which is
    # what lets the UI offer it again after the avatar changes.
    listed = client.get(f"/v1/attachments?asset_uid={asset_uid}", headers=auth(token)).json()
    assert [a["uid"] for a in listed] == [first_avatar]

    # A second upload replaces the avatar without destroying the first
    # picture — losing an image because someone swapped an avatar would be
    # silent data loss.
    second = client.post(
        f"/v1/assets/{asset_uid}/avatar",
        files={"file": ("other.png", PNG, "image/png")},
        headers=auth(token),
    )
    second_avatar = second.json()["avatar_icon_uid"]
    assert second_avatar != first_avatar
    listed = client.get(f"/v1/attachments?asset_uid={asset_uid}", headers=auth(token)).json()
    assert {a["uid"] for a in listed} == {first_avatar, second_avatar}

    promoted = client.put(
        f"/v1/assets/{asset_uid}/avatar/{first_avatar}", headers=auth(token)
    )
    assert promoted.status_code == 200
    assert promoted.json()["avatar_icon_uid"] == first_avatar

    cleared = client.delete(f"/v1/assets/{asset_uid}/avatar", headers=auth(token))
    assert cleared.status_code == 200
    assert cleared.json()["avatar_icon_uid"] is None
    # Both pictures survive as attachments.
    listed = client.get(f"/v1/attachments?asset_uid={asset_uid}", headers=auth(token)).json()
    assert len(listed) == 2


def test_avatar_rejects_an_attachment_from_another_object(token):
    suffix_a, suffix_b = secrets.token_hex(4), secrets.token_hex(4)
    asset_a = _make_asset(token, suffix_a)
    asset_b = _make_asset(token, suffix_b)
    other = client.post(
        f"/v1/assets/{asset_b}/avatar",
        files={"file": ("b.png", PNG, "image/png")},
        headers=auth(token),
    ).json()["avatar_icon_uid"]

    resp = client.put(f"/v1/assets/{asset_a}/avatar/{other}", headers=auth(token))
    assert resp.status_code == 404


def test_schema_icon_replace_and_clear_keep_the_shared_library_intact(token):
    """A type icon comes from the shared library, not an exclusive upload —
    replacing or clearing the one a type points at must not delete it out
    from under any other type that might be using the same picture."""
    suffix = secrets.token_hex(4)
    client.post("/v1/schemas", json={"uid": f"ic-{suffix}", "name": "Pump"}, headers=auth(token))

    first = client.post(
        f"/v1/schemas/ic-{suffix}/icon",
        files={"file": ("icon.png", PNG, "image/png")},
        headers=auth(token),
    ).json()["icon_uid"]

    db = SessionLocal()
    first_path = db.get(Icon, first).storage_path
    db.close()
    assert os.path.exists(first_path)

    second = client.post(
        f"/v1/schemas/ic-{suffix}/icon",
        files={"file": ("icon2.png", PNG, "image/png")},
        headers=auth(token),
    ).json()["icon_uid"]
    assert second != first

    # The replaced icon survives in the library — unlike the old
    # single-owner attachment model, nothing here should touch it.
    db = SessionLocal()
    assert db.get(Icon, first) is not None
    db.close()
    assert os.path.exists(first_path)

    cleared = client.delete(f"/v1/schemas/ic-{suffix}/icon", headers=auth(token))
    assert cleared.status_code == 200
    assert cleared.json()["icon_uid"] is None
    db = SessionLocal()
    assert db.get(Icon, second) is not None
    db.close()


def test_icon_library_reuse_and_reference_counted_delete(token):
    suffix = secrets.token_hex(4)
    client.post("/v1/schemas", json={"uid": f"lib-a-{suffix}", "name": "Pump A"}, headers=auth(token))
    client.post("/v1/schemas", json={"uid": f"lib-b-{suffix}", "name": "Pump B"}, headers=auth(token))

    icon = client.post(
        "/v1/icons",
        files={"file": ("shared.png", PNG, "image/png")},
        data={"name": "Shared pump icon"},
        headers=auth(token),
    ).json()
    assert icon["name"] == "Shared pump icon"

    for uid in (f"lib-a-{suffix}", f"lib-b-{suffix}"):
        resp = client.put(f"/v1/schemas/{uid}/icon/{icon['uid']}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["icon_uid"] == icon["uid"]

    # Still used by lib-b — deleting it outright is refused.
    client.delete(f"/v1/schemas/lib-a-{suffix}/icon", headers=auth(token))
    blocked = client.delete(f"/v1/icons/{icon['uid']}", headers=auth(token))
    assert blocked.status_code == 409

    # Once nothing references it, the delete goes through and the file is gone.
    db = SessionLocal()
    path = db.get(Icon, icon["uid"]).storage_path
    db.close()
    client.delete(f"/v1/schemas/lib-b-{suffix}/icon", headers=auth(token))
    removed = client.delete(f"/v1/icons/{icon['uid']}", headers=auth(token))
    assert removed.status_code == 204
    assert not os.path.exists(path)


def test_duplicate_label_is_rejected(token):
    """The Flutter model declares (type, value) unique and a scan has to
    resolve to one object; without this check two objects could claim the
    same code and a scan would be ambiguous."""
    suffix_a, suffix_b = secrets.token_hex(4), secrets.token_hex(4)
    asset_a = _make_asset(token, suffix_a)
    asset_b = _make_asset(token, suffix_b)
    body = {
        "uid": f"lb-{suffix_a}", "type": "qrcode", "value": "https://example.invalid/o/1",
        "issuer": "user", "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }

    assert client.post(f"/v1/assets/{asset_a}/labels", json=body, headers=auth(token)).status_code == 201

    clash = client.post(
        f"/v1/assets/{asset_b}/labels",
        json={**body, "uid": f"lb-{suffix_b}"},
        headers=auth(token),
    )
    assert clash.status_code == 409
    assert "Camera 1" in clash.json()["detail"]

    # A different symbology carrying the same string is a different label.
    ok = client.post(
        f"/v1/assets/{asset_b}/labels",
        json={**body, "uid": f"lb2-{suffix_b}", "type": "barcode"},
        headers=auth(token),
    )
    assert ok.status_code == 201


def test_jira_qrcode_label_is_imported_and_kept_current():
    """Jira Insight's per-object QR code encodes the object URL, which the
    navlist payload already carries as _links.self — so it imports with no
    extra request."""
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    db.add(Workspace(id=f"ws-{suffix}", name="WS"))
    db.flush()
    db.add(Schema(uid=f"s-{suffix}", workspace_id=f"ws-{suffix}", name="Camera"))
    db.flush()
    asset = Asset(
        uid=f"a-{suffix}", workspace_id=f"ws-{suffix}", schema_uid=f"s-{suffix}",
        key=f"JK-{suffix}", name="Camera", type="Camera",
    )
    db.add(asset)
    db.flush()

    jo = {"id": 145356, "_links": {"self": "https://jira.invalid/secure/ShowObject.jspa?id=145356"}}
    assert _import_object_qrcode(db, asset, jo) == 1
    db.commit()

    label = db.query(AssetLabel).filter(AssetLabel.asset_uid == asset.uid).one()
    assert label.type == "qrcode"
    assert label.issuer == "system"
    assert label.value == "https://jira.invalid/secure/ShowObject.jspa?id=145356"

    # Re-importing the same object must not pile up duplicates...
    assert _import_object_qrcode(db, asset, jo) == 0
    db.commit()
    assert db.query(AssetLabel).filter(AssetLabel.asset_uid == asset.uid).count() == 1

    # ...and a moved Jira updates the existing label in place.
    moved = {"id": 145356, "_links": {"self": "https://jira2.invalid/secure/ShowObject.jspa?id=145356"}}
    assert _import_object_qrcode(db, asset, moved) == 0
    db.commit()
    label = db.query(AssetLabel).filter(AssetLabel.asset_uid == asset.uid).one()
    assert label.value == "https://jira2.invalid/secure/ShowObject.jspa?id=145356"
    db.close()


def test_jira_object_without_links_produces_no_label():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    db.add(Workspace(id=f"ws-{suffix}", name="WS"))
    db.flush()
    db.add(Schema(uid=f"s-{suffix}", workspace_id=f"ws-{suffix}", name="Camera"))
    db.flush()
    asset = Asset(
        uid=f"a-{suffix}", workspace_id=f"ws-{suffix}", schema_uid=f"s-{suffix}",
        key=f"JK-{suffix}", name="Camera", type="Camera",
    )
    db.add(asset)
    db.flush()
    assert _import_object_qrcode(db, asset, {"id": 1}) == 0
    assert db.query(AssetLabel).filter(AssetLabel.asset_uid == asset.uid).count() == 0
    db.close()
