"""Product readiness (asset-model-revision §19) and the gaps left by the
cutover gates: field-level restrictions, unmerge, merges that overlap,
checksum backfill, the pilot reversion export, the derive worker, the
append-only audit log and its digest chain, controlled bulk changes, and
equipment lifecycle, custody and spares."""
import json
import secrets
import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db import SessionLocal
from app.ledger import audit, bulk, cutover, engine, equipment, identity, service, temporal
from app.ledger.__main__ import backfill_checksums, derive_worker
from app.ledger.engine import LedgerError
from app.main import app
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetLabel
from app.models.attachment import Attachment
from app.models.ledger import AuditDigest, Conflict, Decision, DeriveRequest, RecordEvent
from app.models.schema import Schema
from app.models.workspace import Workspace
from tests.test_ledger_slice import T0, Slice, proposed_installation
from tests.test_ledger_transition import ATTEST, cut_over, token, twins

client = TestClient(app)
DAY = timedelta(days=1)


# --------------------------------------------------------------------------- field-level restrictions

def test_a_restricted_field_is_hidden_kept_on_edit_and_its_neighbour_is_not_named():
    ws = f"fld-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Fields"))
    db.flush()
    schema = Schema(uid=f"{ws}:pr", workspace_id=ws, name="Purchase", applies_to="objects",
                    attributes=[{"key": "supplier", "type": "string"},
                                {"key": "cost", "type": "number", "restricted": "costs"}])
    pump_type = engine.ensure_type(db, ws, "Ion Pump")
    db.add(schema)
    db.flush()
    pr = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=schema.uid, key=f"{ws}-PR", name="Purchase",
               type="Purchase", attributes={"supplier": "Agilent", "cost": 18400})
    secret = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=pump_type.uid, key=f"{ws}-SEC", name="Secret",
                   type="Ion Pump", attributes={"classification": "restricted:security_incident"})
    db.add_all([pr, secret])
    db.flush()
    db.add(Relation(workspace_id=ws, from_asset_uid=pr.uid, to_asset_uid=secret.uid, relation_type="about"))
    without, with_grant = token(db, ws), token(db, ws, ["costs", "security_incident"])
    db.commit()

    seen = client.get(f"/v1/assets/{pr.uid}", headers=without).json()
    assert seen["attributes"] == {"supplier": "Agilent"}
    assert secret.uid not in seen["outbound_relations"]
    full = client.get(f"/v1/assets/{pr.uid}", headers=with_grant).json()
    assert full["attributes"]["cost"] == 18400 and secret.uid in full["outbound_relations"]
    # Saving the form they saw neither erases nor sets the field they cannot see.
    resp = client.put(f"/v1/assets/{pr.uid}", headers=without,
                      json={"attributes": {"supplier": "Agilent Italia", "cost": 1}})
    assert resp.status_code == 200 and "cost" not in resp.json()["attributes"]
    db.refresh(pr)
    assert pr.attributes == {"supplier": "Agilent Italia", "cost": 18400}
    assert "18400" not in client.get("/v1/export/assets", headers=without).text
    found = client.get("/v1/hub/search", headers=without, params={"q": "18400"}).json()["assets"]
    assert pr.uid not in [a["uid"] for a in found]
    db.close()


# --------------------------------------------------------------------------- merges

def test_an_unmerge_puts_back_everything_the_merge_moved():
    s = Slice()
    db = SessionLocal()
    engine.ingest(db, s.insight, revision="i1", content=twins(s), observed_at=T0, parser="insight-fixture")
    a, b = s.rec(db, f"{s.fac}INV-A"), s.rec(db, f"{s.fac}INV-B")
    db.add(Relation(workspace_id=s.inv, from_asset_uid=b.uid, to_asset_uid=a.uid, relation_type="spare for"))
    db.commit()
    m = identity.merge(db, s.inv, "steward", a.uid, b.uid)
    db.commit()
    assert engine.resolve_ref(db, f"insight:object:{s.oid2}") == a.uid
    identity.unmerge(db, s.inv, "steward", m.decision_id, "they are two pumps after all")
    db.commit()
    db.refresh(b)
    assert b.record_status == "Active" and b.merged_into_uid is None
    assert engine.resolve_ref(db, f"insight:object:{s.oid2}") == b.uid
    assert not db.scalar(select(AssetLabel).where(AssetLabel.asset_uid == a.uid, AssetLabel.type == "former_key",
                                                  AssetLabel.value == b.key))
    assert db.scalar(select(Relation).where(Relation.from_asset_uid == b.uid, Relation.relation_type == "spare for"))
    # The candidate is back for a person to decide; the unmerge cannot be repeated.
    assert db.scalar(select(Conflict).where(Conflict.conflict_type == "identity_candidate",
                                            Conflict.detail["records"].contains([b.uid])))
    with pytest.raises(LedgerError):
        identity.unmerge(db, s.inv, "steward", m.decision_id)
    db.close()


def test_a_merge_of_units_installed_at_the_same_time_stands_with_a_blocking_item():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    [prop] = proposed_installation(db, s)
    service.confirm_installation(db, s.ws, "operator", prop["uid"])
    other = service.new_installation_claims(db, s.ws, "operator", s.pos(db, "GUNSIP02").uid, s.unit(db, "90001").uid,
                                            temporal.instant("2026-01-01", "day"))
    service.confirm_installation(db, s.ws, "operator", other)
    db.commit()
    identity.merge(db, s.inv, "steward", s.unit(db, "84321").uid, s.unit(db, "90001").uid)
    db.commit()
    survivor = s.unit(db, "84321")
    [item] = db.scalars(select(Conflict).where(Conflict.conflict_type == "merge_installation_overlap",
                                               Conflict.subject_uid == survivor.uid))
    assert item.severity == "blocking"
    # Ending one of the two installations resolves it.
    engine.apply_decisions(db, s.ws, "operator", [service.confirm_value(
        other, "attr:valid_until", temporal.instant("2026-02-01", "day"))])
    db.commit()
    assert db.get(Conflict, item.conflict_id) is None
    db.close()


# --------------------------------------------------------------------------- maintenance

def test_checksums_are_backfilled_and_the_derive_worker_drains_the_queue(tmp_path):
    ws = f"mnt-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Maintenance"))
    db.flush()
    f = tmp_path / "old.pdf"
    f.write_bytes(b"an attachment from before checksums")
    att = Attachment(uid=str(uuid.uuid4()), workspace_id=ws, filename="old.pdf", file_size=35, storage_path=str(f))
    db.add(att)
    db.commit()
    db.execute(text("UPDATE attachments SET sha256 = NULL WHERE uid = :u"), {"u": att.uid})
    db.commit()
    assert backfill_checksums() >= 1
    db.refresh(att)
    assert att.sha256 and len(att.sha256) == 64

    req = engine.request_derive(db, [ws], "test")
    db.commit()
    derive_worker(once=True, interval=0)
    db.refresh(req)
    assert req.status == "done"
    db.close()


def test_the_pilot_reversion_exports_what_changed_and_returns_the_domain_to_its_source():
    s = Slice()
    db = SessionLocal()
    s.inventory(db)
    d = cut_over(db, s)
    service.edit_value(db, s.inv, "rossi", s.unit(db).uid, "attr:argus_location", "Rack C3", "moved after cutover")
    db.commit()
    report = cutover.reversion_export(db, d.id, "platform-lead")
    assert any(x["kind"] == "confirm" and x["value"] == "Rack C3" for x in report["decisions"])
    assert len(report["sha256"]) == 64
    cutover.revert_pilot(db, d.id, "platform-lead", "pilot abandoned (U9)")
    db.commit()
    db.refresh(d)
    assert d.stage == "T1" and d.exited_at is None and not cutover.authoritative(db, s.inv)
    back = s.inventory(db, rev="i9", at=T0 + 5 * DAY, location="Rack D1")
    assert back["state"] == "published"                     # the stream is open again
    db.close()


# --------------------------------------------------------------------------- audit

def test_the_audit_log_is_append_only_and_its_digest_chain_finds_a_changed_day():
    db = SessionLocal()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE ledger_decisions SET reason = 'rewritten' WHERE seq = (SELECT min(seq) "
                        "FROM ledger_decisions)"))
        db.flush()
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM ledger_record_events WHERE seq = (SELECT min(seq) FROM ledger_record_events)"))
    db.rollback()

    yesterday = engine.now().date() - DAY
    if db.get(AuditDigest, yesterday) is None:
        noon = datetime.combine(yesterday, time(12), tzinfo=timezone.utc)
        db.add(RecordEvent(uid=f"audit-{secrets.token_hex(3)}", kind="status", before="Active", after="Retired",
                           cause="audit test", at=noon))
        db.flush()
    sealed = audit.seal_day(db, yesterday)
    db.commit()
    assert sealed.counts["record_events"] >= 1
    assert audit.verify(db)["ok"]

    start, end = audit._bounds(yesterday)
    victim = db.scalar(select(RecordEvent).where(RecordEvent.at >= start, RecordEvent.at < end).limit(1))
    original = victim.cause
    db.execute(text("ALTER TABLE ledger_record_events DISABLE TRIGGER ledger_record_events_append_only"))
    db.execute(text("UPDATE ledger_record_events SET cause = 'tampered' WHERE seq = :s"), {"s": victim.seq})
    db.commit()
    try:
        broken = audit.verify(db)
        assert not broken["ok"] and broken["day"] == yesterday.isoformat()
    finally:
        db.execute(text("UPDATE ledger_record_events SET cause = :c WHERE seq = :s"), {"c": original, "s": victim.seq})
        db.execute(text("ALTER TABLE ledger_record_events ENABLE TRIGGER ledger_record_events_append_only"))
        db.commit()
    assert audit.verify(db)["ok"]
    with pytest.raises(ValueError):
        audit.seal_day(db, yesterday - timedelta(days=500))
    db.close()


def test_a_record_has_an_audit_trail():
    s = Slice()
    db = SessionLocal()
    s.inventory(db)
    unit = s.unit(db)
    service.edit_value(db, s.inv, "rossi", unit.uid, "attr:argus_location", "Rack B13")
    headers = token(db, s.inv)
    db.commit()
    trail = client.get(f"/v1/ledger/records/{unit.uid}/audit", headers=headers).json()
    kinds = {(e["type"], e["kind"]) for e in trail}
    assert ("record", "created") in kinds and ("decision", "confirm") in kinds and ("identity", "bound") in kinds
    assert [e["at"] for e in trail] == sorted(e["at"] for e in trail)
    db.close()


# --------------------------------------------------------------------------- bulk changes

def test_a_bulk_change_is_previewed_applied_as_one_batch_and_undone(monkeypatch):
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    db.commit()
    spec = {"targets": {"type": "Control Device"}, "set": [{"predicate": "attr:argus_location", "value": "Tunnel"}]}
    decisions_before = db.scalar(select(text("count(*)")).select_from(Decision))
    change = bulk.preview(db, s.ws, "planner", spec, "devices are in the tunnel")
    db.commit()
    assert change.count == 3 and change.state == "previewed"
    assert db.scalar(select(text("count(*)")).select_from(Decision)) == decisions_before   # a dry run
    assert {c["after"] for r in change.preview for c in r["changes"]} == {"Tunnel"}

    monkeypatch.setattr(bulk, "APPROVAL_THRESHOLD", 2)
    waiting = bulk.apply(db, s.ws, change.id, "planner")
    assert waiting.state == "awaiting_approval"
    with pytest.raises(LedgerError):
        bulk.approve(db, s.ws, change.id, "planner")
    applied = bulk.approve(db, s.ws, change.id, "reviewer")
    db.commit()
    assert applied.state == "applied" and applied.approved_by == "reviewer"
    batch = list(db.scalars(select(Decision).where(Decision.batch_id == applied.batch_id)))
    assert len(batch) == 3
    assert s.dev(db, "GUNSIP01").attributes["argus_location"] == "Tunnel"

    bulk.undo(db, s.ws, change.id, "planner")
    db.commit()
    for name in ("GUNSIP00", "GUNSIP01", "GUNSIP02"):
        assert "argus_location" not in (s.dev(db, name).attributes or {})
    db.close()


def test_large_deletes_are_refused_in_favour_of_a_reviewed_bulk_change():
    ws = f"big-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Big"))
    db.flush()
    headers = token(db, ws)
    db.commit()
    uids = [str(uuid.uuid4()) for _ in range(bulk.APPROVAL_THRESHOLD + 1)]
    assert client.post("/v1/assets/bulk-delete", headers=headers, json={"uids": uids}).status_code == 409
    assert client.post("/v1/issues/bulk-delete", headers=headers, json={"uids": uids}).status_code == 409
    db.close()


# --------------------------------------------------------------------------- equipment

def test_lifecycle_custody_location_history_and_spares():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    [prop] = proposed_installation(db, s)
    service.confirm_installation(db, s.ws, "operator", prop["uid"])
    db.commit()
    installed, spare = s.unit(db, "84321"), s.unit(db, "90001")
    assert equipment.lifecycle(db, installed)["state"] == "Installed"
    with pytest.raises(LedgerError):
        equipment.set_lifecycle(db, s.inv, "rossi", installed.uid, "In stock")
    db.rollback()

    assert equipment.set_lifecycle(db, s.inv, "rossi", spare.uid, "In stock")["state"] == "In stock"
    db.commit()
    with pytest.raises(LedgerError):
        equipment.set_lifecycle(db, s.inv, "rossi", spare.uid, "Ordered")
    db.rollback()
    equipment.set_custodian(db, s.inv, "rossi", spare.uid, "bianchi@lnf.infn.it", "handed over for tests")
    equipment.set_custodian(db, s.inv, "bianchi", spare.uid, "stores@lnf.infn.it", "back to stores")
    service.edit_value(db, s.inv, "stores", spare.uid, "attr:argus_location", "Store 2, shelf 4")
    for name, value in (("is_designated_spare", True), ("product_model", "IPCMini")):
        service.edit_value(db, s.inv, "stores", spare.uid, f"attr:{name}", value)
    service.edit_value(db, s.ws, "controls", s.pos(db).uid, "attr:expected_product_model", "IPCMini")
    headers = token(db, s.inv)
    db.commit()

    custody = equipment.value_history(db, spare.uid, "custodian")
    assert custody["current"] == "stores@lnf.infn.it"
    assert [h["value"] for h in custody["history"]] == ["bianchi@lnf.infn.it", "stores@lnf.infn.it"]
    assert custody["history"][0]["until"] == custody["history"][1]["at"]
    location = equipment.value_history(db, spare.uid, "argus_location")
    assert [h["value"] for h in location["history"]] == ["Storage", "Store 2, shelf 4"]
    assert location["history"][0]["via"] == "insight"

    [avail] = equipment.spares(db, [s.inv], product_model="IPCMini")
    assert avail["uid"] == spare.uid and avail["available"]
    for_position = equipment.spares_for_position(db, s.pos(db).uid, [s.inv])
    assert for_position["basis"] == {"product_model": "IPCMini"}
    assert [x["uid"] for x in for_position["spares"]] == [spare.uid]
    state = client.get(f"/v1/equipment/{spare.uid}", headers=headers).json()
    assert state["lifecycle"]["state"] == "In stock" and state["designated_spare"]
    assert "Decommissioned" in state["lifecycle"]["allowed"]
    db.close()
