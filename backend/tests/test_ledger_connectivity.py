"""The rest of the S1 vertical slice (asset-model-revision §14): Access Point
reassignment and the address-at-time query (A17–A19), port mapping (A20–A23),
ticket attribution (A31) and rule identity and versions (A32).
"""
import copy
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import hash_token
from app.db import SessionLocal
from app.ledger import connectivity, engine, rules, service, temporal, tickets
from app.ledger.engine import InvariantError
from app.main import app
from app.models.api_token import ApiToken
from app.models.asset import Asset, Relation
from app.models.issue import Issue
from app.models.ledger import (Claim, ClaimEvent, Conflict, Decision, FactState, IdentityEvent, JobRun,
                               MigrationMap, RecordEvent, StreamHead)
from app.models.workspace import Workspace
from tests.test_ledger_slice import T0, Slice, proposed_installation

client = TestClient(app)
DAY = timedelta(days=1)


def _token(db, ws):
    raw = secrets.token_urlsafe(12)
    db.add(ApiToken(workspace_id=ws, token_hash=hash_token(raw)))
    return {"Authorization": f"Bearer {raw}"}


def install(db, ws, position_uid, unit_uid, since="2026-01-01"):
    uid = service.new_installation_claims(db, ws, "operator", position_uid, unit_uid,
                                          temporal.instant(since, "day"))
    service.confirm_installation(db, ws, "operator", uid)
    return uid


# --------------------------------------------------------------------------- A17–A19

def mag_yaml(fac, devices):
    lines = [f"beamline: {fac}", "epicsConfiguration:", "  iocs:", "    - name: mag-psu", "      devgroup: mag",
             "      devices:"]
    for name, host in devices:
        lines.append(f"        - {{name: {name}, host: {host}}}")
    return "\n".join(lines).encode()


class APFixture:
    """`192.168.0.28` assigned to `<FAC>:POS:GUNQUA01/PS`, with PS-1 installed there."""

    def __init__(self):
        self.fac = f"A{secrets.token_hex(3).upper()}"
        self.ws, self.inv = f"ap-{secrets.token_hex(3)}", f"apinv-{secrets.token_hex(3)}"
        self.config = f"epik8s:{self.fac}#values.yaml@main"
        self.insight = f"insight:{self.fac}:ps"
        db = SessionLocal()
        db.add_all([Workspace(id=self.ws, name="AP"), Workspace(id=self.inv, name="AP inventory")])
        db.flush()
        engine.register_stream(db, self.config, self.ws, "epik8s", facility=self.fac,
                               may_create=["IOC", "Control Device", "Equipment Position", "Access Point",
                                           "Communication Path"])
        engine.register_stream(db, self.insight, self.inv, "insight", may_create=["Power Supply"])
        engine.activate_policy(db)
        self.headers = _token(db, self.ws)
        engine.ingest(db, self.insight, revision="i1", observed_at=T0, parser="insight-fixture",
                      content=json.dumps({"objects": [
                          {"objectId": f"{self.fac}1", "type": "Power Supply", "key": f"{self.fac}PS-1",
                           "attributes": {"serial": "PS-1"}},
                          {"objectId": f"{self.fac}2", "type": "Power Supply", "key": f"{self.fac}PS-2",
                           "attributes": {"serial": "PS-2"}}]}).encode())
        self.r1 = self.config_rev(db, "r1", T0, [("GUNQUA01", "192.168.0.28"), ("GUNQUA02", "192.168.0.29")])
        install(db, self.ws, self.pos(db, "GUNQUA01").uid, self.unit(db, "PS-1").uid)
        db.commit()
        db.close()

    def config_rev(self, db, rev, at, devices):
        return engine.ingest(db, self.config, revision=rev, content=mag_yaml(self.fac, devices), observed_at=at,
                             parser="epik8s-slice")

    def pos(self, db, name):
        return db.scalar(select(Asset).where(Asset.key == f"{self.fac}:POS:{name}/PS"))

    def unit(self, db, serial):
        return db.scalar(select(Asset).where(Asset.key == f"{self.fac}{serial}"))

    def aps(self, db):
        return connectivity.access_points(db, self.ws, "192.168.0.28")


@pytest.fixture()
def ap():
    return APFixture()


def reassign_by_r4(db, f):
    """r3 repeats r1 ten days later (the previous observation); r4, ten days
    after that, names the address for GUNQSK01's power supply instead."""
    f.config_rev(db, "r3", T0 + 10 * DAY, [("GUNQUA01", "192.168.0.28"), ("GUNQUA02", "192.168.0.29")])
    r4 = f.config_rev(db, "r4", T0 + 20 * DAY, [("GUNQSK01", "192.168.0.28"), ("GUNQUA02", "192.168.0.29")])
    # GUNQUA01's position holds a Confirmed Installation, so r4 waits for a person.
    assert r4["state"] == "held"
    engine.approve_revision(db, r4["revision_id"], "controls-steward")
    db.commit()


def test_A17_a_reassigned_address_retires_the_old_access_point_with_a_successor(ap):
    db = SessionLocal()
    [old] = ap.aps(db)
    assert old["position_uid"] == ap.pos(db, "GUNQUA01").uid
    assert db.get(Asset, old["uid"]).key.startswith("AP-")
    assert old["in_service_from"] == {"kind": "before_records", "bound": T0.isoformat()}
    ticket = Issue(uid=str(uuid.uuid4()), workspace_id=ap.ws, asset_uid=old["uid"], title="PS unreachable")
    db.add(ticket)
    db.commit()

    reassign_by_r4(db, ap)
    views = {v["uid"]: v for v in ap.aps(db)}
    old_v = views[old["uid"]]
    [new_v] = [v for v in views.values() if v["uid"] != old["uid"]]
    handover = {"kind": "range", "earliest": (T0 + 10 * DAY).isoformat(), "latest": (T0 + 20 * DAY).isoformat()}
    # The old one keeps what it was, and ends somewhere between the two observations.
    assert old_v["record_status"] == "Retired" and old_v["successor"] == new_v["uid"]
    assert old_v["position_uid"] == ap.pos(db, "GUNQUA01").uid and old_v["in_service_until"] == handover
    # The new one takes the address at the new position, from the same uncertain instant.
    assert new_v["record_status"] == "Active" and new_v["position_uid"] == ap.pos(db, "GUNQSK01").uid
    assert new_v["in_service_from"] == handover and new_v["address"] == "192.168.0.28"
    ref = f"epik8s:{ap.fac}:endpoint:192.168.0.28"
    assert engine.resolve_ref(db, ref) == new_v["uid"]
    assert db.scalar(select(IdentityEvent).where(IdentityEvent.source_ref == ref, IdentityEvent.kind == "rebound"))
    path = db.scalar(select(Asset).where(Asset.key == f"{ap.fac}:PATH:mag-psu:GUNQSK01"))
    assert connectivity.edge_target(db, path.uid, "enters at") == new_v["uid"]
    # One batch, on the record; the old one's ticket stays where it happened.
    assert db.scalar(select(Decision).where(Decision.kind == "reassign", Decision.subject_uid == old["uid"]))
    assert db.scalar(select(RecordEvent).where(RecordEvent.uid == old["uid"], RecordEvent.kind == "successor"))
    db.refresh(ticket)
    assert ticket.asset_uid == old["uid"]
    # The occupied position is flagged, not retired.
    assert ap.pos(db, "GUNQUA01").record_status == "Active"
    db.close()


def test_A18_who_used_an_address_is_certain_outside_the_handover_and_possible_inside_it(ap):
    db = SessionLocal()
    reassign_by_r4(db, ap)
    install(db, ap.ws, ap.pos(db, "GUNQSK01").uid, ap.unit(db, "PS-2").uid)
    db.commit()
    old_pos, new_pos = ap.pos(db, "GUNQUA01").uid, ap.pos(db, "GUNQSK01").uid
    ps1, ps2 = ap.unit(db, "PS-1").uid, ap.unit(db, "PS-2").uid

    def used(t):
        return sorted((r["position_uid"], r["asset_uid"], r["certainty"])
                      for r in connectivity.who_used(db, ap.ws, "192.168.0.28", t))

    assert used(T0 + 5 * DAY) == [(old_pos, ps1, "definite")]
    assert used(T0 + 15 * DAY) == sorted([(old_pos, ps1, "possible"), (new_pos, ps2, "possible")])
    assert used(T0 + 25 * DAY) == [(new_pos, ps2, "definite")]

    # A person who knows when the cable moved replaces the uncertainty with an exact handover.
    old_uid = next(v["uid"] for v in ap.aps(db) if v["record_status"] == "Retired")
    new_uid = next(v["uid"] for v in ap.aps(db) if v["record_status"] == "Active")
    h = temporal.instant(T0 + 14 * DAY)
    engine.apply_decisions(db, ap.ws, "controls-steward", [
        service.confirm_value(old_uid, "attr:in_service_until", h),
        service.confirm_value(new_uid, "attr:in_service_from", h)])
    db.commit()
    assert used(T0 + 14 * DAY - timedelta(seconds=1)) == [(old_pos, ps1, "definite")]
    assert used(T0 + 14 * DAY) == [(new_pos, ps2, "definite")]
    db.close()


def test_A19_an_assignment_is_written_once(ap):
    db = SessionLocal()
    [view] = ap.aps(db)
    other = ap.pos(db, "GUNQUA02").uid
    with pytest.raises(InvariantError) as err:
        engine.apply_decisions(db, ap.ws, "someone", [
            service.confirm_value(view["uid"], "rel:assigned to", {"ref": f"uid:{other}"})])
    assert err.value.code == "I-AP-2"
    db.rollback()
    resp = client.post("/v1/ledger/decisions", headers=ap.headers, json={"batch": [
        {"kind": "confirm", "subject_uid": view["uid"], "predicate": "rel:assigned to",
         "value": {"ref": f"uid:{other}"}}]})
    assert resp.status_code == 409 and "I-AP-2" in resp.text
    # Moving it is a reassignment: the old one retires with a successor.
    resp = client.post(f"/v1/access-points/{view['uid']}/reassign", headers=ap.headers,
                       json={"position_uid": other, "at": temporal.instant(T0 + 3 * DAY)})
    assert resp.status_code == 200, resp.text
    db.expire_all()
    [old] = [v for v in ap.aps(db) if v["uid"] == view["uid"]]
    assert old["record_status"] == "Retired" and old["successor"] == resp.json()["uid"]
    assert resp.json()["position_uid"] == other
    rows = client.get("/v1/access-points", headers=ap.headers,
                      params={"address": "192.168.0.28", "at": (T0 + 4 * DAY).isoformat()}).json()
    assert [r["position_uid"] for r in rows["used_by"]] == [other]
    db.close()


# --------------------------------------------------------------------------- A20–A23

def registry_json(fac, overrides=None):
    """The IT registry: position mxa001 and three converters with 16 ports
    each. M-8800's ports are configured RS-232."""
    overrides = overrides or {}
    records = [{"ref": f"it:{fac}:pos:mxa001", "type": "Equipment Position", "key": f"{fac}:IT:POS:mxa001",
                "name": "scsparcsipmxa001", "attributes": {"position_class": "Serial Converter"}}]
    for conv in ("M-5531", "M-7702", "M-8800"):
        records.append({"ref": f"it:{fac}:eq:{conv}", "type": "Serial Converter", "key": f"{fac}:{conv}", "name": conv})
        for n in range(1, 17):
            attrs = {"port_label": f"P{n}", "port_role": f"serial-data#{n}",
                     "port_kind": "RS-232" if conv == "M-8800" else "RS-485-2w", "operating_mode": "TCP server",
                     "tcp_port": 4000 + n}
            attrs.update(overrides.get((conv, n), {}))
            records.append({"ref": f"it:{fac}:port:{conv}:P{n}", "type": "Equipment Port", "key": f"{fac}:{conv}:P{n}",
                            "name": f"{conv} P{n}", "attributes": attrs, "relations": {"port of": f"it:{fac}:eq:{conv}"}})
    return json.dumps({"records": records}).encode()


def controls_json(fac, interlock_segment=None):
    records = [
        {"ref": f"ctl:{fac}:ap:mxa001", "type": "Access Point", "name": "scsparcsipmxa001",
         "attributes": {"address": "scsparcsipmxa001"}, "relations": {"assigned to": f"it:{fac}:pos:mxa001"}},
        {"ref": f"ctl:{fac}:path:vac", "type": "Communication Path", "name": "vac-gunvpc → mxa001",
         "relations": {"enters at": f"ctl:{fac}:ap:mxa001"}},
    ]
    for n in range(1, 5):
        records.append({"ref": f"ctl:{fac}:seg:{n}", "type": "Bus Segment", "name": f"segment {n}",
                        "attributes": {"required_port": {"role": f"serial-data#{n}", "kind": "RS-485-2w",
                                                         "mode": "TCP server", "tcp_port": 4000 + n},
                                       "safety_class": "interlock" if n == interlock_segment else "none"},
                        "relations": {"served by": f"ctl:{fac}:path:vac"}})
    return json.dumps({"records": records}).encode()


class ITFixture:
    def __init__(self, interlock_segment=None):
        self.fac = f"I{secrets.token_hex(3).upper()}"
        self.it, self.ws = f"it-{secrets.token_hex(3)}", f"ctl-{secrets.token_hex(3)}"
        self.registry, self.controls = f"it-registry:{self.fac}", f"controls:{self.fac}"
        db = SessionLocal()
        db.add_all([Workspace(id=self.it, name="IT"), Workspace(id=self.ws, name="Controls")])
        db.flush()
        engine.register_stream(db, self.registry, self.it, "it-registry",
                               may_create=["Equipment Position", "Serial Converter", "Equipment Port"])
        engine.register_stream(db, self.controls, self.ws, "controls",
                               may_create=["Access Point", "Communication Path", "Bus Segment"])
        engine.activate_policy(db)
        self.registry_rev(db, "it1", T0)
        engine.ingest(db, self.controls, revision="c1", content=controls_json(self.fac, interlock_segment), observed_at=T0,
                      parser="registry-fixture")
        # Each segment's requirement has been confirmed once (§9.3 step 4).
        engine.apply_decisions(db, self.ws, "controls-steward", [
            service.confirm_value(self.seg(db, n).uid, "attr:required_port", self.seg(db, n).attributes["required_port"])
            for n in range(1, 5)])
        self.installation = install(db, self.it, self.pos(db).uid, self.conv(db, "M-5531").uid)
        db.commit()
        db.close()

    def registry_rev(self, db, rev, at, overrides=None):
        return engine.ingest(db, self.registry, revision=rev, content=registry_json(self.fac, overrides),
                             observed_at=at, parser="registry-fixture")

    def pos(self, db):
        return db.scalar(select(Asset).where(Asset.key == f"{self.fac}:IT:POS:mxa001"))

    def conv(self, db, name):
        return db.scalar(select(Asset).where(Asset.key == f"{self.fac}:{name}"))

    def port(self, db, conv, n):
        return db.scalar(select(Asset).where(Asset.key == f"{self.fac}:{conv}:P{n}"))

    def seg(self, db, n):
        return db.scalar(select(Asset).where(Asset.workspace_id == self.ws, Asset.type == "Bus Segment",
                                             Asset.name == f"segment {n}"))

    def attached(self, db, n):
        return db.scalar(select(Relation.to_asset_uid).where(
            Relation.from_asset_uid == self.seg(db, n).uid, Relation.relation_type == "attached to",
            Relation.derivation == "derived"))

    def items(self, db, n, ctype=None):
        q = select(Conflict).where(Conflict.subject_uid == self.seg(db, n).uid)
        if ctype:
            q = q.where(Conflict.conflict_type == ctype)
        return list(db.scalars(q))

    def swap(self, db, conv, at):
        service.swap(db, self.it, "it-operator", self.pos(db).uid, self.conv(db, conv).uid, temporal.instant(at),
                     reason="Replacement")
        db.commit()


@pytest.fixture()
def it():
    return ITFixture()


def test_A20_a_compatible_replacement_attaches_like_for_like(it):
    db = SessionLocal()
    for n in range(1, 5):
        assert it.attached(db, n) == it.port(db, "M-5531", n).uid
    t = engine.now() - 2 * DAY
    it.swap(db, "M-7702", t)
    for n in range(1, 5):
        assert it.attached(db, n) == it.port(db, "M-7702", n).uid
        assert it.items(db, n) == []
    edge = db.scalar(select(Relation).where(Relation.from_asset_uid == it.seg(db, 1).uid,
                                            Relation.relation_type == "attached to"))
    assert edge.rule == "port-match/1"
    before = connectivity.attachments_at(db, it.seg(db, 1).uid, t - timedelta(seconds=1))
    assert before["port_uid"] == it.port(db, "M-5531", 1).uid
    db.close()


def test_A21_an_incompatible_replacement_leaves_segments_unattached_until_the_registry_is_fixed(it):
    db = SessionLocal()
    it.swap(db, "M-8800", engine.now() - 2 * DAY)
    ap_uid = engine.resolve_ref(db, f"ctl:{it.fac}:ap:mxa001")
    implemented = db.scalar(select(Relation.to_asset_uid).where(
        Relation.from_asset_uid == ap_uid, Relation.relation_type == "implemented by"))
    assert implemented == it.conv(db, "M-8800").uid
    for n in range(1, 5):
        assert it.attached(db, n) is None
        [item] = it.items(db, n, "port_mapping_unresolved")
        failed = {p["label"]: p["failed"] for p in item.detail["ports"]}
        assert failed[f"P{n}"] == "3b kind"
    # IT reconfigures the ports; the next derive run attaches them.
    it.registry_rev(db, "it2", T0 + DAY, {("M-8800", n): {"port_kind": "RS-485-2w"} for n in range(1, 17)})
    db.commit()
    for n in range(1, 5):
        assert it.attached(db, n) == it.port(db, "M-8800", n).uid
        assert it.items(db, n) == []
    db.close()


def test_A22_a_safety_segment_needs_a_confirmation_per_installation_and_it_never_overrides_compatibility():
    it = ITFixture(interlock_segment=4)
    db = SessionLocal()
    it.swap(db, "M-7702", engine.now() - 2 * DAY)
    assert it.attached(db, 4) is None
    [item] = it.items(db, 4, "port_confirmation_required")
    assert [c["port_uid"] for c in item.detail["candidates"]] == [it.port(db, "M-7702", 4).uid]
    assert it.attached(db, 1) == it.port(db, "M-7702", 1).uid     # the ordinary segments attach

    engine.apply_decisions(db, it.ws, "controls-steward", [connectivity.confirm_port_map(
        it.seg(db, 4).uid, item.detail["installation_uid"], it.port(db, "M-7702", 4).uid, [])])
    db.commit()
    assert it.attached(db, 4) == it.port(db, "M-7702", 4).uid and it.items(db, 4) == []

    it.registry_rev(db, "it2", T0 + DAY, {("M-7702", 4): {"port_kind": "RS-232"}})
    db.commit()
    assert it.attached(db, 4) is None
    [invalid] = it.items(db, 4, "port_map_invalid")
    assert invalid.detail["failed"] == "3b kind"

    it.swap(db, "M-5531", engine.now() - DAY)
    assert it.attached(db, 4) is None
    assert it.items(db, 4, "port_confirmation_required")
    db.close()


def test_A23_two_ports_with_the_same_role_are_ambiguous(it):
    db = SessionLocal()
    it.registry_rev(db, "it2", T0 + DAY, {("M-7702", 13): {"port_role": "serial-data#3", "tcp_port": 4003}})
    it.swap(db, "M-7702", engine.now() - 2 * DAY)
    assert it.attached(db, 3) is None
    [item] = it.items(db, 3, "port_mapping_unresolved")
    assert sorted(c["label"] for c in item.detail["candidates"]) == ["P13", "P3"]
    assert it.attached(db, 2) == it.port(db, "M-7702", 2).uid
    db.close()


# --------------------------------------------------------------------------- A31

def test_A31_tickets_are_attributed_to_the_unit_installed_at_incident_time_and_counted_once():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    [prop] = proposed_installation(db, s)
    service.confirm_installation(db, s.ws, "operator", prop["uid"], valid_from=temporal.instant("2026-01-01", "day"))
    pos, u1, u2 = s.pos(db), s.unit(db, "84321"), s.unit(db, "90001")
    t = datetime(2026, 6, 1, tzinfo=timezone.utc)

    def ticket(key, attrs):
        issue = Issue(uid=str(uuid.uuid4()), workspace_id=s.ws, asset_uid=pos.uid, title=key, attributes=attrs)
        db.add(issue)
        db.flush()
        return issue

    t1 = ticket("T-1", {"occurred_from": temporal.instant("2026-03-02T10:00:00Z")})
    t2 = ticket("T-2", {"argus_source": "jira", "argus_source_key": f"{s.fac}-2",
                        "argus_source_created": (t + 2 * DAY).isoformat()})
    t3 = ticket("T-3", {"argus_source": "jira", "argus_source_key": f"{s.fac}-3",
                        "argus_source_created": "2025-06-01T09:00:00+00:00"})
    # The legacy object became the position and 84321 (§12.4).
    db.add(MigrationMap(legacy_uid=pos.uid, new_uid=u1.uid, role="equipment", plan_id="slice"))
    db.commit()
    # The swap re-derives the links of every ticket on the position.
    service.swap(db, s.ws, "operator", pos.uid, u2.uid, temporal.instant(t), reason="Failure")
    db.commit()

    def links(issue):
        return sorted((l["asset_uid"], l["role"], l["certainty"], l["origin"])
                      for l in tickets.links_of_ticket(db, issue.uid) if l["role"] != "subject")

    assert links(t1) == [(u1.uid, "involved_equipment", "definite", "derived")]
    assert links(t2) == sorted([(u1.uid, "involved_equipment", "possible", "derived"),
                                (u2.uid, "involved_equipment", "possible", "derived")])
    assert links(t3) == [(u1.uid, "involved_equipment", "possible", "migration-split")]
    db.refresh(t2)
    assert t2.attributes["occurrence_source"] == "legacy_created_fallback"
    assert tickets.record_counts(db, pos.uid)["subject"] == 3
    assert tickets.record_counts(db, u1.uid)["involved"] == 1
    assert tickets.group_count(db, [pos.uid, u1.uid, u2.uid]) == 3
    db.close()


def test_a_ticket_created_through_the_api_is_attributed_at_once():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    [prop] = proposed_installation(db, s)
    service.confirm_installation(db, s.ws, "operator", prop["uid"], valid_from=temporal.instant("2026-01-01", "day"))
    db.commit()
    pos, unit = s.pos(db), s.unit(db)
    resp = client.post("/v1/issues", headers=s.headers, json={
        "uid": str(uuid.uuid4()), "title": "Pressure spike", "asset_uid": pos.uid,
        "attributes": {"occurred_from": temporal.instant("2026-04-01T08:00:00Z")}})
    assert resp.status_code == 201, resp.text
    ctx = client.get(f"/v1/ledger/tickets/{resp.json()['uid']}/links", headers=s.headers).json()
    assert {(l["asset_uid"], l["role"], l["certainty"]) for l in ctx} >= {(unit.uid, "involved_equipment",
                                                                           "definite")}
    db.close()


# --------------------------------------------------------------------------- A32

def _events(db, stream_id, since):
    return list(db.scalars(select(ClaimEvent).where(ClaimEvent.stream_id == stream_id, ClaimEvent.seq > since)))


def _max_seq(db):
    return db.scalar(select(func.max(ClaimEvent.seq))) or 0


def _positions(db, s):
    return {a.key: a.attributes.get("position_class") for a in db.scalars(select(Asset).where(
        Asset.workspace_id == s.ws, Asset.type == "Equipment Position"))}


def _exists_status(db, uid):
    return {f.status for f in db.scalars(select(FactState).where(FactState.subject_uid == uid,
                                                                 FactState.predicate == "exists"))
            if f.contributor.startswith("claim:")} - {"withdrawn"}


def test_A32_rule_identity_and_versions():
    s = Slice()
    db = SessionLocal()
    s.config_rev(db, extra=("GUNIONP01",))
    db.commit()
    # A rejection under /1 does not carry to /2, which does not declare it.
    sip2 = s.pos(db, "GUNSIP02")
    [c] = [c for c in engine._claims_for_subject(db, sip2.uid) if c[0].predicate == "exists"]
    engine.apply_decisions(db, s.ws, "reviewer", [{"kind": "reject", "target": {"claim_id": c[0].claim_id,
                                                                                "scope": "fingerprint"}}])
    db.commit()
    assert _exists_status(db, sip2.uid) == {"rejected"}

    engine.activate_ruleset(db, s.ws, {"infer.vac.sip": "infer.vac.sip/2"}, {"infer.vac.sip/2": "2.0"}, "rules-owner")
    db.commit()
    assert _exists_status(db, sip2.uid) == {"accepted"}
    assert _positions(db, s)[f"{s.fac}:POS:GUNIONP01"] == "Ion pump"      # the 2.0 bug
    # Now reject GUNSIP00 under /2; /3 will carry it.
    sip0 = s.pos(db, "GUNSIP00")
    [c] = [c for c in engine._claims_for_subject(db, sip0.uid) if c[0].predicate == "exists" and c[2]]
    engine.apply_decisions(db, s.ws, "reviewer", [{"kind": "reject", "target": {"claim_id": c[0].claim_id,
                                                                                "scope": "fingerprint"}}])
    db.commit()

    # 1. A refactor: same output, new implementation — no claim events.
    mark = _max_seq(db)
    engine.activate_ruleset(db, s.ws, {"infer.vac.sip": "infer.vac.sip/2"}, {"infer.vac.sip/2": "2.1"}, "rules-owner")
    db.commit()
    assert _events(db, s.config, mark) == []
    run = db.scalar(select(JobRun).where(JobRun.stage == "parse", JobRun.scope == s.config)
                    .order_by(JobRun.id.desc()).limit(1))
    assert run.status == "ran" and "infer.vac.sip/2=2.1" in run.counts["impl_version"]

    # 2. A fix within the meaning: only the output it changes.
    mark = _max_seq(db)
    engine.activate_ruleset(db, s.ws, {"infer.vac.sip": "infer.vac.sip/2"}, {"infer.vac.sip/2": "2.2"}, "rules-owner")
    db.commit()
    evs = _events(db, s.config, mark)
    assert sorted(e.kind for e in evs) == ["appeared", "disappeared"]
    assert all(db.get(Claim, e.claim_id).rule_id == "infer.vac.sip/2" for e in evs)
    assert all("infer.vac.sip/2=2.2" in e.impl_version for e in evs)
    before = _positions(db, s)
    assert before[f"{s.fac}:POS:GUNIONP01"] == "Ion Pump"

    # 3. A new meaning: every output is a new /3 claim, every /2 claim goes;
    #    the facts do not move, and the rejection carries because /3 says so.
    head = db.get(StreamHead, s.config).published_number
    live2 = {cid for cid in engine._presence(db, s.config, head) if db.get(Claim, cid).rule_id == "infer.vac.sip/2"}
    mark = _max_seq(db)
    engine.activate_ruleset(db, s.ws, {"infer.vac.sip": "infer.vac.sip/3"}, {}, "rules-owner")
    db.commit()
    evs = _events(db, s.config, mark)
    gone = {e.claim_id for e in evs if e.kind == "disappeared"}
    new = [db.get(Claim, e.claim_id) for e in evs if e.kind == "appeared"]
    assert gone == live2 and len(new) == len(live2)
    assert all(c.rule_id == "infer.vac.sip/3" for c in new)
    assert _positions(db, s) == before
    assert _exists_status(db, sip0.uid) == {"rejected"}
    carried = db.scalar(select(Decision).where(Decision.actor == "policy", Decision.kind == "reject",
                                               Decision.workspace_id == s.ws))
    assert carried.target["rules"] == ["infer.vac.sip/2", "infer.vac.sip/3"]

    # 4. The CI check: a signature change under an unchanged id fails.
    assert rules.check_catalogue() == []
    changed = copy.deepcopy(rules.RULES)
    changed["infer.vac.sip/3"]["signature"]["value_domain"]["attr:position_class"] = ["Ion Pump", "Getter Pump"]
    assert any("infer.vac.sip/3: output signature changed without a new rule id" in e
               for e in rules.check_catalogue(changed))
    db.close()


def test_the_committed_rule_catalogue_passes_the_ci_check():
    assert rules.check_catalogue() == []
