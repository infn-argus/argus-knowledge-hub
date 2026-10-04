"""A new instance has no administrator and nobody to make one in the web app: the emails in
ARGUS_BOOTSTRAP_ADMINS are made administrators when they first sign in, and nobody else is."""
import secrets

from app.auth import _resolve_oidc_user
from app.db import SessionLocal


def test_a_listed_email_is_an_administrator_from_its_first_sign_in(monkeypatch):
    t = secrets.token_hex(4)
    listed, other = f"first-{t}@lnf.infn.it", f"other-{t}@lnf.infn.it"
    monkeypatch.setenv("ARGUS_BOOTSTRAP_ADMINS", f" {listed.upper()} , nobody@example.org")
    db = SessionLocal()
    try:
        assert _resolve_oidc_user(db, {"sub": f"s1-{t}", "email": listed}).is_admin is True
        assert _resolve_oidc_user(db, {"sub": f"s2-{t}", "email": other}).is_admin is False
    finally:
        db.rollback()
        db.close()


def test_without_the_setting_nobody_is(monkeypatch):
    monkeypatch.delenv("ARGUS_BOOTSTRAP_ADMINS", raising=False)
    db = SessionLocal()
    try:
        assert _resolve_oidc_user(db, {"sub": f"s-{secrets.token_hex(4)}", "email": "x@y.org"}).is_admin is False
    finally:
        db.rollback()
        db.close()
