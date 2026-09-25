"""Transition and readiness tests (asset-model-revision §14, A33–A41): the
gates of a domain's cutover from Jira and Insight to ARGUS.
"""
import json
import os
import secrets
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import hash_token
from app.db import SessionLocal
from app.ledger import cutover, engine, identity, service, temporal, tickets
from app.ledger.engine import LedgerError
from app.main import app
from app.models.api_token import ApiToken
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetLabel
from app.models.attachment import Attachment
from app.models.issue import Issue
from app.models.ledger import Conflict, RevisionEvent
from app.models.schema import Schema
from app.models.workspace import Workspace
from tests.test_ledger_connectivity import ITFixture
from tests.test_ledger_slice import T0, Slice

client = TestClient(app)
DAY = timedelta(days=1)
ATTEST = {k: True for k in cutover.ATTESTATIONS}
# A fixture has no two weeks of shadow runs, restore rehearsal or probe run: waived, as for a rehearsal.
ENTRY = {"attestations": {"readiness": True, "users_trained": True, "jira_readonly_scheduled": True},
         "waivers": {"t2": "fixture", "restore": "fixture", "performance": "fixture"}}


def token(db, ws, grants=()):
    raw = secrets.token_urlsafe(12)
    db.add(ApiToken(workspace_id=ws, token_hash=hash_token(raw), restricted_grants=list(grants)))
    db.flush()
    return {"Authorization": f"Bearer {raw}"}


def objects_manifest(s):
    return {"watermark": {"object_history_id": 991}, "objects": [
        {"objectId": s.oid1, "key": f"{s.fac}INV-84321"}, {"objectId": s.oid2, "key": f"{s.fac}INV-90001"}]}


def cut_over(db, s, domain_id=None, manifest=None):
    """Take the inventory domain through T1, T2, the freeze, a passing report and the exit."""
    d = cutover.create_domain(db, s.inv, domain_id or f"pilot-{s.fac}", "Vacuum equipment",
                              stream_ids=[s.insight], pilot=True)
    cutover.advance(db, d.id, "T1", "steward")
    cutover.advance(db, d.id, "T2", "steward")
    manifest = manifest or objects_manifest(s)
    cutover.set_stewards(db, d.id, "owner", "steward", "backup")
    cutover.freeze(db, d.id, "steward", manifest["watermark"], manifest, **ENTRY)
    report = cutover.reconcile(db, d.id, manifest, "steward")
    assert report.passed, report.body["differences"]
    cutover.sign_exit(db, d.id, "owner", ATTEST)
    return d


# --------------------------------------------------------------------------- A33

def test_A33_a_frozen_stream_refuses_revisions_and_editing_opens_at_the_exit():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    d = cutover.create_domain(db, s.inv, f"pilot-{s.fac}", "Vacuum equipment", stream_ids=[s.insight], pilot=True)
    cutover.advance(db, d.id, "T1", "steward")
    unit = s.unit(db)
    # No dual write: between import and exit ARGUS holds the scope read-only.
    with pytest.raises(LedgerError):
        service.edit_value(db, s.inv, "someone", unit.uid, "attr:argus_location", "Rack B13")
    cutover.advance(db, d.id, "T2", "steward")
    manifest = objects_manifest(s)
    cutover.set_stewards(db, d.id, "owner", "steward", "backup")
    cutover.freeze(db, d.id, "steward", manifest["watermark"], manifest, **ENTRY)
    db.commit()
    frozen = db.scalar(select(RevisionEvent).where(RevisionEvent.stream_id == s.insight,
                                                   RevisionEvent.kind == "frozen"))
    assert frozen.detail == {"watermark": {"object_history_id": 991},
                             "manifest_hash": cutover.hash_manifest(manifest)}

    late = s.inventory(db, rev="i2", at=T0 + DAY, location="Rack B99")
    db.commit()
    assert late["state"] == "rejected"
    ev = db.scalar(select(RevisionEvent).where(RevisionEvent.revision_id == late["revision_id"]))
    assert ev.kind == "rejected" and ev.cause == "frozen"
    db.refresh(unit)
    assert unit.attributes["argus_location"] == "Rack B12"    # nothing projected

    assert cutover.reconcile(db, d.id, manifest, "steward").passed
    cutover.sign_exit(db, d.id, "owner", ATTEST)
    service.edit_value(db, s.inv, "someone", unit.uid, "attr:argus_location", "Rack B13")
    db.commit()
    db.refresh(unit)
    assert unit.attributes["argus_location"] == "Rack B13"
    assert cutover.authoritative(db, s.inv)
    db.close()


# --------------------------------------------------------------------------- A34

def test_A34_a_rekeyed_insight_object_is_the_same_record_with_its_old_key_as_an_alias():
    s = Slice()
    db = SessionLocal()
    s.inventory(db)
    db.commit()
    unit = s.unit(db)
    old_key = unit.key
    rekeyed = json.dumps({"objects": [
        {"objectId": s.oid1, "type": "Ion Pump", "key": f"{s.fac}INV-84321-R", "name": "Ion pump 84321",
         "attributes": {"serial": f"{s.fac}-84321", "manufacturer": "Agilent", "argus_location": "Rack B12"}},
        {"objectId": s.oid2, "type": "Ion Pump", "key": f"{s.fac}INV-90001", "name": "Ion pump 90001",
         "attributes": {"serial": f"{s.fac}-90001", "manufacturer": "Agilent", "argus_location": "Storage"}}]}).encode()
    engine.ingest(db, s.insight, revision="i2", content=rekeyed, observed_at=T0 + DAY, parser="insight-fixture")
    db.commit()
    db.refresh(unit)
    assert unit.key == f"{s.fac}INV-84321-R"
    assert db.scalar(select(AssetLabel).where(AssetLabel.asset_uid == unit.uid, AssetLabel.type == "former_key",
                                              AssetLabel.value == old_key))
    assert db.scalar(select(Asset).where(Asset.key == old_key)) is None
    assert not db.scalar(select(Conflict).where(Conflict.conflict_type == "identity_candidate",
                                                Conflict.detail["records"].contains([unit.uid])))
    headers = token(db, s.inv)
    db.commit()
    hit = client.get(f"/v1/lookup/{old_key}", headers=headers).json()
    assert hit["uid"] == unit.uid and hit["via"] == "former_key"
    db.close()


# --------------------------------------------------------------------------- A35

def twins(s):
    return json.dumps({"objects": [
        {"objectId": s.oid1, "type": "Ion Pump", "key": f"{s.fac}INV-A", "name": "Ion pump A",
         "attributes": {"serial": f"SN-{s.fac}", "manufacturer": "Agilent"}},
        {"objectId": s.oid2, "type": "Ion Pump", "key": f"{s.fac}INV-B", "name": "Ion pump B",
         "attributes": {"serial": f"SN-{s.fac}", "manufacturer": "agilent "}}]}).encode()


def test_A35_shared_serials_are_candidates_never_merges_and_after_cutover_creation_is_refused():
    s = Slice()
    db = SessionLocal()
    engine.ingest(db, s.insight, revision="i1", content=twins(s), observed_at=T0, parser="insight-fixture")
    db.commit()
    a, b = s.rec(db, f"{s.fac}INV-A"), s.rec(db, f"{s.fac}INV-B")
    [candidate] = db.scalars(select(Conflict).where(Conflict.conflict_type == "identity_candidate",
                                                    Conflict.detail["records"].contains([a.uid])))
    assert sorted(candidate.detail["records"]) == sorted([a.uid, b.uid])
    assert candidate.detail["identifier"] == "serial"
    assert a.record_status == b.record_status == "Active" and a.merged_into_uid is None is b.merged_into_uid

    manifest = {"watermark": {"object_history_id": 7}, "objects": [
        {"objectId": s.oid1, "key": a.key}, {"objectId": s.oid2, "key": b.key}]}
    cut_over(db, s, manifest=manifest)
    headers = token(db, s.inv)
    db.commit()
    schema_uid = a.schema_uid
    resp = client.post("/v1/assets", headers=headers, json={
        "uid": str(uuid.uuid4()), "schema_uid": schema_uid, "key": f"{s.fac}INV-C", "name": "Ion pump C",
        "type": "Ion Pump", "attributes": {"serial": f"SN-{s.fac}", "manufacturer": "Agilent"}})
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["invariant"] == "I-ID-1"
    assert resp.json()["detail"]["existing"]["uid"] in (a.uid, b.uid)
    ok = client.post("/v1/assets", headers=headers, json={
        "uid": str(uuid.uuid4()), "schema_uid": schema_uid, "key": f"{s.fac}INV-D", "name": "Ion pump D",
        "type": "Ion Pump", "attributes": {"serial": f"SN-{s.fac}-2", "manufacturer": "Agilent"}})
    assert ok.status_code == 201, ok.text

    # The steward merges the twins: one survivor, one tombstone, the candidate closes.
    identity.merge(db, s.inv, "steward", a.uid, b.uid, "the same pump, recorded twice")
    db.commit()
    db.refresh(b)
    assert b.record_status == "Merged" and b.merged_into_uid == a.uid
    assert engine.resolve_ref(db, f"insight:object:{s.oid2}") == a.uid
    assert db.get(Conflict, candidate.conflict_id) is None
    hit = client.get(f"/v1/lookup/{b.key}", headers=headers).json()
    assert hit["uid"] == a.uid
    db.close()


# --------------------------------------------------------------------------- A36

def test_A36_an_edit_is_visible_at_once_and_derived_edges_are_marked_until_they_follow(monkeypatch):
    s = Slice()
    db = SessionLocal()
    engine.register_stream(db, f"insight:{s.fac}:locations", s.inv, "insight", may_create=["Location"])
    engine.activate_policy(db)
    engine.ingest(db, f"insight:{s.fac}:locations", revision="l1", observed_at=T0, parser="insight-fixture",
                  content=json.dumps({"objects": [
                      {"objectId": f"L{s.oid1}", "type": "Location", "key": f"{s.fac}LOC-B12", "name": "Rack B12"},
                      {"objectId": f"L{s.oid2}", "type": "Location", "key": f"{s.fac}LOC-B13",
                       "name": "Rack B13"}]}).encode())
    s.inventory(db)
    headers = token(db, s.inv)
    ticket = Issue(uid=str(uuid.uuid4()), workspace_id=s.inv, title="Check pump", description="old")
    db.add(ticket)
    db.commit()
    unit = s.unit(db)
    b12, b13 = s.rec(db, f"{s.fac}LOC-B12"), s.rec(db, f"{s.fac}LOC-B13")

    def located():
        return db.scalar(select(Relation.to_asset_uid).where(Relation.from_asset_uid == unit.uid,
                                                             Relation.relation_type == "located in"))
    assert located() == b12.uid

    resp = client.put(f"/v1/issues/{ticket.uid}", headers=headers, json={"description": "pump replaced"})
    assert resp.json()["description"] == "pump replaced"
    assert client.get(f"/v1/issues/{ticket.uid}", headers=headers).json()["description"] == "pump replaced"

    monkeypatch.setenv("LEDGER_USER_EDIT_DERIVE", "manual")
    resp = client.post(f"/v1/ledger/records/{unit.uid}/edit", headers=headers,
                       json={"predicate": "attr:argus_location", "value": "Rack B13"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["attributes"]["argus_location"] == "Rack B13"
    assert resp.json()["processing"]["state"] == "deriving"
    ctx = client.get(f"/v1/hub/assets/{unit.uid}/context", headers=headers).json()
    assert ctx["processing"]["state"] == "deriving"
    assert client.get(f"/v1/assets/{unit.uid}", headers=headers).json()["attributes"]["argus_location"] == "Rack B13"
    db.expire_all()
    assert located() == b12.uid                     # not yet derived

    engine.process_derive_requests(db)
    db.commit()
    assert located() == b13.uid
    assert client.get(f"/v1/hub/assets/{unit.uid}/context", headers=headers).json()["processing"] is None
    db.close()


# --------------------------------------------------------------------------- A37

def test_A37_restricted_records_are_absent_without_the_grant_everywhere_and_present_with_it():
    ws = f"acl-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="ACL"))
    db.flush()
    schema = engine.ensure_type(db, ws, "Procurement Record")
    kind = engine.ensure_type(db, ws, "Ion Pump")
    ticket_type = Schema(uid=f"{ws}:safety", workspace_id=ws, name="Safety investigation", applies_to="tickets")
    db.add(ticket_type)
    pump = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=kind.uid, key=f"{ws}-PUMP", name="Pump P1",
                 type="Ion Pump", attributes={})
    pr = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=schema.uid, key=f"{ws}-PR-2026-17",
               name="Purchase of pump P1", type="Procurement Record",
               attributes={"classification": "restricted:costs", "cost": 18400})
    db.add_all([pump, pr])
    db.flush()
    db.add(Relation(workspace_id=ws, from_asset_uid=pump.uid, to_asset_uid=pr.uid, relation_type="procured by"))
    inv = Issue(uid=str(uuid.uuid4()), workspace_id=ws, title="Investigation of the P1 pump incident",
                schema_uid=ticket_type.uid, asset_uid=pump.uid,
                attributes={"classification": "restricted:safety_investigation"})
    db.add(inv)
    without = token(db, ws)
    with_grant = token(db, ws, ["costs", "safety_investigation"])
    db.commit()

    def views(h):
        mcp = client.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "search_objects", "arguments": {"query": "purchase"}}}).json()
        mcp_tickets = client.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                          "params": {"name": "search_tickets",
                                                                     "arguments": {"query": "investigation"}}}).json()
        graph = client.get("/v1/graph", headers=h, params={"kind": "asset", "uid": pump.uid}).json()
        return {
            "list": pr.uid in [a["uid"] for a in client.get("/v1/assets", headers=h).json()],
            "get": client.get(f"/v1/assets/{pr.uid}", headers=h).status_code,
            "search": [a["uid"] for a in client.get("/v1/hub/search", headers=h, params={"q": "purchase"}).json()
                       ["assets"]],
            "ticket_search": [t["uid"] for t in client.get("/v1/hub/search", headers=h,
                                                             params={"q": "investigation"}).json()["tickets"]],
            "counts": client.get("/v1/hub/overview", headers=h).json(),
            "tickets": [i["uid"] for i in client.get("/v1/issues", headers=h).json()],
            "ticket_get": client.get(f"/v1/issues/{inv.uid}", headers=h).status_code,
            "export": client.get("/v1/export/assets", headers=h).text,
            "export_tickets": client.get("/v1/export/tickets", headers=h).text,
            "graph": graph,
            "mcp": json.loads(mcp["result"]["content"][0]["text"]),
            "mcp_tickets": json.loads(mcp_tickets["result"]["content"][0]["text"]),
        }

    no, yes = views(without), views(with_grant)
    assert not no["list"] and no["get"] == 404 and pr.uid not in no["search"]
    assert inv.uid not in no["ticket_search"] and inv.uid not in no["tickets"] and no["ticket_get"] == 404
    assert pr.uid not in no["export"] and "18400" not in no["export"] and inv.uid not in no["export_tickets"]
    assert no["mcp"]["total"] == 0 and no["mcp_tickets"]["total"] == 0
    assert no["counts"]["assets"]["own"] == 1 and no["counts"]["tickets"]["total"] == 0
    # The restricted record and the restricted ticket are both drawn, anonymously.
    assert sorted(n["kind"] for n in no["graph"]["nodes"] if n["restricted"]) == ["asset", "ticket"]
    [anon] = [n for n in no["graph"]["nodes"] if n["restricted"] and n["kind"] == "asset"]
    assert anon["label"] == "Restricted record" and anon["uid"] != pr.uid and anon["type_name"] is None
    assert any(e["to_uid"] == anon["uid"] for e in no["graph"]["edges"])
    assert pr.uid not in json.dumps(no["graph"]) and inv.uid not in json.dumps(no["graph"])

    assert yes["list"] and yes["get"] == 200 and pr.uid in yes["search"]
    assert inv.uid in yes["ticket_search"] and inv.uid in yes["tickets"] and yes["ticket_get"] == 200
    assert pr.uid in yes["export"] and inv.uid in yes["export_tickets"]
    assert yes["mcp"]["total"] == 1 and yes["mcp_tickets"]["total"] == 1
    assert yes["counts"]["assets"]["own"] == 2 and yes["counts"]["tickets"]["total"] == 1
    assert pr.uid in [n["uid"] for n in yes["graph"]["nodes"]]
    db.close()


# --------------------------------------------------------------------------- A38

def test_A38_an_operational_incident_needs_to_say_when_it_happened():
    ws = f"inc-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Incidents"))
    db.flush()
    incident = Schema(uid=f"{ws}:incident", workspace_id=ws, name="Operational incident", applies_to="tickets")
    db.add(incident)
    headers = token(db, ws)
    db.commit()
    base = {"schema_uid": incident.uid, "title": "Beam lost"}
    refused = client.post("/v1/issues", headers=headers, json={**base, "uid": str(uuid.uuid4())})
    assert refused.status_code == 422 and refused.json()["detail"]["invariant"] == "I-TKT-4"
    accepted = client.post("/v1/issues", headers=headers, json={
        **base, "uid": str(uuid.uuid4()), "attributes": {"occurred_from": temporal.instant("2026-03-02", "day")}})
    assert accepted.status_code == 201, accepted.text
    # Removing the time later is refused too.
    cleared = client.put(f"/v1/issues/{accepted.json()['uid']}", headers=headers, json={"attributes": {}})
    assert cleared.status_code == 422

    legacy = Issue(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=incident.uid, title="Old beam loss",
                   attributes={"argus_source": "jira", "argus_source_key": f"{ws.upper()}-1",
                               "argus_source_created": "2025-11-20T09:00:00+00:00"})
    db.add(legacy)
    db.flush()
    tickets.derive_for_ticket(db, legacy)
    db.commit()
    db.refresh(legacy)
    assert legacy.attributes["occurrence_source"] == "legacy_created_fallback"
    earliest, latest, source = tickets.incident_range(legacy)
    assert source == "legacy_created_fallback" and latest - earliest == timedelta(days=7)
    db.close()


# --------------------------------------------------------------------------- A39

def test_A39_a_safety_segment_waits_for_a_person_even_with_a_unique_registry_backed_match():
    it = ITFixture(interlock_segment=1)
    db = SessionLocal()
    it.swap(db, "M-7702", engine.now() - DAY)
    assert it.attached(db, 1) is None
    [item] = it.items(db, 1, "port_confirmation_required")
    [candidate] = item.detail["candidates"]
    assert candidate["port_uid"] == it.port(db, "M-7702", 1).uid
    from app.ledger import connectivity
    engine.apply_decisions(db, it.ws, "controls-steward", [connectivity.confirm_port_map(
        it.seg(db, 1).uid, item.detail["installation_uid"], candidate["port_uid"], [])])
    db.commit()
    assert it.attached(db, 1) == it.port(db, "M-7702", 1).uid
    db.close()


# --------------------------------------------------------------------------- A40

def test_A40_historical_keys_and_urls_redirect_and_an_unknown_one_points_to_the_archive():
    ws = f"hist-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="History"))
    db.flush()
    key = f"H{secrets.token_hex(2).upper()}-123"
    issue = Issue(uid=str(uuid.uuid4()), workspace_id=ws, title="Migrated",
                  attributes={"argus_source": "jira", "argus_source_key": key})
    kind = engine.ensure_type(db, ws, "Ion Pump")
    equipment_key = f"LNFMAC-{secrets.token_hex(3)}"
    pump = Asset(uid=str(uuid.uuid4()), workspace_id=ws, schema_uid=kind.uid, key=equipment_key, name="Pump",
                 type="Ion Pump", attributes={})
    db.add_all([issue, pump])
    cutover.create_domain(db, ws, f"tickets-{ws}", "Tickets", resource="tickets",
                          archive_url="https://jira-archive.example.org/browse/{key}")
    headers = token(db, ws)
    db.commit()
    by_key = client.get(f"/v1/lookup/{key}", headers=headers).json()
    assert by_key["path"] == f"/tickets/{issue.uid}"
    by_url = client.get(f"/v1/lookup/https://jira.example.org/browse/{key}", headers=headers).json()
    assert by_url["uid"] == issue.uid
    by_equipment = client.get(f"/v1/lookup/{equipment_key}", headers=headers).json()
    assert by_equipment["path"] == f"/assets/{pump.uid}"
    unknown = client.get("/v1/lookup/SPARC-999999", headers=headers)
    assert unknown.status_code == 404
    assert unknown.json()["detail"] == {"status": "not migrated", "identifier": "SPARC-999999",
                                        "archive": "https://jira-archive.example.org/browse/SPARC-999999"}
    db.close()


# --------------------------------------------------------------------------- A41

def test_A41_a_missing_attachment_fails_the_reconciliation_and_blocks_the_exit(tmp_path):
    ws = f"rec-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Reconciliation"))
    db.flush()
    stream = engine.register_stream(db, f"jira:{ws}", ws, "jira")
    key = f"R{secrets.token_hex(2).upper()}-7"
    issue = Issue(uid=str(uuid.uuid4()), workspace_id=ws, title="With attachments", state="closed",
                  attributes={"argus_source": "jira", "argus_source_key": key, "argus_source_status": "Done"})
    db.add(issue)
    db.flush()
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"jpeg bytes of the broken flange")
    db.add(Attachment(uid=str(uuid.uuid4()), workspace_id=ws, issue_uid=issue.uid, filename="photo.jpg",
                      file_size=photo.stat().st_size, storage_path=str(photo)))
    db.flush()
    stored = db.scalar(select(Attachment).where(Attachment.issue_uid == issue.uid))
    assert stored.sha256 and len(stored.sha256) == 64
    engine.ingest(db, stream.id, revision="export-1", observed_at=T0, parser="resolved", content=b"[]")
    d = cutover.create_domain(db, ws, f"tickets-{ws}", "Tickets", resource="tickets", stream_ids=[stream.id])
    cutover.advance(db, d.id, "T1", "steward")
    cutover.advance(db, d.id, "T2", "steward")
    missing_sha = "9f2c" * 16
    manifest = {"watermark": {"updated": "2026-09-20T18:00:00Z", "changelog_id": 5521},
                "status_map": {"Done": "closed"},
                "issues": [{"key": key, "status": "Done", "comments": 0, "attachments": [
                    {"name": "photo.jpg", "size": photo.stat().st_size, "sha256": stored.sha256},
                    {"name": "wiring.pdf", "size": 48213, "sha256": missing_sha}]}]}
    cutover.set_stewards(db, d.id, "owner", "steward", "backup")
    cutover.freeze(db, d.id, "steward", manifest["watermark"], manifest, **ENTRY)
    report = cutover.reconcile(db, d.id, manifest, "steward")
    db.commit()
    assert not report.passed and report.body["unexplained"] == 1
    [diff] = report.body["differences"]
    assert diff["section"] == "attachments" and diff["item"] == f"{key}/wiring.pdf"
    assert diff["sha256"] == missing_sha
    assert report.body["sections"]["attachments"] == {"source": 2, "argus": 1}
    criteria = {c["id"]: c["ok"] for c in cutover.exit_criteria(db, d.id, ATTEST)}
    assert criteria["frozen"] and not criteria["report"]
    with pytest.raises(LedgerError):
        cutover.sign_exit(db, d.id, "owner", ATTEST)
    db.rollback()
    assert db.get(type(d), d.id).exited_at is None
    db.close()


def test_the_cutover_runs_through_the_api_and_the_exit_lists_what_is_missing():
    s = Slice()
    db = SessionLocal()
    s.inventory(db)
    headers = token(db, s.inv)
    db.commit()
    domain = f"api-{s.fac}"
    assert client.post("/v1/domains", headers=headers, json={
        "id": domain, "name": "Vacuum equipment", "stream_ids": [s.insight], "pilot": True}).status_code == 201
    assert client.post(f"/v1/domains/{domain}/stage", headers=headers, json={"stage": "T3"}).status_code == 422
    for stage in ("T1", "T2"):
        assert client.post(f"/v1/domains/{domain}/stage", headers=headers, json={"stage": stage}).status_code == 200
    manifest = objects_manifest(s)
    manifest["objects"].append({"objectId": "404404", "key": "LNFMAC-GONE"})
    # §17.4: no freeze until the entry criteria are met or waived.
    refused = client.post(f"/v1/domains/{domain}/freeze", headers=headers,
                          json={"watermark": manifest["watermark"], "manifest": manifest})
    assert refused.status_code == 422 and "entry criteria" in refused.json()["detail"]["error"]
    entry = {c["id"]: c for c in client.get(f"/v1/domains/{domain}", headers=headers).json()["entry_criteria"]}
    assert not entry["stewards"]["ok"] and not entry["t2"]["ok"] and entry["legacy"]["ok"]
    assert client.put(f"/v1/domains/{domain}/stewards", headers=headers,
                      json={"steward": "rossi", "backup": "rossi"}).status_code == 422
    assert client.put(f"/v1/domains/{domain}/stewards", headers=headers,
                      json={"steward": "rossi", "backup": "bianchi"}).json()["backup_steward"] == "bianchi"
    assert client.post(f"/v1/domains/{domain}/freeze", headers=headers, json={
        "watermark": manifest["watermark"], "manifest": manifest, **ENTRY,
        "waivers": {**ENTRY["waivers"], "queues_blocking": "no"}}).status_code == 422   # never waived
    assert client.post(f"/v1/domains/{domain}/freeze", headers=headers, json={
        "watermark": manifest["watermark"], "manifest": manifest, **ENTRY}).json()["stage"] == "T3"
    report = client.post(f"/v1/domains/{domain}/reconcile", headers=headers, json={"manifest": manifest}).json()
    assert not report["passed"]
    [diff] = [d for d in report["differences"] if d["item"] == "LNFMAC-GONE"]
    refused = client.post(f"/v1/domains/{domain}/exit", headers=headers, json={"attestations": ATTEST})
    assert refused.status_code == 409
    unmet = {c["id"] for c in refused.json()["detail"]["criteria"] if not c["ok"]}
    assert {"report", "identifiers"} <= unmet
    # A deliberate omission, explained by a decision, no longer blocks.
    client.post(f"/v1/domains/{domain}/explain", headers=headers,
                json={"difference": diff["id"], "reason": "scrapped in 2019, never physically delivered"})
    assert client.post(f"/v1/domains/{domain}/reconcile", headers=headers, json={"manifest": manifest}).json()["passed"]
    signed = client.post(f"/v1/domains/{domain}/exit", headers=headers, json={"attestations": ATTEST})
    assert signed.status_code == 200 and signed.json()["authoritative"]
    view = client.get(f"/v1/domains/{domain}", headers=headers).json()
    assert all(c["ok"] for c in view["exit_criteria"] if not c.get("attested"))
    assert len(client.get(f"/v1/domains/{domain}/reports", headers=headers).json()) == 2
    db.close()
