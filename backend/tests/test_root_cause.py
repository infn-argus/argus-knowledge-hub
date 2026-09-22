"""Impact and root-cause analysis.

The cases are a small beamline built to have the shapes that matter: a converter serving two IOCs, a
supply powering a magnet, a chiller cooling a structure, an assembly missing a part. What is worth
pinning is what a failure must *not* reach: an IOC that stops does not stop the pump it reads.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetTicket
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services import causal_model as cm
from app.services.root_cause import blast_radius, impact_of, root_causes


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def world():
    """A workspace with a beamline in it. `w.key("AP1")` is a key; `w.link(a, r, b)` a relation."""
    db = SessionLocal()
    tag = secrets.token_hex(3).upper()
    ws = f"rca-{secrets.token_hex(4)}"
    db.add(Workspace(id=ws, name="RCA"))
    db.flush()
    db.add(Schema(uid=f"{ws}:t", workspace_id=ws, name="Thing", applies_to="objects", attributes=[]))
    db.flush()

    class World:
        pass

    w = World()
    w.db, w.ws, w.tag, w.assets = db, ws, tag, {}

    def key(name):
        return f"{tag}:{name}"

    def add(name, type_="Thing", **attrs):
        a = Asset(uid=f"{ws}:{name}", workspace_id=ws, schema_uid=f"{ws}:t", key=key(name), name=name,
                  type=type_, attributes=attrs)
        db.add(a)
        db.flush()
        w.assets[name] = a
        return a

    def link(a, relation, b):
        db.add(Relation(workspace_id=ws, from_asset_uid=w.assets[a].uid, to_asset_uid=w.assets[b].uid,
                        relation_type=relation))
        db.flush()

    w.key, w.add, w.link = key, add, link

    # control path: a converter serving two IOCs, each with a device that acts on a pump
    for name, kind in [("AP1", "Access Point"), ("PUMP1", "Ion Pump"),
                       ("PUMP2", "Ion Pump"), ("PUMP3", "Ion Pump"), ("SECT", "Section"),
                       ("CFG", "Control Configuration")]:
        add(name, kind)
    add("IOC1", "IOC", pv_prefix=key("IOC1"))
    add("IOC2", "IOC", pv_prefix=key("IOC2"))
    link("IOC1", "connects to", "AP1")
    link("IOC2", "connects to", "AP1")
    for dev, ioc, pump in [("D1", "IOC1", "PUMP1"), ("D2", "IOC1", "PUMP2"), ("D3", "IOC2", "PUMP3")]:
        add(dev, "Control Device", pv=f"{key(dev)}:PV")
        link(dev, "provided by", ioc)
        link(dev, "acts on", pump)
        link(dev, "declared in", "CFG")
    link("IOC1", "declared in", "CFG")
    # the vacuum element the first pump realises, in a section
    add("ELM1", "Vacuum Sector")
    link("ELM1", "realized by", "PUMP1")
    link("PUMP1", "part of", "SECT")

    # power: a supply and its magnet, controlled through IOC2
    add("PSU", "Power Supply")
    add("MAG", "Quadrupole")
    add("DPSU", "Control Device")
    link("PSU", "powers", "MAG")
    link("DPSU", "acts on", "PSU")
    link("DPSU", "provided by", "IOC2")

    # cooling and composition
    add("CHILL", "Chiller")
    add("STRUCT", "Accelerating Structure")
    link("CHILL", "cools", "STRUCT")
    add("STATION", "Screen Station")
    add("CAM", "Camera")
    add("ACT", "Actuator")
    link("STATION", "composed of", "CAM")
    link("STATION", "composed of", "ACT")
    db.commit()
    yield w
    db.rollback()
    db.query(Relation).filter(Relation.workspace_id == ws).delete()
    db.query(AssetTicket).filter(AssetTicket.asset_uid.like(f"{ws}:%")).delete(synchronize_session=False)
    db.query(Asset).filter(Asset.workspace_id == ws).delete()
    db.query(Schema).filter(Schema.workspace_id == ws).delete()
    db.query(Workspace).filter(Workspace.id == ws).delete()
    db.commit()
    db.close()


def keys(result, w):
    return {a["key"].split(":", 1)[1] for a in result["affected"]}


def by_key(result, w, name):
    return next(a for a in result["affected"] if a["key"] == w.key(name))


# --- the model itself -------------------------------------------------------------------------------------------------

def test_a_failure_goes_from_provider_to_dependent_whichever_way_the_edge_is_stored():
    assert cm.dependency("device", "ioc", "provided by") == ("ioc", "device")      # stored dependent → provider
    assert cm.dependency("psu", "magnet", "powers") == ("psu", "magnet")           # stored provider → dependent
    assert cm.dependency("device", "config", "declared in") is None                # nothing crosses it
    assert cm.dependency("a", "b", "some relation nobody classified") is None


def test_what_a_node_has_lost_decides_where_it_can_go_next():
    assert cm.follows(cm.FUNCTION, cm.CONTROL) and cm.follows(cm.FUNCTION, cm.FUNCTION)
    assert cm.follows(cm.CONTROL, cm.CONTROL)
    assert not cm.follows(cm.CONTROL, cm.FUNCTION)        # lost readout is not lost function
    assert not cm.follows(cm.PERMIT, cm.FUNCTION) and not cm.follows(cm.PERMIT, cm.CONTROL)


def test_every_relation_type_has_a_layer_a_direction_and_a_loss():
    for name, meaning in cm.SEMANTICS.items():
        assert meaning.layer in cm.LAYERS, name
        assert meaning.flows in (cm.FORWARD, cm.REVERSE, cm.NONE), name
        assert (meaning.carries is None) == (meaning.flows == cm.NONE), name


# --- impact -----------------------------------------------------------------------------------------------------------

def test_a_stopped_converter_takes_the_readout_of_everything_behind_it(world):
    result = impact_of(world.db, world.ws, world.key("AP1"))
    assert {"IOC1", "IOC2", "D1", "D2", "D3", "PUMP1", "PUMP2", "PUMP3", "DPSU", "PSU"} <= keys(result, world)
    assert all(a["losses"] == {"control": a["depth"]} for a in result["affected"])


def test_lost_readout_does_not_stop_what_is_read(world):
    """The pump is still pumping and the magnet still powered: nobody can see it, which is not the same."""
    result = impact_of(world.db, world.ws, world.key("AP1"))
    assert "ELM1" not in keys(result, world)              # the element the pump realises
    assert "MAG" not in keys(result, world)               # the magnet its supply powers
    assert "SECT" not in keys(result, world)


def test_a_failed_pump_reaches_the_element_it_realises_and_the_section_it_is_in(world):
    result = impact_of(world.db, world.ws, world.key("PUMP1"))
    assert keys(result, world) == {"ELM1", "SECT"}
    assert by_key(result, world, "ELM1")["losses"] == {"function": 1}
    assert by_key(result, world, "SECT")["weak"] is True         # membership degrades, it does not remove


def test_a_failed_supply_takes_its_magnet_and_nothing_upstream(world):
    result = impact_of(world.db, world.ws, world.key("PSU"))
    assert keys(result, world) == {"MAG"}


def test_a_chiller_takes_what_it_cools(world):
    result = impact_of(world.db, world.ws, world.key("CHILL"))
    assert keys(result, world) == {"STRUCT"} and by_key(result, world, "STRUCT")["layers"] == ["cooling"]


def test_an_assembly_is_degraded_by_the_loss_of_a_part(world):
    result = impact_of(world.db, world.ws, world.key("CAM"))
    assert keys(result, world) == {"STATION"} and by_key(result, world, "STATION")["losses"] == {"degradation": 1}


def test_provenance_edges_carry_no_failure(world):
    assert impact_of(world.db, world.ws, world.key("CFG"))["affected"] == []


def test_a_walk_can_be_limited_to_some_layers(world):
    assert impact_of(world.db, world.ws, world.key("AP1"), layers=["power"])["affected"] == []
    only_control = impact_of(world.db, world.ws, world.key("AP1"), layers=["control"])
    assert "PSU" in keys(only_control, world)


def test_every_affected_object_says_how_it_was_reached(world):
    result = impact_of(world.db, world.ws, world.key("AP1"))
    d3 = by_key(result, world, "D3")
    assert [h["relation"] for h in d3["path"]] == ["connects to", "provided by"]
    assert d3["depth"] == 2 and d3["layers"] == ["control"]


def test_an_unknown_object_is_none_and_an_unclassified_relation_is_reported_not_dropped(world):
    assert impact_of(world.db, world.ws, "no-such-thing") is None
    world.link("CAM", "somehow related to", "ACT")
    world.db.commit()
    assert impact_of(world.db, world.ws, world.key("CAM"))["unclassified_relations"] == {"somehow related to": 1}


def test_a_soft_deleted_object_is_not_in_the_graph(world):
    from datetime import datetime, timezone
    world.assets["D3"].deleted_at = datetime.now(timezone.utc)
    world.db.commit()
    assert "D3" not in keys(impact_of(world.db, world.ws, world.key("IOC2")), world)


def test_an_inferred_object_on_a_path_is_flagged(world):
    world.assets["PUMP1"].attributes = {"argus_keywords": ["inferred"]}
    world.db.commit()
    assert by_key(impact_of(world.db, world.ws, world.key("AP1")), world, "PUMP1")["via_inference"] is True
    assert by_key(impact_of(world.db, world.ws, world.key("AP1")), world, "D1")["via_inference"] is False


# --- root cause -------------------------------------------------------------------------------------------------------

def top(result):
    return [c["key"].split(":", 1)[1] for c in result["candidates"]]


def test_two_symptoms_behind_different_iocs_point_at_the_converter_they_share(world):
    result = root_causes(world.db, world.ws, [world.key("D1"), world.key("D3")])
    assert top(result)[0] == "AP1"
    assert result["candidates"][0]["coverage"] == 1.0
    assert result["hypotheses"][0]["unexplained"] == []
    assert [c["key"].split(":", 1)[1] for c in result["hypotheses"][0]["causes"]] == ["AP1"]


def test_one_symptom_points_at_the_nearest_thing_that_explains_it(world):
    result = root_causes(world.db, world.ws, [world.key("D1")])
    assert top(result)[0] == "D1"            # its own failure is the smallest hypothesis
    assert {"IOC1", "AP1"} <= set(top(result))


def test_a_healthy_neighbour_rules_out_the_hypothesis_that_would_have_taken_it_down(world):
    """D3 answers, so the converter (which it depends on) cannot be down, and the IOC must be."""
    result = root_causes(world.db, world.ws, [world.key("D1"), world.key("D2")], healthy=[world.key("D3")])
    ranked = {c["key"].split(":", 1)[1]: c for c in result["candidates"]}
    assert top(result)[0] == "IOC1"
    assert ranked["AP1"]["contradicted_by"] == [world.key("D3")]
    assert ranked["AP1"]["fit"] < ranked["IOC1"]["fit"]


def test_a_refuted_cause_is_not_offered_as_the_fewest_causes(world):
    """D2 answers, and it hangs from the same IOC and converter as D1: neither can be down, so D1's
    own fault is what is left for it, and the other symptom's IOC is still open."""
    result = root_causes(world.db, world.ws, [world.key("D1"), world.key("D3")], healthy=[world.key("D2")])
    causes = {c["key"].split(":", 1)[1] for c in result["hypotheses"][0]["causes"]}
    assert causes == {"D1", "IOC2"} and result["hypotheses"][0]["unexplained"] == []
    assert "AP1" not in causes and "IOC1" not in causes


def test_a_condition_that_is_not_met_is_caused_by_what_gates_it_and_by_a_lost_readout(world):
    """RF conditioning is enabled by a pump: the pump failing, or being unreadable, both stop it."""
    world.add("COND", "IOC")
    world.link("COND", "enabled by", "PUMP1")
    world.db.commit()
    result = root_causes(world.db, world.ws, [world.key("COND")], symptom_kind={world.key("COND"): "permit"})
    ranked = top(result)
    assert {"PUMP1", "D1", "IOC1", "AP1"} <= set(ranked)         # unreadable: the whole control chain
    impact = impact_of(world.db, world.ws, world.key("PUMP1"))
    assert by_key(impact, world, "COND")["losses"] == {"permit": 1}
    # ...but a permit lost does not break what the conditioning IOC drives
    assert keys(impact_of(world.db, world.ws, world.key("COND")), world) == set()


def test_a_control_symptom_cannot_be_caused_by_a_supply(world):
    """A magnet whose readout is gone: the supply that powers it is not a suspect, the IOC is."""
    result = root_causes(world.db, world.ws, [world.key("PSU")], symptom_kind={world.key("PSU"): "control"})
    assert "DPSU" in top(result) and "IOC2" in top(result)
    # a function symptom on the magnet, by contrast, is the supply's doing and not the IOC's
    magnet = root_causes(world.db, world.ws, [world.key("MAG")], symptom_kind={world.key("MAG"): "function"})
    assert "PSU" in top(magnet) and "IOC2" not in top(magnet) and "AP1" not in top(magnet)


def test_symptoms_with_unrelated_causes_are_explained_by_two_hypotheses(world):
    result = root_causes(world.db, world.ws, [world.key("D1"), world.key("STRUCT")])
    causes = {c["key"].split(":", 1)[1] for c in result["hypotheses"][0]["causes"]}
    assert "CHILL" in causes and len(result["hypotheses"][0]["causes"]) == 2
    assert result["hypotheses"][0]["unexplained"] == []


def test_an_object_nothing_connects_to_is_its_own_explanation_not_a_missing_record(world):
    """An object nothing connects to exists: it is its own only explanation, not a missing record."""
    world.add("ORPHAN")
    world.db.commit()
    result = root_causes(world.db, world.ws, [world.key("D1"), world.key("ORPHAN")])
    assert result["not_found"] == []
    assert {c["key"].split(":", 1)[1] for c in result["hypotheses"][0]["causes"]} >= {"ORPHAN"}
    assert impact_of(world.db, world.ws, world.key("ORPHAN"))["affected"] == []


def test_each_candidate_carries_the_path_to_each_symptom_and_how_far_it_would_reach(world):
    result = root_causes(world.db, world.ws, [world.key("D3")])
    ap1 = next(c for c in result["candidates"] if c["key"] == world.key("AP1"))
    explained = ap1["explains"][0]
    assert [h["relation"] for h in explained["path"]] == ["connects to", "provided by"]
    assert explained["loss"] == "control" and ap1["would_also_affect"] >= 8


def test_tickets_that_named_a_candidate_before_are_reported_as_evidence(world):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    world.db.add(AssetTicket(uid=f"{world.ws}:tk", asset_uid=world.assets["AP1"].uid, ticket_key="OPS-41",
                             summary="converter lost power", type="Bug", status="Done", created=now, updated=now))
    world.db.commit()
    result = root_causes(world.db, world.ws, [world.key("D1"), world.key("D3")])
    assert next(c for c in result["candidates"] if c["key"] == world.key("AP1"))["history"] == \
        {"tickets": 1, "recent": ["OPS-41"]}


def test_symptoms_that_are_not_in_the_graph_are_named(world):
    result = root_causes(world.db, world.ws, [world.key("D1"), "nope"])
    assert result["not_found"] == ["nope"] and top(result)


# --- single points of failure ---------------------------------------------------------------------------------------

def test_the_blast_radius_weighs_a_lost_function_over_a_lost_readout_and_lists_both(world):
    result = blast_radius(world.db, world.ws)
    ap1 = next(a for a in result["assets"] if a["key"] == world.key("AP1"))
    assert ap1["control"] >= 9 and ap1["function"] == 0            # readout, not function
    assert ap1["weight"] == ap1["control"] + ap1["degradation"] + ap1["permit"]
    # a chiller stops one structure: three times the weight of one blind channel
    chill = next(a for a in result["assets"] if a["key"] == world.key("CHILL"))
    assert chill["function"] == 1 and chill["weight"] == 3
    by_function = [a["key"].split(":", 1)[1] for a in result["by_function"]]
    assert set(by_function[:4]) <= {"PUMP1", "CHILL", "PSU", "CAM", "ACT", "PUMP2", "PUMP3"} and "AP1" not in by_function
    assert result["by_readout"][0]["key"] == world.key("AP1")


def test_a_workspace_with_no_relations_has_no_single_points_of_failure():
    db = SessionLocal()
    ws = f"rca-empty-{secrets.token_hex(3)}"
    db.add(Workspace(id=ws, name="Empty"))
    db.commit()
    try:
        assert blast_radius(db, ws)["assets"] == []
        assert root_causes(db, ws, ["x"])["candidates"] == []
    finally:
        db.query(Workspace).filter(Workspace.id == ws).delete()
        db.commit()
        db.close()


# --- the API and the assistant's tools ---------------------------------------------------------------------------

import json

from fastapi.testclient import TestClient

from app.auth import hash_token
from app.main import app
from app.models.api_token import ApiToken

client = TestClient(app)


@pytest.fixture()
def token(world):
    raw = secrets.token_urlsafe(16)
    world.db.add(ApiToken(workspace_id=world.ws, token_hash=hash_token(raw)))
    world.db.commit()
    yield {"Authorization": f"Bearer {raw}"}
    world.db.query(ApiToken).filter(ApiToken.workspace_id == world.ws).delete()
    world.db.commit()


def test_impact_is_asked_by_key(world, token):
    body = client.get("/v1/graph/impact", params={"uid": world.key("CHILL")}, headers=token).json()
    assert body["origin"]["key"] == world.key("CHILL")
    assert [a["key"] for a in body["affected"]] == [world.key("STRUCT")]


def test_impact_of_something_that_is_not_there_is_a_404_and_a_wrong_layer_a_422(world, token):
    assert client.get("/v1/graph/impact", params={"uid": "nope"}, headers=token).status_code == 404
    bad = client.get("/v1/graph/impact", params={"uid": world.key("AP1"), "layers": "gravity"}, headers=token)
    assert bad.status_code == 422 and "gravity" in bad.json()["detail"]


def test_root_cause_is_posted_with_what_is_known(world, token):
    body = client.post("/v1/graph/root-cause", headers=token, json={
        "symptoms": [world.key("D1"), world.key("D2")], "healthy": [world.key("D3")],
        "symptom_kind": {world.key("D1"): "control", world.key("D2"): "control"}}).json()
    assert body["candidates"][0]["key"] == world.key("IOC1")
    assert body["hypotheses"][0]["unexplained"] == []
    assert client.post("/v1/graph/root-cause", headers=token,
                       json={"symptoms": [world.key("D1")], "symptom_kind": {world.key("D1"): "sad"}}
                       ).status_code == 422


def test_the_blast_radius_is_available(world, token):
    body = client.get("/v1/graph/blast-radius", params={"top": 3}, headers=token).json()
    assert len(body["assets"]) == 3 and body["considered"] > 3


def test_the_rules_the_analysis_runs_on_can_be_read(world, token):
    body = client.get("/v1/graph/relation-semantics", headers=token).json()
    assert body["relations"]["provided by"] == {
        "layer": "control", "flows": "reverse", "carries": "control", "weak": False,
        "note": "device → IOC: the IOC stops, the device loses its readout"}
    assert set(body["layers"]) >= {"control", "power", "cooling", "timing"}


def rpc_tool(token, name, arguments):
    resp = client.post("/mcp", headers=token, json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}})
    body = resp.json()["result"]
    assert body["isError"] is False, body
    return json.loads(body["content"][0]["text"])


def test_an_assistant_can_ask_what_a_failure_reaches_and_gets_paths_it_can_quote(world, token):
    result = rpc_tool(token, "impact_analysis", {"uid_or_key": world.key("AP1"), "limit": 3})
    assert result["found"] and result["count"] >= 9 and result["shown"] == 3
    assert result["affected"][0]["path"].startswith(world.key("AP1")) and "--connects to-->" in result["affected"][0]["path"]
    assert result["by_loss"] == {"control": result["count"]}
    assert rpc_tool(token, "impact_analysis", {"uid_or_key": "nope"}) == {"found": False}


def test_an_assistant_can_ask_what_explains_a_set_of_symptoms(world, token):
    result = rpc_tool(token, "root_cause_analysis", {
        "symptoms": f"{world.key('D1')},{world.key('D3')}", "control_symptoms": f"{world.key('D1')},{world.key('D3')}"})
    first = result["candidates"][0]
    assert first["key"] == world.key("AP1") and len(first["explains"]) == 2
    assert first["explains"][0]["path"].count("--") >= 4
    assert result["fewest_causes"][0]["unexplained"] == []


def test_the_tools_are_listed(world, token):
    names = {t["name"] for t in client.post("/mcp", headers=token,
             json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]}
    assert {"impact_analysis", "root_cause_analysis", "single_points_of_failure"} <= names
    assert rpc_tool(token, "single_points_of_failure", {"top": 2})["assets"]



# --- alarms: no live feed, but the same translation one would need ----------------------------------------------

from app.services.alarm_symptoms import Alarm, build_index, infer_kind, resolve, root_cause_from_alarms


def test_severity_reads_as_a_readout_or_a_function_loss_never_a_permit():
    assert infer_kind("INVALID", "") == "control"
    assert infer_kind("OK", "Archive_Disconnected") == "control"     # the status says it plainly
    assert infer_kind("MAJOR", "HIHI") == "function"
    assert infer_kind("MINOR", "LOW") == "function"
    assert infer_kind("OK", "") is None
    assert infer_kind("UNKNOWN", "") is None                          # not guessed


def test_a_disconnected_device_alarm_resolves_to_the_device_itself(world):
    index = build_index(world.db, world.ws)
    r = resolve(Alarm(world.key("D1") + ":PV", "INVALID", "Client_Timeout"), index)
    assert (r.key, r.kind) == (world.key("D1"), "control")


def test_a_value_alarm_resolves_to_what_the_device_acts_on(world):
    index = build_index(world.db, world.ws)
    r = resolve(Alarm(world.key("D1") + ":PV", "MAJOR", "HIHI"), index)
    assert (r.key, r.kind) == (world.key("PUMP1"), "function")


def test_a_permit_alarm_is_never_inferred_and_only_used_when_given(world):
    index = build_index(world.db, world.ws)
    healthy = resolve(Alarm(world.key("D1") + ":PV", "OK", ""), index)
    assert healthy.kind is None                                       # OK carries no kind on its own
    stated = resolve(Alarm(world.key("D1") + ":PV", "MAJOR", "HIHI", kind="permit"), index)
    assert stated.kind == "permit" and stated.key == world.key("PUMP1")


def test_a_heartbeat_alarm_on_the_iocs_own_prefix_is_a_control_symptom_on_the_ioc(world):
    index = build_index(world.db, world.ws)
    r = resolve(Alarm(world.key("IOC1") + ":Heartbeat", "INVALID", ""), index)
    assert (r.key, r.kind) == (world.key("IOC1"), "control")
    assert "not an exact device PV" in r.note


def test_a_pv_nothing_carries_is_reported_not_dropped(world):
    index = build_index(world.db, world.ws)
    r = resolve(Alarm("NOBODY:HAS:THIS", "MAJOR", "HIGH"), index)
    assert r.key is None and "no object" in r.note


def test_two_alarms_behind_different_iocs_point_at_the_converter_through_the_full_call(world):
    result = root_cause_from_alarms(world.db, world.ws, [
        {"pv": f"{world.key('D1')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": f"{world.key('D3')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": "NOBODY:HAS:THIS", "severity": "MAJOR", "status": "HIGH"},
    ])
    assert result["candidates"][0]["key"] == world.key("AP1")
    assert result["placed"] == 2
    assert result["unresolved"] == [{"pv": "NOBODY:HAS:THIS", "severity": "MAJOR", "status": "HIGH",
                                     "reason": "no object in this workspace carries this PV"}]


def test_an_ok_alarm_becomes_a_healthy_object_without_being_asked_twice(world):
    """D2 answers (OK), and it hangs from the same IOC and converter as D1: neither can be down, so
    D1's own fault is what is left — exactly as giving `healthy` by hand would produce."""
    result = root_cause_from_alarms(world.db, world.ws, [
        {"pv": f"{world.key('D1')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": f"{world.key('D2')}:PV", "severity": "OK"},
    ])
    assert result["candidates"][0]["key"] == world.key("D1")
    refuted = {c["key"]: c for c in result["candidates"] if c["key"] in (world.key("IOC1"), world.key("AP1"))}
    assert all(c["contradicted_by"] == [world.key("D2")] for c in refuted.values())


def test_no_usable_alarms_is_an_empty_answer_not_an_error(world):
    result = root_cause_from_alarms(world.db, world.ws, [{"pv": f"{world.key('D1')}:PV", "severity": "OK"}])
    assert result["candidates"] == [] and result["symptoms"] == []


def test_the_worse_of_two_alarms_on_one_object_is_kept(world):
    """A device reported both disconnected and, moments before, out of range: the graph should not
    quietly settle for the milder claim."""
    result = root_cause_from_alarms(world.db, world.ws, [
        {"pv": f"{world.key('D1')}:PV", "severity": "MAJOR", "status": "HIHI"},
        {"pv": f"{world.key('D1')}:PV", "severity": "INVALID", "status": "Disconnected"},
    ])
    assert result["candidates"][0]["explains"][0]["loss"] == "function"


# --- through the API and the assistant's tools ------------------------------------------------------------------

def test_root_cause_from_alarms_is_posted_as_a_feed(world, token):
    body = client.post("/v1/graph/root-cause/from-alarms", headers=token, json={"alarms": [
        {"pv": f"{world.key('D1')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": f"{world.key('D3')}:PV", "severity": "INVALID", "status": "Disconnected"},
    ]}).json()
    assert body["candidates"][0]["key"] == world.key("AP1")
    bad = client.post("/v1/graph/root-cause/from-alarms", headers=token, json={"alarms": []})
    assert bad.status_code == 422


def test_an_assistant_can_ask_root_cause_from_a_raw_alarm_list(world, token):
    result = rpc_tool(token, "root_cause_from_alarms", {"alarms": [
        {"pv": f"{world.key('D1')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": f"{world.key('D3')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": "NOBODY:HAS:THIS", "severity": "MAJOR"},
    ]})
    assert result["candidates"][0]["key"] == world.key("AP1")
    assert result["unresolved"] == [{"pv": "NOBODY:HAS:THIS", "severity": "MAJOR", "status": "",
                                     "reason": "no object in this workspace carries this PV"}]


def test_the_alarm_tool_is_listed(world, token):
    names = {t["name"] for t in client.post("/mcp", headers=token,
             json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]}
    assert "root_cause_from_alarms" in names


def test_an_unresolved_healthy_alarm_is_reported_too_not_silently_dropped(world):
    """A person mistyping a PV they claim is healthy must not have it vanish without a trace."""
    result = root_cause_from_alarms(world.db, world.ws, [
        {"pv": f"{world.key('D1')}:PV", "severity": "INVALID", "status": "Disconnected"},
        {"pv": "NOBODY:CLAIMS:THIS:IS:OK", "severity": "OK"},
    ])
    assert {"pv": "NOBODY:CLAIMS:THIS:IS:OK", "severity": "OK", "status": "",
           "reason": "no object in this workspace carries this PV"} in result["unresolved"]
