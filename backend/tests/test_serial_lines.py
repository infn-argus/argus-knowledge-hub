"""The guided conversion of the old importer's Serial Lines (§9.1, §9.3,
§12.4): a Communication Path from the IOC to the Access Point, the line
retyped in place as the Bus Segment behind it, an advisory required_port,
the old edges gone, and the root-cause walk still finding what it found."""
import secrets
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.ledger import engine, service
from app.main import app
from app.models.asset import Asset, Relation
from app.models.ledger import Decision
from app.models.workspace import Workspace
from app.services.root_cause import root_causes
from tests.test_ledger_transition import token

client = TestClient(app)


def record(db, ws, type_, key, attrs=None):
    a = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=engine.ensure_type(db, ws, type_).uid, key=key,
              name=key, type=type_, attributes=attrs or {})
    db.add(a)
    db.flush()
    return a


def edge(db, ws, a, rel, b):
    db.add(Relation(workspace_id=ws, from_asset_uid=a.uid, to_asset_uid=b.uid, relation_type=rel))
    db.flush()


def world(ledger_only=False, stray=False):
    """IOC ─provided by─ two gauges ─on line─ a line on port 4003 of a Moxa."""
    ws = f"lines-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    ioc = record(db, ws, "IOC", f"{ws}-IOC")
    g1, g2 = record(db, ws, "Control Device", f"{ws}-G1"), record(db, ws, "Control Device", f"{ws}-G2")
    ap = record(db, ws, "Access Point", f"{ws}-AP", {"address": "10.0.0.9:4003"})
    moxa = record(db, ws, "Serial Converter", f"{ws}-MOXA")
    line = record(db, ws, "Serial Line", f"{ws}-MOXA:4003", {"line_kind": "RS485", "baud": 9600})
    for g in (g1, g2):
        edge(db, ws, g, "provided by", ioc)
        edge(db, ws, g, "on line", line)
    edge(db, ws, line, "port of", ap)
    edge(db, ws, line, "carried by", moxa)
    ids = {k: v.uid for k, v in dict(ioc=ioc, g1=g1, g2=g2, ap=ap, moxa=moxa, line=line).items()}
    if stray:
        g3 = record(db, ws, "Control Device", f"{ws}-G3")
        edge(db, ws, g3, "on line", line)
        ids["g3"] = g3.uid
    headers = token(db, ws)
    if ledger_only:
        db.get(Workspace, ws).ledger_only = True
    db.commit()
    db.close()
    return ws, headers, ids


def edges(db, rel, a=None, b=None):
    q = db.query(Relation).filter_by(relation_type=rel)
    if a:
        q = q.filter_by(from_asset_uid=a)
    if b:
        q = q.filter_by(to_asset_uid=b)
    return q.all()


def test_a_line_is_proposed_then_converted_and_the_walk_still_finds_the_converter():
    ws, headers, ids = world()
    golden = client.post("/v1/migration/golden-incidents", headers=headers, json={
        "name": "gauges dark", "symptoms": [ids["g1"], ids["g2"]], "expected_causes": [ids["moxa"]]})
    assert golden.status_code == 201, golden.text

    lines = client.get("/v1/ledger/serial-lines", headers=headers).json()["lines"]
    assert len(lines) == 1
    p = lines[0]
    assert p["ready"] and not p["questions"]
    assert p["access_point"]["uid"] == ids["ap"] and p["converter"]["uid"] == ids["moxa"]
    assert len(p["paths"]) == 1 and p["paths"][0]["ioc"]["uid"] == ids["ioc"]
    assert sorted(p["paths"][0]["devices"]) == sorted([ids["g1"], ids["g2"]])
    assert p["required_port"] == {"tcp_port": 4003}
    before = client.get("/v1/ledger/registry/report", headers=headers).json()
    assert before["counts"]["deprecated"] == 3 and before["counts"]["source_type"] == 1     # `port of` from a line

    assert client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers,
                       json={"reason": " "}).status_code == 422
    r = client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers,
                    json={"reason": "the line is the bus behind the Moxa port"})
    assert r.status_code == 200, r.text
    built = r.json()
    assert built["golden"]["ok"] is True and len(built["paths"]) == 1 and len(built["removed"]) == 4
    assert built["implemented_by"] == ids["moxa"]

    db = SessionLocal()
    line = db.get(Asset, ids["line"])
    assert line.type == "Bus Segment" and line.key == f"{ws}-MOXA:4003"          # same record, same key
    assert "required_port" not in (line.attributes or {})                       # advisory, not in effect
    path = built["paths"][0]["uid"]
    assert db.get(Asset, path).type == "Communication Path"
    assert edges(db, "enters at", path, ids["ap"]) and edges(db, "continues on", path, ids["line"])
    assert edges(db, "served by", ids["line"], path)
    assert {r.from_asset_uid for r in edges(db, "uses path", b=path)} == {ids["g1"], ids["g2"]}
    assert edges(db, "implemented by", ids["ap"], ids["moxa"])
    for rel in ("on line", "port of", "carried by"):
        assert not edges(db, rel, b=ids["line"]) and not edges(db, rel, a=ids["line"]), rel
    assert db.query(Decision).filter_by(workspace_id=ws, kind="convert_serial_line").count() == 1
    assert db.query(Decision).filter_by(workspace_id=ws, kind="remove_legacy_edge").count() == 4
    result = root_causes(db, ws, [ids["g1"], ids["g2"]], top=20)
    assert ids["moxa"] in [c["uid"] for c in result["candidates"]]
    db.close()

    after = client.get("/v1/ledger/registry/report", headers=headers).json()
    assert before["total"] == 5 and after["total"] == 0          # `port of` also pointed at a non-equipment
    assert client.get("/v1/ledger/serial-lines", headers=headers).json()["lines"] == []
    assert client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers,
                       json={"reason": "again"}).status_code == 422


def test_a_conversion_that_would_lose_a_known_cause_is_refused_unless_accepted():
    ws, headers, ids = world()
    db = SessionLocal()
    # A second endpoint, already implemented by another converter: entering there drops the Moxa.
    other_ap = record(db, ws, "Access Point", f"{ws}-AP2")
    other = record(db, ws, "Serial Converter", f"{ws}-MOXA2")
    edge(db, ws, other_ap, "implemented by", other)
    uids = other_ap.uid
    db.commit()
    db.close()
    client.post("/v1/migration/golden-incidents", headers=headers, json={
        "name": "gauges dark", "symptoms": [ids["g1"]], "expected_causes": [ids["moxa"]]})

    body = {"reason": "enters at the new endpoint", "access_point_uid": uids}
    refused = client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers, json=body)
    assert refused.status_code == 422 and "lose a cause" in refused.json()["detail"]["error"]
    db = SessionLocal()
    assert db.get(Asset, ids["line"]).type == "Serial Line"                      # nothing of it stayed
    assert len(edges(db, "on line", b=ids["line"])) == 2
    db.close()

    accepted = client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers,
                           json={**body, "accept_golden_loss": "the Moxa was replaced by MOXA2 in 2025"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["golden"]["ok"] is False and "implemented_by" not in accepted.json()


def test_an_unclear_line_asks_first_and_a_ledger_only_workspace_converts_through_the_ledger():
    ws, headers, ids = world(ledger_only=True, stray=True)
    p = client.get("/v1/ledger/serial-lines", headers=headers).json()["lines"][0]
    assert not p["ready"] and any("no IOC" in q for q in p["questions"])
    refused = client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers, json={"reason": "go"})
    assert refused.status_code == 422 and "no IOC" in refused.json()["detail"]["error"]

    db = SessionLocal()
    service.relate(db, ws, "tester", ids["g3"], "provided by", ids["ioc"])
    db.commit()
    db.close()
    assert client.get("/v1/ledger/serial-lines", headers=headers).json()["lines"][0]["ready"]
    r = client.post(f"/v1/ledger/serial-lines/{ids['line']}/convert", headers=headers, json={"reason": "go"})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    assert db.get(Asset, ids["line"]).type == "Bus Segment"
    path = r.json()["paths"][0]["uid"]
    assert {e.from_asset_uid for e in edges(db, "uses path", b=path)} == {ids["g1"], ids["g2"], ids["g3"]}
    assert not edges(db, "on line", b=ids["line"])
    db.close()
