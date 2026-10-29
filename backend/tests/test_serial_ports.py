"""A unit's ports read from a file (app/intake/assist.py `_ports`, app/intake/proposals.py): a converter's port
table becomes one proposed Equipment Port per port, with its settings — baud rate, framing, flow control, its
alias as its role and its TCP socket. On an existing unit, the ports it has get the values that differ as
proposals for review, and the ones it has not are offered, made only when the person chooses them."""
import json
import secrets as pysecrets
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models.asset import Asset, Relation
from app.models.ledger import Claim
from app.models.llm_config import LLMConfig
from app.models.workspace import Workspace
from app.packages import install as installer
from app.services import asset_types
from app.services import network_companions as nc
from tests.test_ledger_transition import token

client = TestClient(app)

# The Moxa's serial settings page, as the vision model reads it.
MOXA = {"type": "Serial Converter", "attributes": {"n_serial_ports": 4, "serial_modes": ["RS-232"]},
        "ports": [{"label": "Port 1", "kind": "RS-232", "baud": 9600, "data_bits": 7, "parity": "None", "stop_bits": 1,
                   "flow_control": "RTS/CTS", "other": "FIFO enabled"},
                  {"label": "Port 2", "kind": "RS-232", "baud": 9600, "data_bits": 8, "parity": "None", "stop_bits": 1,
                   "flow_control": "RTS/CTS", "other": "FIFO enabled"},
                  {"label": "Port 3", "kind": "RS-232", "baud": "9600", "data_bits": "8", "parity": "none",
                   "stop_bits": "1", "flow_control": "rts/cts", "other": "FIFO enabled"},
                  {"label": "Port 4", "kind": "RS-232", "alias": "VITARA+flame", "baud": 57600, "data_bits": 8,
                   "parity": "None", "stop_bits": 1, "flow_control": "XON/XOFF", "other": "FIFO enabled"}],
        "evidence": {"ports": "Port 4 VITARA+flame 57600 8 1 None Enable XON/XOFF RS-232"},
        "confidence": {"ports": 0.9}}


@pytest.fixture(scope="module")
def world():
    tag = pysecrets.token_hex(3)
    ws = f"serp-{tag}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    installer.install(db, ws, ["core-facility", "accelerator"], actor="test")
    db.add(LLMConfig(workspace_id=ws, base_url="https://gateway.example/v1", model="m-1", vision_model="v-1",
                     enabled=True, last_check_ok=True))
    headers = token(db, ws)
    db.commit()
    usable = asset_types.resolve_type_uids(db, ws)
    out = {"ws": ws, "headers": headers, "converter": usable["Serial Converter"], "port": usable["Equipment Port"],
           "tag": tag}
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


def _ports(out):
    return {c["attributes"]["port_label"]: c["attributes"] for c in out["companions"] if c["kind"] == "port"}


def test_a_port_table_becomes_one_proposed_port_per_port_with_its_settings(world, model):
    model(MOXA)
    out = client.post("/v1/intake/assist/asset", headers=world["headers"],
                      json={"text": "Moxa NPort serial settings", "draft": {"schema_uid": world["converter"],
                                                  "attributes": {"tcp_port_base": 4001}}}).json()
    ports = _ports(out)
    assert list(ports) == ["Port 1", "Port 2", "Port 3", "Port 4"]
    assert ports["Port 1"] == {"port_label": "Port 1", "port_kind": "RS-232", "baud": 9600, "framing": "7N1",
                               "flow_control": "RTS/CTS", "tcp_port": 4001, "port_settings": "FIFO enabled"}
    assert ports["Port 3"]["framing"] == "8N1" and ports["Port 3"]["baud"] == 9600       # read from strings too
    assert ports["Port 4"]["port_role"] == "VITARA+flame" and ports["Port 4"]["flow_control"] == "XON/XOFF"
    assert ports["Port 4"]["baud"] == 57600 and ports["Port 4"]["tcp_port"] == 4004
    assert out["fields"]["attributes.n_serial_ports"]["value"] == 4
    assert not any(k.startswith("attributes.baud") for k in out["fields"])           # never the unit's own


def test_the_ports_are_made_with_a_new_unit(world):
    uid = str(uuid.uuid4())
    r = client.post("/v1/assets", headers=world["headers"], json={
        "uid": uid, "schema_uid": world["converter"], "name": f"moxa-new-{world['tag']}", "attributes": {},
        "ports": [{"port_label": "Port 1", "port_kind": "RS-232", "baud": 9600, "framing": "7N1",
                   "flow_control": "RTS/CTS", "tcp_port": 4001}]})
    assert r.status_code in (200, 201), r.text
    db = SessionLocal()
    port = nc.ports_of(db, uid)[0]
    assert port.attributes["baud"] == 9600 and port.attributes["framing"] == "7N1"
    assert port.attributes["flow_control"] == "RTS/CTS" and port.attributes["tcp_port"] == 4001
    db.close()


def test_on_an_existing_unit_known_ports_get_proposals_and_new_ones_are_offered(world, model):
    unit = str(uuid.uuid4())
    r = client.post("/v1/assets", headers=world["headers"], json={
        "uid": unit, "schema_uid": world["converter"], "name": f"moxa-{world['tag']}",
        "attributes": {"tcp_port_base": 4001},
        "ports": [{"port_label": "Port 1", "port_kind": "RS-232", "baud": 19200, "framing": "7N1"}]})
    assert r.status_code in (200, 201), r.text
    model(MOXA)
    out = client.post(f"/v1/intake/propose/asset/{unit}", headers=world["headers"],
                      data={"text": "the serial settings page"}).json()
    offered = {c["attributes"]["port_label"] for c in out["companions"]}
    assert offered == {"Port 2", "Port 3", "Port 4"}
    changes = {c["field"]: c for c in out["port_changes"]}
    assert changes["baud"]["value"] == 9600 and changes["baud"]["current"] == 19200
    assert "framing" not in changes                                   # already 7N1
    db = SessionLocal()
    port1 = nc.ports_of(db, unit)[0]
    claim = db.scalar(select(Claim).where(Claim.predicate == "attr:baud", Claim.method == "ai_extracted",
                                          Claim.source_ref == f"uid:{port1.uid}"))
    assert claim is not None and claim.value == 9600                  # waits in the review queue
    assert db.get(Asset, port1.uid).attributes["baud"] == 19200         # nothing changed yet
    db.close()

    chosen = [c["attributes"] for c in out["companions"]]
    made = client.post(f"/v1/intake/propose/asset/{unit}/companions", headers=world["headers"],
                       json={"ports": chosen, "run_id": out["run_id"]})
    assert made.status_code == 201, made.text
    assert len(made.json()["ports"]) == 3
    db = SessionLocal()
    ports = {p.attributes["port_label"]: p for p in nc.ports_of(db, unit)}
    assert set(ports) == {"Port 1", "Port 2", "Port 3", "Port 4"}
    assert ports["Port 4"].attributes["port_role"] == "VITARA+flame" and ports["Port 4"].attributes["tcp_port"] == 4004
    rel = db.scalar(select(Relation).where(Relation.from_asset_uid == ports["Port 4"].uid))
    assert rel.relation_type == "port of" and rel.to_asset_uid == unit
    db.close()

    again = client.post(f"/v1/intake/propose/asset/{unit}/companions", headers=world["headers"],
                        json={"ports": [{"port_label": "port 2", "port_kind": "RS-232"}]})
    assert again.status_code == 409 and "port 2" in again.json()["detail"]
    empty = client.post(f"/v1/intake/propose/asset/{unit}/companions", headers=world["headers"], json={})
    assert empty.status_code == 422
