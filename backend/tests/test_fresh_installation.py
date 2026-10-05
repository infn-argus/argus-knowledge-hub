"""A new installation can be entered: a default workspace, and a bootstrap administrator even when their
account was made before they were named one."""
import secrets

import pytest
from sqlalchemy import select, update

from app.db import Base, SessionLocal, engine
from app.models.user import User
from app.models.workspace import Workspace
from app.routers.workspaces import ensure_default_workspace


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def test_an_installation_with_no_workspace_gets_one_ready_to_use(monkeypatch):
    monkeypatch.setenv("ARGUS_DEFAULT_WORKSPACE", f"main-{secrets.token_hex(3)}")
    monkeypatch.setenv("ARGUS_DEFAULT_WORKSPACE_NAME", "Main")
    db = SessionLocal()
    real = db.scalar
    calls = {"n": 0}

    def empty_first(stmt, *a, **kw):                    # "is there any workspace?" answers no, once
        calls["n"] += 1
        return None if calls["n"] == 1 else real(stmt, *a, **kw)
    monkeypatch.setattr(db, "scalar", empty_first)
    try:
        made = ensure_default_workspace(db)
        assert made and db.get(Workspace, made).name == "Main"
        from app.models.schema import Schema
        assert db.scalar(select(Schema.uid).where(Schema.workspace_id == made, Schema.applies_to == "documents"))
    finally:
        monkeypatch.setattr(db, "scalar", real)
        if made:
            from app.ledger.audit import allow_purge
            allow_purge(db)
            db.delete(db.get(Workspace, made))
            db.commit()
        db.close()


def test_an_installation_with_workspaces_is_left_alone(monkeypatch):
    db = SessionLocal()
    db.add(Workspace(id=f"some-{secrets.token_hex(3)}", name="Some"))
    db.commit()
    try:
        assert ensure_default_workspace(db) is None
        monkeypatch.setenv("ARGUS_DEFAULT_WORKSPACE", "")
        assert ensure_default_workspace(db) is None
    finally:
        db.close()


def test_a_bootstrap_administrator_made_before_being_named_is_one_while_nobody_is(monkeypatch):
    from app.auth import _resolve_oidc_user
    email = f"first-{secrets.token_hex(3)}@argus.test"
    monkeypatch.setenv("ARGUS_BOOTSTRAP_ADMINS", email)
    db = SessionLocal()
    try:
        db.add(User(id=f"u-{secrets.token_hex(3)}", email=email, is_admin=False))
        db.flush()
        claims = {"sub": f"sub-{secrets.token_hex(3)}", "email": email}
        # Another administrator exists: naming stops mattering once someone can grant it.
        db.add(User(id=f"adm-{secrets.token_hex(3)}", email="other@argus.test", is_admin=True))
        db.flush()
        assert _resolve_oidc_user(db, claims).is_admin is False
        # Nobody is an administrator (a fresh installation): the named person becomes one.
        db.execute(update(User).where(User.email != email).values(is_admin=False))
        assert _resolve_oidc_user(db, claims).is_admin is True
        # Someone not named does not.
        stranger = _resolve_oidc_user(db, {"sub": "s-x", "email": f"x-{secrets.token_hex(3)}@argus.test"})
        db.execute(update(User).where(User.id != stranger.id).values(is_admin=False))
        assert _resolve_oidc_user(db, {"sub": "s-x", "email": stranger.email}).is_admin is False
    finally:
        db.rollback()
        db.close()
