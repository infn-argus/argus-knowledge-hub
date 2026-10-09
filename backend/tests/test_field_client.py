"""Server foundations for the field client (asset-model-revision §24.3): the
committed contract, the minimum client version, the device registry and the
universal links."""
import json
import secrets
import uuid

from fastapi.testclient import TestClient

from app import contract
from app.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.document import Document
from app.models.issue import Issue
from app.models.workspace import Workspace
from app.services import asset_types
from tests.test_ledger_transition import token

client = TestClient(app)


def test_the_committed_contract_is_the_api():
    """Regenerate with `python -m app.contract` when the API changes on purpose."""
    spec = contract.full()
    committed = json.loads((contract.ROOT / "openapi.json").read_text())
    assert committed == json.loads(contract.dump(spec)), "openapi/openapi.json is stale: run python -m app.contract"
    field = json.loads((contract.ROOT / "field-client.json").read_text())
    assert field == json.loads(contract.dump(contract.field_subset(spec))), "openapi/field-client.json is stale"
    assert set(field["paths"]) <= set(spec["paths"])


def test_a_client_below_its_minimum_version_is_told_to_update(monkeypatch):
    monkeypatch.setitem(__import__("app.services.api_policy", fromlist=["x"]).MINIMUM_CLIENT_VERSIONS,
                        "flutter", "1.4.0")
    old = client.get("/v1/meta/api", headers={"X-ARGUS-Client": "flutter/1.3.9/12"})
    assert old.status_code == 426 and old.json()["detail"]["code"] == "client_too_old"
    assert old.json()["detail"]["minimum"] == "1.4.0"
    assert client.get("/v1/meta/api", headers={"X-ARGUS-Client": "flutter/1.4.0/13"}).status_code == 200
    assert client.get("/v1/meta/api").status_code == 200                 # the web sends no client header


def world():
    ws = f"field-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    types = asset_types.ensure_asset_types(db, ws).uids

    def asset(type_, key, attrs=None):
        a = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=types[type_], key=key, name=key, type=type_,
                  attributes=attrs or {})
        db.add(a)
        db.flush()
        return a
    serial = f"SN-{ws}"
    pump = asset("Ion Pump", f"{ws}-IP-1", {"serial": serial, "manufacturer": "Agilent", "inventory_number": f"INV-{ws}"})
    twin = asset("Ion Pump", f"{ws}-IP-2", {"serial": serial, "manufacturer": "Gamma"})
    position = asset("Quadrupole", f"{ws}-QUA-1")             # a functional element: a Position
    secret = asset("Ion Pump", f"{ws}-SEC", {"classification": "restricted:security_incident", "serial": serial})
    issue = Issue(uid=str(uuid.uuid4()), workspace_id=ws, title="Pump tripped", attributes={})
    doc = Document(uid=str(uuid.uuid4()), workspace_id=ws, code=f"PROC-{secrets.token_hex(3)}", title="Bakeout")
    db.add_all([issue, doc])
    headers = token(db, ws)
    db.commit()
    ids = {"ws": ws, "headers": headers, "pump": pump.uid, "position": position.uid, "secret": secret.uid,
           "issue": issue.uid, "doc": doc.uid, "doc_code": doc.code,
           "twin": twin.uid, "serial": serial}
    db.close()
    return ids


def resolve(w, path):
    return client.get("/v1/links/resolve", params={"path": path}, headers=w["headers"])


def test_universal_links_open_what_the_caller_may_read_and_nothing_else():
    w = world()
    r = resolve(w, f"/asset/{w['pump']}")
    assert r.status_code == 200 and r.json()["kind"] == "asset" and r.json()["web_path"] == f"/assets/{w['pump']}"
    assert resolve(w, f"https://argus.example/position/{w['position']}").json()["kind"] == "position"
    assert resolve(w, f"/ticket/{w['issue']}").json()["web_path"] == f"/tickets/{w['issue']}"
    assert resolve(w, f"/document/{w['doc_code']}").json()["uid"] == w["doc"]
    missing = resolve(w, f"/asset/{uuid.uuid4()}")
    hidden = resolve(w, f"/asset/{w['secret']}")
    assert missing.status_code == hidden.status_code == 404
    assert missing.json() == hidden.json()                                  # indistinguishable (I-ACL-1)
    assert resolve(w, "/somewhere/else").status_code == 422
    assert resolve(w, f"/lookup/{w['ws']}-IP-1").json()["uid"] == w["pump"]


def test_A67_a_label_value_opens_its_one_holder_and_a_shared_serial_opens_none():
    w = world()
    one = resolve(w, f"/lookup/INV-{w['ws']}")
    assert one.status_code == 200 and one.json()["uid"] == w["pump"]
    shared = resolve(w, f"/lookup/{w['serial']}")
    assert shared.status_code == 409 and shared.json()["detail"]["code"] == "ambiguous"
    candidates = {c["uid"] for c in shared.json()["detail"]["candidates"]}
    assert candidates == {w["pump"], w["twin"]}                           # the restricted holder is not offered
    assert resolve(w, "/lookup/NO-SUCH-LABEL").status_code == 404
    ctx = client.get(f"/v1/hub/assets/{w['position']}/context", headers=w["headers"]).json()
    assert ctx["nature"] == "position"


def test_a_revoked_device_is_told_to_wipe_itself():
    w = world()
    d = client.post("/v1/devices", headers=w["headers"],
                    json={"installation_id": "inst-1", "platform": "android", "app_version": "0.1.0"}).json()
    again = client.post("/v1/devices", headers=w["headers"],
                        json={"installation_id": "inst-1", "platform": "android", "app_version": "0.1.1"}).json()
    assert again["id"] == d["id"] and again["app_version"] == "0.1.1"          # one device per installation
    h = {**w["headers"], "X-ARGUS-Device": d["id"]}
    assert client.get("/v1/me", headers=h).status_code == 200
    assert client.post(f"/v1/devices/{d['id']}/revoke", headers=w["headers"], json={"reason": ""}).status_code == 422
    assert client.post(f"/v1/devices/{d['id']}/revoke", headers=w["headers"],
                       json={"reason": "phone lost"}).status_code == 200
    r = client.get("/v1/me", headers=h)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "revoked"
    listed = client.get("/v1/devices", headers=w["headers"]).json()
    assert listed[0]["revoke_reason"] == "phone lost"
    other = world()
    assert client.post(f"/v1/devices/{d['id']}/revoke", headers=other["headers"],
                       json={"reason": "x"}).status_code == 404                  # not someone else's device


def _label(w, asset_uid, type_, value):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    r = client.post(f"/v1/assets/{asset_uid}/labels", headers=w["headers"], json={
        "uid": str(uuid.uuid4()), "type": type_, "value": value, "issuer": "field", "created_at": now, "updated_at": now})
    assert r.status_code == 201, r.text
    return r.json()


def test_a_scan_finds_every_kind_of_label_a_qr_code_first():
    w = world()
    tag = secrets.token_hex(3)
    _label(w, w["pump"], "barcode", f"BC-{tag}")
    assert resolve(w, f"/lookup/BC-{tag}").json()["uid"] == w["pump"], "a barcode label, not only a QR code"
    _label(w, w["twin"], "asset_tag", f"tag-{tag}")
    assert resolve(w, f"/lookup/TAG-{tag}").json()["uid"] == w["twin"], "a hand-typed serial may differ in case"
    # The same value as one record's QR code and another's serial: the QR code is what a scan means.
    _label(w, w["pump"], "qrcode", f"SHARED-{tag}")
    _label(w, w["twin"], "serial", f"SHARED-{tag}")
    assert resolve(w, f"/lookup/SHARED-{tag}").json()["uid"] == w["pump"]
    # A QR code that is a number is the label, not an Insight objectId.
    number = str(900000000 + int(tag, 16) % 99999)
    _label(w, w["twin"], "qrcode", number)
    assert resolve(w, f"/lookup/{number}").json()["uid"] == w["twin"]


def test_a_label_put_on_or_taken_off_a_record_is_in_its_history():
    w = world()
    before = client.get(f"/v1/assets/{w['pump']}", headers=w["headers"]).json()["updated_at"]
    label = _label(w, w["pump"], "qrcode", f"QR-{secrets.token_hex(3)}")
    history = client.get(f"/v1/assets/{w['pump']}/history", headers=w["headers"]).json()
    assert [h["details"] for h in history] == [f"Added qrcode label {label['value']}"] and history[0]["type"] == "label"
    assert client.get(f"/v1/assets/{w['pump']}", headers=w["headers"]).json()["updated_at"] > before
    assert client.delete(f"/v1/assets/{w['pump']}/labels/{label['uid']}", headers=w["headers"]).status_code == 204
    details = [h["details"] for h in client.get(f"/v1/assets/{w['pump']}/history", headers=w["headers"]).json()]
    assert f"Removed qrcode label {label['value']}" in details


def test_an_edit_is_in_the_records_history_from_what_to_what():
    w = world()
    r = client.get(f"/v1/assets/{w['pump']}", headers=w["headers"])
    body = r.json()
    attrs = {**body["attributes"], "manufacturer": "Pfeiffer"}
    put = client.put(f"/v1/assets/{w['pump']}", headers={**w["headers"], "If-Match": r.headers["etag"]},
                     json={"attributes": attrs, "is_global": body["is_global"], "avatar_icon_uid": None,
                           "inbound_relations": body["inbound_relations"], "outbound_relations": body["outbound_relations"]})
    assert put.status_code == 200, put.text
    history = client.get(f"/v1/assets/{w['pump']}/history", headers=w["headers"]).json()
    assert len(history) == 1 and history[0]["type"] == "edit"
    assert "Agilent → Pfeiffer" in history[0]["details"]
