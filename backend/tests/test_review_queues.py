"""Review queues (asset-model-revision §18.2): ageing in working days,
escalation to the backup steward and then the governance group, once per
level, and a dashboard of sizes and ages."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.ledger import cutover, queues
from app.main import app
from app.models.asset import Asset
from app.models.ledger import Conflict, ConflictEvent
from app.models.workflow import Notification
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)
NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)          # a Friday


def conflict(db, ws, ctype, severity, days_ago, detail=None, subject=None):
    cid = uuid.uuid4().hex[:24]
    db.add(Conflict(conflict_id=cid, conflict_type=ctype, severity=severity, workspace_id=ws,
                    subject_uid=subject or str(uuid.uuid4()), detail=detail or {}, opened_seq=1))
    db.add(ConflictEvent(conflict_id=cid, kind="opened", conflict_type=ctype, subject_uid="x", cause="t",
                         at=NOW - timedelta(days=days_ago)))
    db.flush()
    return f"conflict:{cid}"


def setup():
    ws = f"queue-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    d = cutover.create_domain(db, ws, f"d-{ws}", "Vacuum equipment", stream_ids=[])
    cutover.set_stewards(db, d.id, "owner", f"steward@{ws}.example", f"backup@{ws}.example")
    return db, ws


def test_each_item_goes_to_its_queue_with_the_section_18_2_thresholds():
    c = lambda t, s="non-blocking", detail=None: Conflict(conflict_type=t, severity=s, detail=detail or {})
    assert queues.queue_of(c("confirmed_vs_confirmed", "blocking")) == "blocking"
    assert queues.queue_of(c("port_confirmation_required", detail={"safety_class": "interlock"})) == "port_safety"
    assert queues.queue_of(c("port_confirmation_required")) == "port"
    assert queues.queue_of(c("identity_candidate")) == "identity_candidate"
    assert queues.queue_of(c("retirement_blocked")) == "retirement_flag"
    assert queues.queue_of(c("possible_overlap")) == "non_blocking"
    assert [queues._level("identity_candidate", a) for a in (10, 15, 29, 30)] == [0, 1, 1, 2]
    assert [queues._level("port_safety", a) for a in (0, 1)] == [1, 2]


def test_overdue_items_escalate_once_per_level_without_naming_the_record(monkeypatch):
    monkeypatch.setenv("ARGUS_GOVERNANCE", "governance@example.org")
    db, ws = setup()
    candidate = conflict(db, ws, "identity_candidate", "non-blocking", 22)     # 16 working days: to the backup
    conflict(db, ws, "confirmed_vs_confirmed", "blocking", 10)                 # 8 working days: to governance
    conflict(db, ws, "contributory_disagreement", "non-blocking", 7)           # on time
    sent = queues.escalate(db, NOW, ws)
    assert sent == {"backup": 1, "governance": 1, "without_recipient": 0}
    notes = db.query(Notification).filter_by(workspace_id=ws, kind="review_escalated").all()
    assert {n.recipient for n in notes if n.detail["level"] == 1} == {f"backup@{ws}.example", f"steward@{ws}.example"}
    assert {n.recipient for n in notes if n.detail["level"] == 2} == {"governance@example.org", f"backup@{ws}.example"}
    assert all("working day" in n.title and n.detail["path"] == "/review" for n in notes)
    # Once per level.
    assert queues.escalate(db, NOW, ws) == {"backup": 0, "governance": 0, "without_recipient": 0}
    # Three weeks on, the candidate reaches the governance group too.
    later = queues.escalate(db, NOW + timedelta(days=21), ws)
    assert later["governance"] == 1
    assert db.query(Notification).filter(Notification.workspace_id == ws,
                                         Notification.detail["item"].astext == candidate).count() == 4
    db.rollback()
    db.close()


def test_the_dashboard_counts_sizes_ages_and_escalations():
    db, ws = setup()
    conflict(db, ws, "identity_candidate", "non-blocking", 1)
    conflict(db, ws, "identity_candidate", "non-blocking", 22)
    conflict(db, ws, "possible_overlap", "non-blocking", 70)
    queues.escalate(db, NOW, ws)
    dash = queues.dashboard(db, ws, NOW)
    by = {q["queue"]: q for q in dash["queues"]}
    cand = by["identity_candidate"]
    assert cand["size"] == 2 and cand["overdue"] == 1 and cand["at_backup"] == 1 and cand["oldest"] == 16
    assert {b["label"]: b["count"] for b in cand["buckets"]} == {"0–2": 1, "3–5": 0, "6–10": 0, "11–30": 1, "31+": 0}
    assert by["non_blocking"]["targets"] == {"due": 30, "backup": 45, "governance": 90}
    assert dash["steward"] == f"steward@{ws}.example" and dash["total"] == 3
    db.rollback()
    db.close()


def test_the_queues_are_served_and_hide_what_the_viewer_may_not_see():
    db, ws = setup()
    secret = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=None, key=f"SEC-{ws}", name="Investigation",
                   type="Equipment", attributes={"classification": "restricted:safety_investigation"})
    from app.ledger import engine
    secret.schema_uid = engine.ensure_type(db, ws, "Equipment").uid
    db.add(secret)
    db.flush()
    conflict(db, ws, "identity_candidate", "non-blocking", 1, subject=secret.uid)
    conflict(db, ws, "identity_candidate", "non-blocking", 1)
    headers = token(db, ws)
    db.commit()
    db.close()
    dash = client.get("/v1/ledger/review/queues", headers=headers).json()
    assert {q["queue"]: q["size"] for q in dash["queues"]}["identity_candidate"] == 1
    assert client.post("/v1/ledger/review/escalate", headers=headers).status_code == 200
