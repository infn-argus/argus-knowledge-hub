"""Guided replacement from the field (flutter-app-design §8, revision §24.8, A68)."""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal
from app.ledger import engine
from app.main import app
from app.models.asset import Asset
from tests.test_ledger_connectivity import ITFixture
from tests.test_ledger_transition import token

client = TestClient(app)
AT = "2026-09-20T10:00:00+00:00"


def setup(interlock=None):
    it = ITFixture(interlock_segment=interlock)
    db = SessionLocal()
    h = token(db, it.it)
    db.commit()
    ids = {"pos": it.pos(db).uid, "old": it.conv(db, "M-5531").uid, "new": it.conv(db, "M-7702").uid,
           "other": it.conv(db, "M-8800").uid, "inst": it.installation}
    db.close()
    return it, h, ids


def _count(db):
    return db.scalar(select(func.count()).select_from(Asset))


def test_A68_a_wrong_outgoing_unit_and_an_interlock_make_the_replacement_a_proposal(monkeypatch):
    it, h, ids = setup(interlock=4)
    db = SessionLocal()
    before = _count(db)
    db.close()
    base = {"position_uid": ids["pos"], "at": AT, "seen_installation_uid": ids["inst"]}

    # An unknown incoming unit: nothing is made from the Position's name; registration is the way.
    unknown = client.post("/v1/installations/replace", headers=h,
                          json={**base, "incoming_uid": str(uuid.uuid4()), "dry_run": True}).json()
    assert unknown["outcome"] == "refused"
    assert any(c["id"] == "incoming" and "Register it first" in c["message"] for c in unknown["checks"])

    # The person scanned the wrong outgoing unit; an interlock segment sits behind the Position.
    preview = client.post("/v1/installations/replace", headers=h, json={
        **base, "incoming_uid": ids["new"], "outgoing_uid": ids["other"], "dry_run": True}).json()
    assert preview["outcome"] == "propose"
    assert "the outgoing unit differs from the recorded one" in preview["reasons"]
    assert "port confirmation is needed" in preview["reasons"]
    assert any(c["id"] == "ports" and "interlock" in c["message"] for c in preview["checks"])
    assert preview["discrepancy"]["recorded"]["uid"] == ids["old"]
    assert preview["consequences"]["hidden_segments"] == 4            # another workspace's segments: counted only

    r = client.post("/v1/installations/replace", headers=h, json={
        **base, "incoming_uid": ids["new"], "outgoing_uid": ids["other"], "reason": "Failure",
        "evidence": {"photos": ["up-1"], "note": "label unreadable"}})
    assert r.status_code == 202, r.text
    out = r.json()
    assert out["outcome"] == "proposed" and out["review_item"] and out["discrepancy_item"]
    db = SessionLocal()
    [current] = [v for v in engine.installations(db, position_uid=ids["pos"], status="Confirmed")
                 if (v["valid_until"] or {"kind": "open"}).get("kind") == "open"]
    assert current["asset_uid"] == ids["old"]                         # nothing ended or started
    assert _count(db) == before                                       # no unit created
    db.close()
    queue = client.get("/v1/ledger/review", headers=h).json()["conflicts"]
    types = {c["conflict_id"]: c["type"] for c in queue}
    assert types[out["review_item"]] == "replacement_proposal"
    assert types[out["discrepancy_item"]] == "outgoing_discrepancy"

    # An approver confirms: the same atomic swap; the interlock segment then waits for its port.
    ok = client.post(f"/v1/ledger/review/replacements/{out['review_item']}/confirm", headers=h)
    assert ok.status_code == 200, ok.text
    db = SessionLocal()
    [current] = [v for v in engine.installations(db, position_uid=ids["pos"], status="Confirmed")
                 if (v["valid_until"] or {"kind": "open"}).get("kind") == "open"]
    assert current["asset_uid"] == ids["new"]
    assert it.items(db, 4, "port_confirmation_required")
    db.close()
    assert out["review_item"] not in {c["conflict_id"] for c in client.get("/v1/ledger/review", headers=h).json()["conflicts"]}
    # The discrepancy stays for the owner to resolve.
    assert client.post(f"/v1/ledger/review/replacements/{out['discrepancy_item']}/reject", headers=h,
                       json={"reason": "label swapped on the rack"}).status_code == 200


def test_a_plain_replacement_by_the_owner_applies_at_once():
    it, h, ids = setup()
    r = client.post("/v1/installations/replace", headers=h, json={
        "position_uid": ids["pos"], "incoming_uid": ids["new"], "outgoing_uid": ids["old"], "at": AT,
        "seen_installation_uid": ids["inst"]})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "applied" and r.json()["ended"] == [ids["inst"]]
    again = client.post("/v1/installations/replace", headers=h, json={
        "position_uid": ids["pos"], "incoming_uid": ids["new"], "at": AT, "dry_run": True}).json()
    assert again["outcome"] == "refused" and any("already installed here" in c["message"] for c in again["checks"])


def test_the_field_client_lists_its_review_items_with_the_decisions_it_may_take():
    it, h, ids = setup(interlock=4)
    r = client.post("/v1/installations/replace", headers=h, json={
        "position_uid": ids["pos"], "incoming_uid": ids["new"], "outgoing_uid": ids["other"], "at": AT,
        "seen_installation_uid": ids["inst"]}).json()
    mine = client.get("/v1/ledger/review/mine", headers=h).json()
    assert mine["assigned_to_me"] is True                             # a workspace token sees them all
    by_key = {i["key"]: i for i in mine["items"]}
    proposal = by_key[f"conflict:{r['review_item']}"]
    assert proposal["kind"] == "replacement_proposal" and proposal["decisions"] == ["confirm", "reject"]
    assert proposal["record"]["uid"] == ids["pos"]
    assert proposal["detail"]["evidence"] == {} and "port confirmation is needed" in proposal["detail"]["reasons"]
    assert by_key[f"conflict:{r['discrepancy_item']}"]["decisions"] == ["resolve"]
