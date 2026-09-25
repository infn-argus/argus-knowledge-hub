"""Cutover entry criteria (asset-model-revision §17.4): what ARGUS computes
itself — shadow validation's length and clean runs, queue ageing — and the
waivers of the governance group."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db import SessionLocal
from app.ledger import cutover, entry
from app.ledger.engine import LedgerError
from app.models.ledger import Conflict, ConflictEvent, Decision, ReconciliationReport
from app.models.workspace import Workspace

NOW = datetime.now(timezone.utc)


def test_working_days_skip_weekends():
    friday = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
    assert entry.working_days(friday, friday + timedelta(days=3)) == 1          # to Monday
    assert entry.working_days(friday, friday + timedelta(days=7)) == 5
    assert entry.working_days(friday, friday) == 0


@pytest.fixture()
def domain():
    ws = f"entry-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    d = cutover.create_domain(db, ws, f"d-{ws}", "Vacuum equipment", stream_ids=[])
    cutover.advance(db, d.id, "T1", "steward")
    cutover.advance(db, d.id, "T2", "steward")
    yield db, d
    db.rollback()
    db.close()


def backdate_t2(db, d, days):
    db.add(Decision(decision_id=str(uuid.uuid4()), batch_id=str(uuid.uuid4()), kind="advance_domain", actor="steward",
                    workspace_id=d.workspace_id, target={"domain": d.id, "from": "T1", "to": "T2"}, supersedes=[],
                    at=NOW - timedelta(days=days)))
    db.flush()


def report(db, d, passed, days_ago):
    db.add(ReconciliationReport(id=str(uuid.uuid4()), domain_id=d.id, manifest_hash="m", passed=passed, body={},
                                body_hash="h", actor="steward", created_at=NOW - timedelta(days=days_ago)))
    db.flush()


def by_id(db, d, **kw):
    return {c["id"]: c for c in entry.criteria(db, d, **kw)}


def test_shadow_validation_needs_two_weeks_and_ten_consecutive_clean_runs(domain):
    db, d = domain
    t2 = by_id(db, d)["t2"]
    assert not t2["ok"] and t2["detail"]["days"] == 0          # it just started
    # A domain that entered T2 twenty days ago (decisions cannot be edited, so it is recorded so).
    d2 = cutover.create_domain(db, d.workspace_id, f"{d.id}-b", "Older", stream_ids=[])
    d2.stage = "T2"
    backdate_t2(db, d2, 20)
    for i in range(9):
        report(db, d2, True, 19 - i)
    assert by_id(db, d2)["t2"]["detail"]["clean_runs"] == 9 and not by_id(db, d2)["t2"]["ok"]
    report(db, d2, True, 5)
    assert by_id(db, d2)["t2"]["ok"]
    report(db, d2, False, 1)                                   # the streak starts again
    assert by_id(db, d2)["t2"]["detail"]["clean_runs"] == 0
    for i in range(10):
        report(db, d2, True, 0.5 - i / 100)
    assert by_id(db, d2)["t2"]["ok"] and not by_id(db, d2)["t2"]["detail"]["over_limit"]
    # Past 8 weeks the governance group decides (§17.2): flagged, not refused.
    d3 = cutover.create_domain(db, d.workspace_id, f"{d.id}-c", "Long", stream_ids=[])
    d3.stage = "T2"
    backdate_t2(db, d3, 60)
    assert by_id(db, d3)["t2"]["detail"]["over_limit"]


def test_queues_past_their_ageing_target_hold_the_freeze(domain):
    db, d = domain

    def conflict(ctype, severity, days_ago, detail=None):
        cid = uuid.uuid4().hex[:24]
        db.add(Conflict(conflict_id=cid, conflict_type=ctype, severity=severity, workspace_id=d.workspace_id,
                        subject_uid=str(uuid.uuid4()), detail=detail or {}, opened_seq=1))
        db.add(ConflictEvent(conflict_id=cid, kind="opened", conflict_type=ctype, subject_uid="x", cause="t",
                             at=NOW - timedelta(days=days_ago)))
        db.flush()

    conflict("identity_candidate", "non-blocking", 3)
    assert by_id(db, d)["queues_ageing"]["ok"]
    conflict("contributory_disagreement", "non-blocking", 60)  # 30 working days is its target
    ageing = by_id(db, d)["queues_ageing"]
    assert not ageing["ok"] and ageing["detail"]["overdue"] == 1
    # A safety-relevant port confirmation is never left open at a cutover.
    conflict("port_confirmation_required", "non-blocking", 0, {"safety_class": "interlock"})
    assert by_id(db, d)["queues_ageing"]["detail"]["overdue"] == 2
    conflict("confirmed_vs_confirmed", "blocking", 0)
    assert not by_id(db, d)["queues_blocking"]["ok"]


def test_waivers_need_a_reason_and_some_criteria_are_never_waived(domain):
    db, d = domain
    with pytest.raises(LedgerError, match="needs a reason"):
        entry.check(db, d, {}, {"t2": " "})
    with pytest.raises(LedgerError, match="cannot be waived"):
        entry.check(db, d, {}, {"queues_blocking": "pilot"})
    c = {x["id"]: x for x in entry.check(db, d, {}, {"t2": "pilot rehearsal, decided by the governance group"})}
    assert c["t2"]["ok"] and c["t2"]["waived"] and not c["t2"]["met"]
    assert not c["users_trained"]["ok"] and c["users_trained"]["attested"]
