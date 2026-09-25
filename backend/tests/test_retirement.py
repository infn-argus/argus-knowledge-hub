"""The last readiness items (§19 items 8, 11, 14): the API's version and
deprecation policy, the Jira host after retirement, and the conditions
of the retirement itself."""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import OidcIdentity, get_identity
from app.db import SessionLocal
from app.ledger import cutover
from app.ledger.engine import LedgerError
from app.main import app
from app.models.user import User
from app.services import access_review, api_policy, retirement
from tests.test_ledger_slice import Slice
from tests.test_ledger_transition import cut_over, token

client = TestClient(app)


# --------------------------------------------------------------------------- item 8

def test_every_response_names_the_api_version_and_the_policy_is_published():
    meta = client.get("/v1/meta/api")
    assert meta.status_code == 200 and meta.headers["X-ARGUS-API-Version"] == "1"
    body = meta.json()
    assert body["version"] == "1" and body["min_notice_days"] >= 180 and body["policy"]
    assert api_policy.check(api_policy.DEPRECATIONS) == []      # every listed deprecation gives full notice


def test_a_deprecated_endpoint_announces_its_sunset_and_is_gone_after_it(monkeypatch):
    today = datetime.now(timezone.utc).date()
    announced = api_policy.Deprecation("GET", "/v1/meta/api", today - timedelta(days=1), today + timedelta(days=200),
                                       "/v2/meta/api")
    monkeypatch.setattr(api_policy, "DEPRECATIONS", [announced])
    resp = client.get("/v1/meta/api")
    assert resp.status_code == 200
    assert resp.headers["Deprecation"].startswith("@") and "GMT" in resp.headers["Sunset"]
    assert resp.headers["Link"] == '</v2/meta/api>; rel="successor-version"'
    assert resp.json()["deprecations"][0]["gone"] is False

    gone = api_policy.Deprecation("GET", "/v1/meta/api", today - timedelta(days=400), today - timedelta(days=1),
                                  "/v2/meta/api")
    monkeypatch.setattr(api_policy, "DEPRECATIONS", [gone])
    resp = client.get("/v1/meta/api")
    assert resp.status_code == 410 and resp.json()["detail"]["successor"] == "/v2/meta/api"
    # Too short a notice is caught before it ships.
    short = api_policy.Deprecation("*", "/v1/x/{uid}", today, today + timedelta(days=30), "/v1/y")
    assert api_policy.check([short]) and short.matches("DELETE", "/v1/x/abc") and not short.matches("GET", "/v1/x")


def test_stored_jira_and_insight_references_resolve_in_one_call():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    headers = token(db, s.inv)
    db.commit()
    db.close()
    ids = [f"{s.fac}INV-84321", "https://jira.example.org/browse/NOPE-1", f"{s.fac}INV-84321"]
    resp = client.post("/v1/lookup/batch", headers=headers, json={"identifiers": ids})
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert [o["identifier"] for o in out] == ids
    assert out[0]["status"] == "migrated" and out[0]["path"].startswith("/assets/") and out[2]["uid"] == out[0]["uid"]
    assert out[1]["status"] == "not migrated"
    too_many = client.post("/v1/lookup/batch", headers=headers, json={"identifiers": ["X-1"] * 1001})
    assert too_many.status_code == 422


# --------------------------------------------------------------------------- item 11

def test_the_retired_jira_host_sends_every_link_to_the_lookup_page(monkeypatch):
    monkeypatch.setenv("JIRA_LEGACY_HOSTS", "jira.example.org")
    monkeypatch.setenv("ARGUS_WEB_URL", "https://argus.example.org")
    resp = client.get("/browse/SPARC-123", headers={"Host": "jira.example.org"}, follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == ("https://argus.example.org/lookup/"
                                        "https%3A%2F%2Fjira.example.org%2Fbrowse%2FSPARC-123")
    board = client.get("/secure/RapidBoard.jspa", params={"rapidView": "7", "selectedIssue": "SPARC-9"},
                       headers={"Host": "jira.example.org:443"}, follow_redirects=False)
    assert "selectedIssue%3DSPARC-9" in board.headers["location"]
    assert client.get("/", headers={"Host": "jira.example.org"}, follow_redirects=False).headers["location"] \
        == "https://argus.example.org/"
    # Behind a proxy that forwards to a path instead of by host name.
    proxied = client.get("/legacy/jira/browse/SPARC-5", headers={"X-Forwarded-Host": "jira.example.org"},
                         follow_redirects=False)
    assert proxied.status_code == 301 and proxied.headers["location"].endswith("%2Fbrowse%2FSPARC-5")
    # ARGUS's own host is untouched.
    assert client.get("/v1/meta/api").status_code == 200


# --------------------------------------------------------------------------- item 14

def admin_identity(db):
    user = User(id=f"admin-{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@test.invalid", name="Admin",
                is_admin=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)            # used after this session closes
    return OidcIdentity(user=user)


def test_only_an_administrator_sees_the_retirement_and_it_is_refused_while_conditions_are_open():
    db = SessionLocal()
    s = Slice()
    headers = token(db, s.inv)
    ident = admin_identity(db)
    db.close()
    assert client.get("/v1/retirement", headers=headers).status_code == 403
    app.dependency_overrides[get_identity] = lambda: ident
    try:
        status = client.get("/v1/retirement").json()
        ids = {c["id"] for c in status["conditions"]}
        assert {"domains", "exports", "retention", "access_review", "audit_chain", "workflows",
                "restore-rehearsal", "probe", "redirect", "dr_drill"} <= ids
        refused = client.post("/v1/retirement/sign", json={"attestations": {}})
        assert refused.status_code == 409 and refused.json()["detail"]["conditions"]
        assert client.post("/v1/retirement/retention", json={"reference": " ", "jira_archive_until": "2036-12-31"}
                           ).status_code == 422
    finally:
        app.dependency_overrides.pop(get_identity, None)


def test_signing_the_retirement_moves_every_archived_domain_to_T5(monkeypatch):
    monkeypatch.setenv("JIRA_LEGACY_HOSTS", "jira.example.org")
    monkeypatch.setenv("ARGUS_WEB_URL", "https://argus.example.org")
    from app.ledger import audit
    monkeypatch.setattr(audit, "verify", lambda db: {"ok": True, "days": 30, "head": "x"})
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    d = cut_over(db, s)
    domain_id = d.id
    db.commit()
    scope = [domain_id]
    # No domain reaches T5 on its own.
    cutover.advance(db, domain_id, "T4", "owner")
    with pytest.raises(LedgerError):
        cutover.advance(db, domain_id, "T5", "owner")
    open_ = {c["id"] for c in retirement.conditions(db, {}, scope) if not c["ok"]}
    assert {"retention", "access_review", "restore-rehearsal", "probe", "dr_drill"} <= open_
    assert "domains" not in open_ and "exports" not in open_ and "redirect" not in open_

    retirement.record_retention(db, "owner", reference="INFN records policy 2025/7",
                                jira_archive_until=date(2036, 12, 31), exports_until=None, audit_until=None, note=None)
    review = access_review.create(db, s.inv, "owner")
    access_review.sign(db, review, "owner-a")
    access_review.sign(db, review, "owner-b")
    retirement.record_job(db, "restore-rehearsal", {"ok": True}, True)
    retirement.record_job(db, "probe", {"meets": {}}, False)          # a failed probe is no evidence
    assert not next(c for c in retirement.conditions(db, {}, scope) if c["id"] == "probe")["ok"]
    retirement.record_job(db, "probe", {"meets": {}}, True)
    attest = {k: True for k in retirement.ATTESTATIONS}
    with pytest.raises(retirement.RetirementError):
        retirement.sign(db, "owner", {**attest, "dr_drill": False}, scope=scope)
    decision = retirement.sign(db, "owner", attest, "all domains archived", scope=scope)
    assert decision.kind == "retire_jira"
    assert cutover._domain(db, domain_id).stage == "T5"
    with pytest.raises(retirement.RetirementError):                 # once
        retirement.sign(db, "owner", attest, scope=scope)
    # Instance-wide state stays out of the shared test database.
    db.rollback()
    db.close()
