"""Golden incidents (§12.6 I-MIG-7): the root-cause walk must keep finding
the causes the teams know, across a legacy migration."""
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.asset import Relation
from tests.test_legacy_migration import Legacy, outcomes

client = TestClient(app)


def override(L, plan, tag, outcome, reason):
    item = outcomes(plan)[tag]["item"]
    r = client.post(f"/v1/migration/plans/{plan['id']}/items/{item}/override", headers=L.headers,
                    json={"outcome": outcome, "reason": reason})
    assert r.status_code == 200, r.text


def test_a_migration_that_loses_a_known_cause_is_caught_and_can_be_corrected():
    L = Legacy()
    db = SessionLocal()
    # The old gauge the importer no longer writes still powers the quadrupole.
    db.add(Relation(workspace_id=L.ws, from_asset_uid=L.stale.uid, to_asset_uid=L.element.uid, relation_type="powers"))
    db.commit()
    db.close()
    quad, gauge = L.element.key, L.stale.key
    assert client.post("/v1/migration/golden-incidents", headers=L.headers, json={
        "name": "QUA01 tripped", "symptoms": ["nope"], "expected_causes": [gauge]}).status_code == 422
    created = client.post("/v1/migration/golden-incidents", headers=L.headers, json={
        "name": "QUA01 tripped, 2024-03-12", "symptoms": [quad], "symptom_kind": {quad: "function"},
        "expected_causes": [gauge]})
    assert created.status_code == 201, created.text
    run = client.post("/v1/migration/golden-incidents/run", headers=L.headers).json()
    assert run["found"] == run["expected"] == 1

    # The plan retires the stale gauge and its edges: the walk loses the cause.
    plan = client.post("/v1/migration/plans", headers=L.headers, json={}).json()
    assert outcomes(plan)["old:GAUGE9"]["outcome"] == "M-RETIRE"
    override(L, plan, "vac:SIP04", "M-POS", "duplicate")
    client.post(f"/v1/migration/plans/{plan['id']}/apply", headers=L.headers)
    deep = client.post(f"/v1/migration/plans/{plan['id']}/verify",
                       headers=L.headers).json()["invariants"]["deep_verification"]
    assert deep["I-MIG-7"]["ok"] is False and deep["I-MIG-7"]["lost"] == [
        {"incident": "QUA01 tripped, 2024-03-12", "cause": L.stale.uid}]
    refused = client.post(f"/v1/migration/plans/{plan['id']}/finalize", headers=L.headers,
                          json={"golden_waiver": "not applicable"})
    assert refused.status_code == 409 and "I-MIG-7" in refused.json()["detail"]["error"]

    # Rolled back and planned again, with the gauge kept as the position it still is.
    assert client.post(f"/v1/migration/plans/{plan['id']}/rollback", headers=L.headers, json={}).status_code == 200
    plan = client.post("/v1/migration/plans", headers=L.headers, json={}).json()
    override(L, plan, "vac:SIP04", "M-POS", "duplicate")
    override(L, plan, "old:GAUGE9", "M-POS", "it still powers QUA01")
    client.post(f"/v1/migration/plans/{plan['id']}/apply", headers=L.headers)
    deep = client.post(f"/v1/migration/plans/{plan['id']}/verify",
                       headers=L.headers).json()["invariants"]["deep_verification"]
    assert deep["I-MIG-7"]["ok"] and deep["ok"], deep
    done = client.post(f"/v1/migration/plans/{plan['id']}/finalize", headers=L.headers)
    assert done.status_code == 200 and done.json()["status"] == "finalized"
    # The golden set stays, for the next change to the causal model.
    assert len(client.get("/v1/migration/golden-incidents", headers=L.headers).json()) == 1
