"""Legacy migration (asset-model-revision §12): inferred records become
Positions, Equipment and Installations, with a report first, owners'
overrides, an apply that checks itself, and a rollback until finalized."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.ledger import engine, legacy, lookup
from app.main import app
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetLabel, AssetTicket
from app.models.attachment import Attachment
from app.models.import_snapshot import ImportSnapshot
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)
NOW = datetime.now(timezone.utc)


class Legacy:
    """A beamline workspace as the old importer left it, and an inventory."""

    def __init__(self):
        self.fac = f"L{secrets.token_hex(3).upper()}"
        self.ws, self.inv, self.other = f"leg-{self.fac.lower()}", f"inv-{self.fac.lower()}", f"oth-{self.fac.lower()}"
        db = SessionLocal(expire_on_commit=False)       # the fixture's records are read after it closes
        for w in (self.ws, self.inv, self.other):
            db.add(Workspace(id=w, name=w))
        db.flush()
        self.headers = token(db, self.ws)
        # The importer's last run wrote "run-2"; an object only "run-1" wrote is stale.
        self.pos = self.rec(db, "vac:SIP01", "Ion Pump", {})
        self.matched = self.rec(db, "vac:SIP02", "Ion Pump", {}, person={"serial": f"84321-{self.fac}"})
        # The inventory's record of the same pump (the plan's inventory workspace is the beamline's own here).
        self.inventory = self.asset(db, self.ws, f"{self.fac}INV-84321", "Ion Pump",
                                    {"serial": f"84321-{self.fac}", "manufacturer": "Agilent"})
        self.created = self.rec(db, "vac:SIP03", "Ion Pump", {"manufacturer": "Agilent"},
                                person={"serial": f"99001-{self.fac}", "installed_on": "2024-03-05"})
        self.mixed = self.rec(db, "cam:AC101", "Camera", {})
        att = Attachment(uid=str(uuid.uuid4()), workspace_id=self.ws, asset_uid=self.mixed.uid, filename="ac101.jpg",
                         storage_path="/dev/null")
        db.add(att)
        db.flush()
        db.add(AssetLabel(uid=str(uuid.uuid4()), asset_uid=self.mixed.uid, type="serial", value=f"CAM-7-{self.fac}",
                          issuer="photo-identification", verified=False, metadata_json={"attachment_uid": att.uid},
                          created_at=NOW, updated_at=NOW))
        self.stale = self.rec(db, "old:GAUGE9", "Vacuum Gauge", {}, run="run-1")
        db.add(Relation(workspace_id=self.ws, from_asset_uid=self.stale.uid, to_asset_uid=self.pos.uid,
                        relation_type="connected to"))
        self.element = self.rec(db, "mag:QUA01", "Quadrupole", {})
        self.blocked = self.rec(db, "vac:SIP04", "Ion Pump", {}, person={"serial": f"55555-{self.fac}"})
        self.asset(db, self.other, f"{self.fac}OTH-1", "Ion Pump", {"serial": f"55555-{self.fac}", "argus_keywords": ["inferred"]})
        db.add(AssetTicket(uid=str(uuid.uuid4()), asset_uid=self.matched.uid, ticket_key=f"{self.fac}-1",
                           summary="Pump trips", type="Bug", status="Done", created=NOW, updated=NOW))
        db.commit()
        db.close()

    def asset(self, db, ws, key, type_, attrs):
        a = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=engine.ensure_type(db, ws, type_).uid, key=key,
                  name=key, type=type_, attributes=attrs)
        db.add(a)
        db.flush()
        return a

    def rec(self, db, tag, type_, stated, person=None, run="run-2"):
        written = {**stated, "argus_keywords": ["inferred"], "argus_facility": self.fac, "argus_source": "epik8s",
                   "argus_source_ref": run}
        a = self.asset(db, self.ws, f"{self.fac}:AST:{tag}", type_, {**written, **(person or {})})
        db.add(ImportSnapshot(asset_uid=a.uid, source="epik8s", values={**written, "__name__": a.name},
                              source_ref=run, updated_at=NOW - timedelta(days=2 if run == "run-1" else 1)))
        db.flush()
        return a


def outcomes(plan):
    return {r["legacy_key"].split(":AST:")[1]: r for r in plan["rows"]}


def test_the_plan_classifies_every_inferred_record_and_changes_nothing():
    L = Legacy()
    resp = client.post("/v1/migration/plans", headers=L.headers, json={})
    assert resp.status_code == 201, resp.text
    plan = resp.json()
    rows = outcomes(plan)
    assert {k: r["outcome"] for k, r in rows.items()} == {
        "vac:SIP01": "M-POS", "vac:SIP02": "M-PHYS", "vac:SIP03": "M-PHYS", "cam:AC101": "M-MIXED",
        "old:GAUGE9": "M-RETIRE", "mag:QUA01": "M-FUNC", "vac:SIP04": "M-BLOCK"}
    phys = rows["vac:SIP02"]
    assert phys["evidence"]["identifier_matches"] == [L.inventory.uid]
    assert next(a for a in phys["actions"] if a["do"] == "equipment")["match"] == L.inventory.uid
    assert next(a for a in rows["vac:SIP03"]["actions"] if a["do"] == "installation")["valid_from"]["precision"] == "day"
    assert rows["vac:SIP04"]["reviewer_required"] and "also held by" in rows["vac:SIP04"]["warnings"][0]
    assert rows["vac:SIP01"]["actions"][0]["key"] == f"{L.fac}:POS:SIP01"
    csv = client.get(f"/v1/migration/plans/{plan['id']}/report.csv", headers=L.headers)
    assert csv.status_code == 200 and csv.text.startswith("legacy_uid,legacy_key") and f"E-SER(serial=84321-{L.fac}" in csv.text
    db = SessionLocal()
    assert db.get(Asset, L.pos.uid).type == "Ion Pump"                   # nothing applied
    db.close()
    gate = client.get("/v1/migration/gate", headers=L.headers).json()
    assert not gate["ok"] and gate["blocked"] and gate["mixed_open"]


def test_apply_splits_records_routes_dependents_and_holds_the_invariants():
    L = Legacy()
    plan = client.post("/v1/migration/plans", headers=L.headers, json={"inventory_workspace_id": L.ws}).json()
    rows = outcomes(plan)
    # The owners accept the collision as a pure control identity; it needs a reason.
    item = rows["vac:SIP04"]["item"]
    assert client.post(f"/v1/migration/plans/{plan['id']}/items/{item}/override", headers=L.headers,
                       json={"outcome": "M-POS", "reason": " "}).status_code == 409
    assert client.post(f"/v1/migration/plans/{plan['id']}/items/{item}/override", headers=L.headers,
                       json={"outcome": "M-FUNC", "reason": "no"}).status_code == 409
    over = client.post(f"/v1/migration/plans/{plan['id']}/items/{item}/override", headers=L.headers,
                       json={"outcome": "M-POS", "reason": "the other pump is a stale duplicate"})
    assert over.status_code == 200 and over.json()["override"]["reason"]

    applied = client.post(f"/v1/migration/plans/{plan['id']}/apply", headers=L.headers)
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["status"] == "verified", result["invariants"]
    assert all(r["status"] == "applied" for r in result["rows"]), [(r["legacy_key"], r["reason"]) for r in result["rows"]]

    db = SessionLocal()
    pos = db.get(Asset, L.pos.uid)
    assert pos.type == "Equipment Position" and pos.key == f"{L.fac}:POS:SIP01"
    assert pos.attributes["equipment_class"] == "Ion Pump"
    # The old key still resolves, to the same record.
    assert lookup.resolve(db, f"{L.fac}:AST:vac:SIP01", [L.ws])["uid"] == L.pos.uid

    by_key = {r["legacy_key"]: r for r in result["rows"]}
    matched = by_key[f"{L.fac}:AST:vac:SIP02"]["applied"]
    assert matched["equipment"] == L.inventory.uid and not matched["equipment_created"]
    inst = db.get(Asset, matched["installation"])
    assert inst.attributes["installation_status"] == "Confirmed"
    # Its ticket stays on the position (I-TKT-2: counted once).
    assert db.query(AssetTicket).filter_by(asset_uid=L.matched.uid).count() == 1

    created = by_key[f"{L.fac}:AST:vac:SIP03"]["applied"]
    eq = db.get(Asset, created["equipment"])
    assert created["equipment_created"] and eq.record_status == "Active" and eq.attributes["serial"] == f"99001-{L.fac}"

    mixed = by_key[f"{L.fac}:AST:cam:AC101"]["applied"]
    assert db.get(Asset, mixed["equipment"]).record_status == "Provisional"
    assert db.get(Asset, mixed["installation"]).attributes["installation_status"] == "Proposed"
    assert len(mixed["moved_labels"]) == 1 and len(mixed["moved_attachments"]) == 1
    assert db.get(Attachment, mixed["moved_attachments"][0]).asset_uid == mixed["equipment"]

    stale = db.get(Asset, L.stale.uid)
    assert stale.record_status == "Retired"
    assert db.query(Relation).filter((Relation.from_asset_uid == L.stale.uid) | (Relation.to_asset_uid == L.stale.uid)).count() == 0
    assert db.get(Asset, L.element.uid).type == "Quadrupole"
    db.close()
    assert client.get("/v1/migration/gate", headers=L.headers).json()["ok"]
    # A migrated record is not planned again.
    again = client.post("/v1/migration/plans", headers=L.headers, json={}).json()
    assert again["rows"] == []


def test_a_record_changed_after_planning_is_stale_and_nothing_of_it_moves():
    L = Legacy()
    plan = client.post("/v1/migration/plans", headers=L.headers, json={}).json()
    db = SessionLocal()
    record = db.get(Asset, L.pos.uid)
    record.attributes = {**record.attributes, "argus_location": "Rack C3"}
    db.commit()
    db.close()
    result = client.post(f"/v1/migration/plans/{plan['id']}/apply", headers=L.headers).json()
    row = next(r for r in result["rows"] if r["legacy_uid"] == L.pos.uid)
    assert row["status"] == "stale" and result["status"] == "needs_attention"
    db = SessionLocal()
    assert db.get(Asset, L.pos.uid).type == "Ion Pump"
    db.close()


def test_rollback_restores_the_legacy_rows_and_finalize_closes_the_window():
    L = Legacy()
    plan = client.post("/v1/migration/plans", headers=L.headers, json={}).json()
    applied = client.post(f"/v1/migration/plans/{plan['id']}/apply", headers=L.headers).json()
    by_key = {r["legacy_key"]: r for r in applied["rows"]}
    created = by_key[f"{L.fac}:AST:vac:SIP03"]["applied"]
    mixed = by_key[f"{L.fac}:AST:cam:AC101"]["applied"]
    back = client.post(f"/v1/migration/plans/{plan['id']}/rollback", headers=L.headers, json={})
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "rolled_back"
    db = SessionLocal()
    pos = db.get(Asset, L.pos.uid)
    assert pos.type == "Ion Pump" and pos.key == f"{L.fac}:AST:vac:SIP01"
    assert db.query(AssetLabel).filter_by(asset_uid=L.pos.uid, type="former_key").count() == 0
    assert db.get(Asset, created["equipment"]).record_status == "Retired"
    assert db.get(Asset, created["installation"]).record_status == "Retired"
    assert db.get(Attachment, mixed["moved_attachments"][0]).asset_uid == L.mixed.uid
    assert db.get(Asset, L.stale.uid).record_status == "Active"
    assert db.query(Relation).filter_by(from_asset_uid=L.stale.uid, to_asset_uid=L.pos.uid).count() == 1
    db.close()

    # Planned again from scratch; finalized, it can no longer be undone.
    plan2 = client.post("/v1/migration/plans", headers=L.headers, json={}).json()
    assert len(plan2["rows"]) == 7
    item = outcomes(plan2)["vac:SIP04"]["item"]
    client.post(f"/v1/migration/plans/{plan2['id']}/items/{item}/override", headers=L.headers,
                json={"outcome": "M-POS", "reason": "duplicate"})
    assert client.post(f"/v1/migration/plans/{plan2['id']}/finalize", headers=L.headers).status_code == 409
    assert client.post(f"/v1/migration/plans/{plan2['id']}/apply", headers=L.headers).json()["status"] == "verified"
    done = client.post(f"/v1/migration/plans/{plan2['id']}/finalize", headers=L.headers)
    assert done.status_code == 200 and done.json()["status"] == "finalized"
    assert client.post(f"/v1/migration/plans/{plan2['id']}/rollback", headers=L.headers, json={}).status_code == 409


def test_a_domain_is_not_frozen_while_its_legacy_records_are_unmigrated():
    from app.ledger import cutover
    from app.ledger.engine import LedgerError
    L = Legacy()
    db = SessionLocal()
    d = cutover.create_domain(db, L.ws, f"pilot-{L.fac}", "Vacuum equipment", stream_ids=[])
    cutover.advance(db, d.id, "T1", "steward")
    cutover.set_stewards(db, d.id, "owner", "steward", "backup")
    from tests.test_ledger_transition import ENTRY
    with pytest.raises(LedgerError, match="No legacy record is M-BLOCK"):
        cutover.freeze(db, d.id, "steward", {"object_history_id": 1}, {"objects": []}, **ENTRY)
    # The legacy criterion is never waived.
    with pytest.raises(LedgerError, match="cannot be waived"):
        cutover.freeze(db, d.id, "steward", {"object_history_id": 1}, {"objects": []},
                       attestations=ENTRY["attestations"], waivers={**ENTRY["waivers"], "legacy": "pilot"})
    db.rollback()
    db.close()
