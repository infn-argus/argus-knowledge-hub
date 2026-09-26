"""Governing Other Equipment (asset-model-revision §5.5): the class
vocabulary, the report, promotion reviews and promotion."""
import secrets
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.ledger import engine, service
from app.models.ledger import Decision, RecordEvent
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services import asset_types, equipment_classes as ec
from tests.test_ledger_transition import token

client = TestClient(app)


@pytest.fixture(scope="module")
def catalogue():
    cat, other = f"cat-{secrets.token_hex(3)}", f"bl-{secrets.token_hex(3)}"
    db = SessionLocal()
    for w in (cat, other):
        db.add(Workspace(id=w, name=w))
    db.flush()
    asset_types.ensure_asset_types(db, cat, scope=asset_types.SCOPE_GLOBAL)   # the catalogue: shared types
    oe = db.query(Schema).filter_by(workspace_id=cat, name=ec.OTHER).one().uid
    headers, other_headers = token(db, cat), token(db, other)
    db.commit()
    db.close()
    return {"ws": cat, "headers": headers, "other": other, "other_headers": other_headers, "schema": oe}


def make(c, headers, attrs, status=201):
    uid = str(uuid.uuid4())
    r = client.post("/v1/assets", headers=headers, json={"uid": uid, "schema_uid": c["schema"], "key": f"OE-{uid[:8]}",
                                                          "name": "Box", "type": ec.OTHER, "attributes": attrs})
    assert r.status_code == status, r.text
    return uid if status == 201 else r.json()


def test_the_vocabulary_starts_from_the_sources_and_existing_types_are_not_assignable(catalogue):
    classes = {c["name"]: c for c in client.get("/v1/catalogue/equipment-classes", headers=catalogue["headers"]).json()}
    assert classes["PLC"]["status"] == "promoted" and classes["PLC"]["promoted_type"] == "PLC"
    assert classes["Cable"]["promoted_type"] == "Cable Run"
    assert {n for n, c in classes.items() if c["status"] == "active"} >= {"Scope", "Rack PDU", "Unclassified"}

    uid = make(catalogue, catalogue["headers"], {})
    db = SessionLocal()
    assert db.get(Asset, uid).attributes["equipment_class"] == "Unclassified"
    db.close()
    refused = make(catalogue, catalogue["headers"], {"equipment_class": "PLC"}, status=422)
    assert refused["detail"]["invariant"] == "I-CAT-1" and "use the type PLC" in refused["detail"]["error"]
    make(catalogue, catalogue["headers"], {"equipment_class": "Toaster"}, status=422)
    # Only the catalogue adds a class.
    assert client.post("/v1/catalogue/equipment-classes", headers=catalogue["other_headers"],
                       json={"name": "Toaster"}).status_code == 403
    name = f"Toaster {secrets.token_hex(2)}"
    assert client.post("/v1/catalogue/equipment-classes", headers=catalogue["headers"], json={"name": name}).status_code == 201
    make(catalogue, catalogue["headers"], {"equipment_class": name})
    assert client.post("/v1/catalogue/equipment-classes", headers=catalogue["headers"],
                       json={"name": "Camera"}).status_code == 422          # already a type


def test_the_unclassified_alert_follows_section_5_5():
    assert not ec.alert_for(9, 50)            # 18 %, but fewer than 10
    assert ec.alert_for(10, 100)              # 10 %, and 10
    assert not ec.alert_for(20, 1000)         # 2 %
    assert ec.alert_for(51, 100000)           # more than 50, whatever the share


def test_thresholds_open_a_review_and_a_declined_class_returns_only_with_a_new_trigger(catalogue):
    c, h = catalogue, catalogue["headers"]
    name = f"Scope {secrets.token_hex(2)}"
    client.post("/v1/catalogue/equipment-classes", headers=h, json={"name": name})
    make(c, h, {"equipment_class": name, "description": "Bandwidth: 1 GHz\nChannels: 4"})
    make(c, h, {"equipment_class": name, "description": "Bandwidth: 500 MHz"})
    for attr in ("Bandwidth", "Channels", "Sample rate"):
        assert client.post("/v1/catalogue/equipment-classes/requests", headers=c["other_headers"],
                           json={"class_name": name, "attribute": attr}).status_code == 201
    rep = client.get("/v1/catalogue/equipment-classes/report", headers=h).json()
    row = next(x for x in rep["classes"] if x["class"] == name)
    assert row["objects"] == 2 and row["sources"] == {"manual": 2}
    assert {"key": "bandwidth", "count": 2} in row["description_keys"]
    assert [t["kind"] for t in row["triggers"]] == ["requested_attributes"]
    assert rep["unclassified"]["count"] >= 1 and "rule" in rep["unclassified"]

    opened = client.post("/v1/catalogue/equipment-classes/reviews/run", headers=h).json()
    review = next(r for r in opened if r["class"] == name)
    assert all(r["class"] != name for r in client.post("/v1/catalogue/equipment-classes/reviews/run", headers=h).json())
    assert client.post(f"/v1/catalogue/equipment-classes/reviews/{review['id']}/decline", headers=h,
                       json={"reason": "three scopes do not need a type yet"}).status_code == 200
    assert all(r["class"] != name for r in client.post("/v1/catalogue/equipment-classes/reviews/run", headers=h).json())
    # Objects in a second workspace are a new kind of trigger.
    make(c, c["other_headers"], {"equipment_class": name})
    again = client.post("/v1/catalogue/equipment-classes/reviews/run", headers=h).json()
    assert any(r["class"] == name and {t["kind"] for t in r["triggers"]} >= {"workspaces"} for r in again)


def test_promotion_retypes_the_objects_in_place_and_retires_the_class(catalogue):
    c, h = catalogue, catalogue["headers"]
    name = f"Rack PDU {secrets.token_hex(2)}"
    client.post("/v1/catalogue/equipment-classes", headers=h, json={"name": name})
    ours = make(c, h, {"equipment_class": name})
    theirs = make(c, c["other_headers"], {"equipment_class": name})
    client.post("/v1/catalogue/equipment-classes/requests", headers=h, json={"class_name": name, "attribute": "Outlets"})
    # The other workspace switched to ledger-only: the retype still goes through.
    client.put("/v1/ledger/ledger-only", headers=c["other_headers"], json={"enabled": True, "reason": "S5"})
    type_name = f"Power Distribution Unit {secrets.token_hex(2)}"
    assert client.post("/v1/catalogue/equipment-classes/promote", headers=c["other_headers"],
                       json={"class_name": name, "type_name": type_name, "reason": "x"}).status_code == 403
    done = client.post("/v1/catalogue/equipment-classes/promote", headers=h,
                       json={"class_name": name, "type_name": type_name, "reason": "used in two beamlines"})
    assert done.status_code == 200, done.text
    assert done.json()["retyped"] == 2 and done.json()["attributes"] == ["Outlets"]
    db = SessionLocal()
    schema = db.get(Schema, done.json()["schema_uid"])
    parent = db.get(Schema, schema.parent_schema_uid)
    assert parent.name == "Asset" and schema.is_global and [a["name"] for a in schema.attributes] == ["Outlets"]
    for uid in (ours, theirs):
        rec = db.get(Asset, uid)
        assert rec.type == type_name and rec.schema_uid == schema.uid
        assert db.query(RecordEvent).filter_by(uid=uid, kind="retyped").count() == 1
        # The retype is a confirmed statement with the promotion's reason, in the object's own workspace.
        d = db.query(Decision).filter_by(subject_uid=uid, predicate="type", kind="confirm").one()
        assert d.value == type_name and d.workspace_id == rec.workspace_id and "used in two beamlines" in d.reason
    engine.rebuild(db, c["other"])
    assert db.get(Asset, theirs).type == type_name                      # a rebuild keeps it
    service.edit_values(db, c["ws"], "tester", ours, {"type": None}, reason="not a PDU after all")
    assert db.get(Asset, ours).type == ec.OTHER                          # withdrawing it undoes it
    db.rollback()
    db.close()
    refused = make(c, h, {"equipment_class": name}, status=422)
    assert type_name in refused["detail"]["error"]
