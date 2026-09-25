"""Relation rewrites in the legacy migration (§12.3 step 4, §6.2): the
deprecated verbs with a mechanical rewrite are rewritten; the others are
left for a person, with what to do."""
import secrets
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.ledger import engine
from app.main import app
from app.models.asset import Asset, Relation
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)


def record(db, ws, type_, key, attrs=None):
    a = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=engine.ensure_type(db, ws, type_).uid, key=key,
              name=key, type=type_, attributes=attrs or {})
    db.add(a)
    db.flush()
    return a


def edge(db, ws, a, rel, b):
    r = Relation(workspace_id=ws, from_asset_uid=a.uid, to_asset_uid=b.uid, relation_type=rel)
    db.add(r)
    db.flush()
    return r.id


def test_deprecated_edges_are_rewritten_or_left_for_a_person_and_roll_back():
    ws = f"edges-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    wp = record(db, ws, "Work Package", f"{ws}-WP3")
    structure = record(db, ws, "Accelerating Structure", f"{ws}-S1")
    pump, spare = record(db, ws, "Ion Pump", f"{ws}-SIP1", {"product_model": "VacIon 40"}), record(db, ws, "Ion Pump", f"{ws}-SIP9")
    device, line = record(db, ws, "Control Device", f"{ws}-DEV"), record(db, ws, "Serial Line", f"{ws}-LINE")
    pos1, pos2 = record(db, ws, "Equipment Position", f"{ws}-P1"), record(db, ws, "Equipment Position", f"{ws}-P2")
    edge(db, ws, structure, "assigned to", wp)
    edge(db, ws, spare, "spare for", pump)
    edge(db, ws, device, "on line", line)
    edge(db, ws, pos1, "spare for", pos2)
    headers = token(db, ws)
    db.commit()
    ids = {k: v.uid for k, v in {"wp": wp, "structure": structure, "pump": pump, "spare": spare}.items()}
    db.close()

    plan = client.post("/v1/migration/plans", headers=headers, json={}).json()
    rows = {r["legacy_type"] + ":" + r["legacy_key"].split(" ")[0].rsplit("-", 1)[-1]: r for r in plan["rows"]}
    assert rows["assigned to:S1"]["outcome"] == "M-EDGE"
    assert rows["spare for:SIP9"]["outcome"] == "M-EDGE"
    assert rows["on line:DEV"]["outcome"] == "M-EDGE-HOLD" and "Bus Segment" in rows["on line:DEV"]["warnings"][0]
    assert rows["spare for:P1"]["outcome"] == "M-EDGE-HOLD"
    edge_item = rows["spare for:SIP9"]["item"]
    assert client.post(f"/v1/migration/plans/{plan['id']}/items/{edge_item}/override", headers=headers,
                       json={"outcome": "M-POS", "reason": "no"}).status_code == 409

    before = client.get("/v1/ledger/registry/report", headers=headers).json()["counts"].get("deprecated", 0)
    applied = client.post(f"/v1/migration/plans/{plan['id']}/apply", headers=headers).json()
    assert applied["status"] == "verified", [(r["legacy_key"], r["status"], r["reason"]) for r in applied["rows"]]
    db = SessionLocal()
    structure = db.get(Asset, ids["structure"])
    assert structure.attributes["work_package"] == ids["wp"]
    assert db.query(Relation).filter_by(from_asset_uid=ids["structure"], relation_type="assigned to").count() == 0
    derived = db.query(Relation).filter_by(from_asset_uid=ids["structure"], relation_type="in work package").one()
    assert derived.to_asset_uid == ids["wp"] and derived.derivation == "derived"
    spare = db.get(Asset, ids["spare"])
    assert spare.attributes["is_designated_spare"] is True and spare.attributes["product_model"] == "VacIon 40"
    db.close()
    after = client.get("/v1/ledger/registry/report", headers=headers).json()["counts"].get("deprecated", 0)
    assert after == before - 2                   # the held edges are still there, for a person
    deep = client.post(f"/v1/migration/plans/{plan['id']}/verify", headers=headers).json()["invariants"]
    assert deep["deep_verification"]["I-MIG-6"]["ok"], deep["deep_verification"]["I-MIG-6"]
    assert deep["deep_verification"]["I-MIG-5"]["ok"]

    back = client.post(f"/v1/migration/plans/{plan['id']}/rollback", headers=headers, json={})
    assert back.status_code == 200, back.text
    db = SessionLocal()
    assert "work_package" not in db.get(Asset, ids["structure"]).attributes
    assert db.query(Relation).filter_by(from_asset_uid=ids["structure"], relation_type="assigned to").count() == 1
    assert db.query(Relation).filter_by(from_asset_uid=ids["structure"], relation_type="in work package").count() == 0
    assert "is_designated_spare" not in db.get(Asset, ids["spare"]).attributes
    db.close()
