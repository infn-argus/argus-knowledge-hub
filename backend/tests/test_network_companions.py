"""A new record's network port and address (app/services/network_companions.py): a MAC read from a nameplate or a
description becomes a proposed Equipment Port, an address a proposed Address Record; networked types are offered a
port; the port and address are saved with the record, in one transaction, linked to it."""
import json
import secrets as pysecrets
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models.asset import Asset, Relation
from app.models.llm_config import LLMConfig
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.packages import install as installer
from app.services import asset_types
from app.services import network_companions as nc
from tests.test_ledger_transition import token

client = TestClient(app)


@pytest.fixture(scope="module")
def world():
    tag = pysecrets.token_hex(3)
    ws = f"netc-{tag}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    installer.install(db, ws, ["core-facility", "accelerator"], actor="test")
    db.add(LLMConfig(workspace_id=ws, base_url="https://gateway.example/v1", model="m-1", vision_model="v-1",
                     enabled=True, last_check_ok=True))
    headers = token(db, ws)
    db.commit()
    usable = asset_types.resolve_type_uids(db, ws)
    out = {"ws": ws, "headers": headers, "camera": usable["Camera"], "pump": usable["Ion Pump"],
           "server": usable["Server"], "port": usable["Equipment Port"], "tag": tag}
    db.close()
    yield out
    db = SessionLocal()
    from app.ledger.audit import allow_purge
    allow_purge(db)
    db.delete(db.get(Workspace, ws))
    db.commit()
    db.close()


@pytest.fixture
def model(monkeypatch):
    def answer(reply):
        monkeypatch.setattr("app.services.llm.complete_structured",
                            lambda endpoint, system, user, max_tokens=512: json.dumps(reply))
        monkeypatch.setattr("app.services.llm.look",
                            lambda endpoint, image, mime, system, user: json.dumps(reply))
    return answer


def test_a_mac_is_read_in_any_usual_spelling():
    for spelling in ("00:30:53:37:86:28", "00-30-53-37-86-28", "0030.5337.8628", "003053378628", "00:30:53:37:86:28 "):
        assert nc.normalise_mac(spelling) == "00:30:53:37:86:28", spelling
    for bad in ("00:30:53:37:86", "zz:30:53:37:86:28", "00:00:00:00:00:00", "MAC 1", None):
        assert nc.normalise_mac(bad) is None, bad


def test_networked_equipment_is_offered_a_port_and_the_rest_is_not(world):
    db = SessionLocal()
    assert nc.networked(db, db.get(Schema, world["camera"]))
    assert nc.networked(db, db.get(Schema, world["server"]))
    assert not nc.networked(db, db.get(Schema, world["pump"]))
    assert not nc.networked(db, db.get(Schema, world["port"]))
    db.close()
    g = client.post("/v1/intake/guide/asset", headers=world["headers"], json={"draft": {"schema_uid": world["camera"]}}).json()
    assert g["network_port"]["offered"] is True and g["network_port"]["port_type_uid"] == world["port"]
    g = client.post("/v1/intake/guide/asset", headers=world["headers"], json={"draft": {"schema_uid": world["pump"]}}).json()
    assert g["network_port"]["offered"] is False


def test_a_mac_on_the_nameplate_becomes_a_proposed_port_not_a_field(world, model):
    text = f"Basler a2A1920-51gmBAS camera, S/N 4070{world['tag']}, MAC: 00:30:53:{world['tag'][:2]}:86:28, ip 10.60.2.15"
    mac = f"00:30:53:{world['tag'][:2]}:86:28".upper()
    model({"type": "Camera", "name": "Basler camera", "attributes": {"manufacturer": "Basler", "model": "a2A1920-51gmBAS",
                                                                     "mac": mac},
           "network": {"mac": f"00:30:53:{world['tag'][:2]}:86:28", "ip": "10.60.2.15"},
           "evidence": {"type": "camera", "network.mac": f"00:30:53:{world['tag'][:2]}:86:28", "network.ip": "10.60.2.15"},
           "confidence": {"type": 0.8, "network.mac": 0.95, "network.ip": 0.9}})
    out = client.post("/v1/intake/assist/asset", headers=world["headers"], json={"text": text}).json()
    assert "attributes.mac" not in out["fields"]                      # Camera has no MAC of its own
    port = next(c for c in out["companions"] if c["kind"] == "port")
    assert port["attributes"]["mac"] == mac and port["selected"] and port["grounded"]
    assert port["relation"] == "port of" and port["type_uid"] == world["port"]
    addr = next(c for c in out["companions"] if c["kind"] == "address")
    assert addr["attributes"] == {"ip": "10.60.2.15"}


def test_the_camera_and_its_port_and_address_are_saved_together(world):
    uid = str(uuid.uuid4())
    mac = f"00:30:53:{world['tag'][2:4]}:86:29".upper()
    r = client.post("/v1/assets", headers=world["headers"], json={
        "uid": uid, "schema_uid": world["camera"], "name": "Basler camera SM-9", "attributes": {"manufacturer": "Basler"},
        "ports": [{"port_label": "eth0", "port_kind": "RJ45", "mac": mac.lower().replace(":", "-")}],
        "addresses": [{"ip": "10.60.2.16", "hostname": "cam-sm9"}]})
    assert r.status_code == 201 or r.status_code == 200, r.text
    db = SessionLocal()
    port_rel = db.scalar(select(Relation).where(Relation.to_asset_uid == uid, Relation.relation_type == "port of"))
    assert port_rel is not None
    port = db.get(Asset, port_rel.from_asset_uid)
    assert port.type == "Equipment Port" and port.attributes["mac"] == mac and port.workspace_id == world["ws"]
    assert port.name == "Basler camera SM-9 · eth0"
    addr_rel = db.scalar(select(Relation).where(Relation.from_asset_uid == uid, Relation.relation_type == "described by"))
    addr = db.get(Asset, addr_rel.to_asset_uid)
    assert addr.type == "Address Record" and addr.attributes["ip"] == "10.60.2.16" and addr.attributes["hostname"] == "cam-sm9"
    db.close()
    # The same MAC again is refused, and nothing of the second record is kept.
    uid2 = str(uuid.uuid4())
    r = client.post("/v1/assets", headers=world["headers"], json={
        "uid": uid2, "schema_uid": world["camera"], "name": "Another camera", "attributes": {},
        "ports": [{"mac": mac}]})
    assert r.status_code == 422 and "already on" in r.text
    db = SessionLocal()
    assert db.get(Asset, uid2) is None
    db.close()


def test_an_already_recorded_mac_is_not_proposed_again(world, model):
    db = SessionLocal()
    mac = next(a.attributes["mac"] for a in db.scalars(select(Asset).where(Asset.workspace_id == world["ws"],
                                                                         Asset.type == "Equipment Port")))
    db.close()
    model({"type": "Camera", "name": "Basler camera", "attributes": {}, "network": {"mac": mac},
           "evidence": {"network.mac": mac}, "confidence": {"network.mac": 0.9}})
    out = client.post("/v1/intake/assist/asset", headers=world["headers"], json={"text": f"camera MAC {mac}"}).json()
    assert not [c for c in out["companions"] if c["kind"] == "port"]
    assert any(d["field"] == "network.mac" and "already on" in d["reason"] for d in out["dropped"])


def test_a_bad_mac_or_address_is_refused_and_nothing_is_saved(world):
    for extra in ({"ports": [{"mac": "not-a-mac"}]}, {"addresses": [{"ip": "999.1.1.1"}]}):
        uid = str(uuid.uuid4())
        r = client.post("/v1/assets", headers=world["headers"],
                        json={"uid": uid, "schema_uid": world["camera"], "name": "x", "attributes": {}, **extra})
        assert r.status_code == 422, r.text
        db = SessionLocal()
        assert db.get(Asset, uid) is None
        db.close()
