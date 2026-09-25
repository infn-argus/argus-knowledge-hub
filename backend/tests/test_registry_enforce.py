"""The relation registry in enforce mode (asset-model-revision §13 S7):
switched on per workspace once every violation is fixed or accepted;
then a new edge that breaks the registry is refused."""
import secrets
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.ledger import engine
from app.main import app
from app.models.asset import Relation
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)


def setup():
    w = f"reg-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=w, name=w))
    db.flush()
    types = {t: engine.ensure_type(db, w, t).uid for t in ("Ion Pump", "Equipment Position", "Quadrupole", "Section")}
    headers = token(db, w)
    db.commit()
    db.close()
    recs = {}
    for name, t in (("A", "Ion Pump"), ("B", "Ion Pump"), ("P", "Equipment Position"), ("Q", "Quadrupole"),
                    ("S1", "Section"), ("S2", "Section")):
        uid = str(uuid.uuid4())
        r = client.post("/v1/assets", headers=headers, json={"uid": uid, "schema_uid": types[t], "key": f"{w}-{name}",
                                                              "name": name, "type": t, "attributes": {}})
        assert r.status_code == 201, r.text
        recs[name] = uid
    return w, headers, recs


def relate(headers, a, rel, b):
    return client.post("/v1/relations", headers=headers, json={"from_asset_uid": a, "to_asset_uid": b,
                                                               "relation_type": rel})


def test_enforce_mode_needs_a_clean_or_explained_report_and_then_refuses_bad_edges():
    w, headers, r = setup()
    # Warn mode: a bad edge is written and reported.
    assert relate(headers, r["A"], "powers", r["B"]).status_code == 201
    db = SessionLocal()
    db.add(Relation(workspace_id=w, from_asset_uid=r["A"], to_asset_uid=r["B"], relation_type="spare for"))
    db.commit()
    db.close()
    rep = client.get("/v1/ledger/registry/report", headers=headers).json()
    assert rep["mode"] == "warn" and rep["unexplained"] == 2          # powers from a pump; spare for
    refused = client.put("/v1/ledger/registry/mode", headers=headers, json={"mode": "enforce", "reason": "S7"})
    assert refused.status_code == 409 and refused.json()["detail"]["unexplained"] == 2

    # Fix one (remove the edge), accept the others with a reason.
    powers = next(x for x in client.get("/v1/relations", headers=headers).json() if x["relation_type"] == "powers")
    assert client.delete(f"/v1/relations/{powers['id']}", headers=headers).status_code == 204
    rep = client.get("/v1/ledger/registry/report", headers=headers).json()
    assert rep["unexplained"] == 1
    v = rep["violations"][0]
    assert client.post("/v1/ledger/registry/exceptions", headers=headers,
                       json={"violation_id": v["id"], "reason": " "}).status_code == 422
    assert client.post("/v1/ledger/registry/exceptions", headers=headers, json={
        "violation_id": v["id"], "reason": "the spare shelf list is migrated next month"}).status_code == 201
    rep = client.get("/v1/ledger/registry/report", headers=headers).json()
    assert rep["unexplained"] == 0 and rep["violations"][0]["explained_by"]
    assert client.put("/v1/ledger/registry/mode", headers=headers,
                      json={"mode": "enforce", "reason": "S7"}).json()["mode"] == "enforce"

    # Enforced: the registry decides what may be written.
    bad = relate(headers, r["A"], "powers", r["Q"])                       # a pump is not a position
    assert bad.status_code == 409 and bad.json()["detail"]["invariant"] == "I-REG"
    assert relate(headers, r["P"], "powers", r["Q"]).status_code == 201
    assert relate(headers, r["B"], "spare for", r["A"]).status_code == 409          # deprecated verb
    assert relate(headers, r["S1"], "part of", r["S2"]).status_code == 201
    cycle = relate(headers, r["S2"], "part of", r["S1"])
    assert cycle.status_code == 409 and "cycle" in cycle.json()["detail"]["error"]
    # Removing an edge never breaks the registry.
    ok = next(x for x in client.get("/v1/relations", headers=headers).json()
              if x["relation_type"] == "part of")
    assert client.delete(f"/v1/relations/{ok['id']}", headers=headers).status_code == 204
    # Back to warn, with a reason.
    assert client.put("/v1/ledger/registry/mode", headers=headers,
                      json={"mode": "warn", "reason": "rollback"}).json()["mode"] == "warn"
    assert relate(headers, r["B"], "powers", r["Q"]).status_code == 201
