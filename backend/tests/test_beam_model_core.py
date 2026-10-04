"""The canonical beam model library (app/beam_model_core): no database, the same code the Toolbox runs.

Architectural requirements (docs/beam-model-format.md §13) on the six fixtures — ring, linac, branched
transfer line, laser transport, physical apertures, collider IR — and asset matching (docs/beam-asset-sync.md)
against mock Knowledge Hub assets.
"""
import copy
import json
from pathlib import Path

import pytest

from app.beam_model_core import matching as M
from app.beam_model_core import queries as Q
from app.beam_model_core import vocabulary as V
from app.beam_model_core.network import Network, resolve
from app.beam_model_core.schema import SCHEMA_VERSION, json_schema
from app.beam_model_core.upgrade import upgrade
from app.beam_model_core.validation import load

FX = Path(__file__).parent / "fixtures" / "beam_model"


def fixture(name: str):
    doc, rep = load(json.loads((FX / name).read_text()))
    assert rep.ok, rep.errors
    return doc, rep


def assets():
    return json.loads((FX / "ring_assets.json").read_text())


def sync(existing=None, assets_=None, **cfg):
    doc, _ = fixture("ring.beam.json")
    fx = assets()
    r = M.run(doc, assets_ if assets_ is not None else fx["assets"],
              fx["existing"] if existing is None else existing,
              M.Config(naming_rules=fx["naming_rules"], **cfg), dataset="design-2026")
    return {p["component"]: p for p in r["proposals"]}, r


# =========================================================================== topology: one abstraction

def test_a_ring_is_an_ordinary_closed_path_with_no_ring_specific_concept():
    doc, rep = fixture("ring.beam.json")
    net = Network.of(doc)
    ring = net.order("accumulator-ring")
    assert ring[-1] in [n for n, k in net.pred[ring[0]] if k == "closes"] or \
        (ring[0], "closes") in net.succ[ring[-1]]
    # round the ring from the last element: the first is next
    after_last = [n.component for n, _d, _k in net.walk(ring[-1], "downstream", 1)]
    assert ring[0].component in after_last
    # between two elements: the shorter way round
    between = net.between("QUAA105", "QUAA101", path="accumulator-ring")
    assert len(between) < len(ring) / 2 and "SEPA101" in [n.component for n in between]
    assert "TOPOLOGY" in rep.levels


def test_a_linac_uses_the_same_path_abstraction_open():
    doc, rep = fixture("linac.beam.json")
    net = Network.of(doc)
    order = [n.component for n in net.order("linac-line")]
    assert order == ["GUN01", "BUN01", "ACC01", "QUAL01", "BPML01", "ACC02", "DIPL01", "SCRL01", "DMPL01"]
    assert [n.component for n in net.sources()] == ["GUN01"]
    assert [n.component for n in net.destinations()] == ["DMPL01"]
    assert not net.walk("DMPL01", "downstream")
    assert {"TOPOLOGY", "LATTICE"} <= set(rep.levels) and "OPTICS" not in rep.levels


def test_branching_is_explicit_and_s_is_only_a_coordinate():
    doc, _ = fixture("transfer.beam.json")
    net = Network.of(doc)
    down = {n.component: k for n, _d, k in net.walk("SEPT1", "downstream", 1)}
    assert down == {"L1_Q1": "branch", "L2_Q1": "branch"}
    # each branch's s starts from 0 again: s does not order the network
    assert net.positions("line1")["L1_Q1"]["s"] == 0.0 == net.positions("main")["A_Q1"]["s"]
    reach = {n.component for n, _d, _k in net.walk("INJ_GUN", "downstream")}
    assert {"DUMP1", "EXP1"} <= reach
    assert {n.component for n, _d, _k in net.walk("EXP1", "upstream")} >= {"SEPT1", "A_Q1", "INJ_GUN"}
    assert sorted(n.component for n in net.destinations()) == ["DUMP1", "EXP1"]


def test_a_laser_line_uses_the_same_topology_model():
    doc, rep = fixture("laser.beam.json")
    net = Network.of(doc)
    assert [n.component for n, _d, k in net.walk("BSP01", "downstream", 1)] == ["IP01", "CAM01"]
    res = resolve(doc)
    assert "photon_transport" in res["MIR01"].capabilities and res["IP01"].virtual
    assert doc.beams[0].kind == "photon" and doc.beams[0].charge is None
    assert "PHYSICAL" in rep.levels       # the iris restricts the beam


def test_shared_components_carry_one_placement_per_path_and_beam():
    doc, rep = fixture("collider_ir.beam.json")
    net = Network.of(doc)
    assert sorted(net.paths_of("IP1")) == ["electron-ring", "positron-ring"]
    assert rep.summary["shared_components"] == ["IP1", "QD0L", "QD0R"]
    pos_next = [n.component for n, _d, k in net.walk(net.by_path["positron-ring"][2], "downstream", 1)]
    ele_next = [n.component for n, _d, k in net.walk(net.by_path["electron-ring"][2], "downstream", 1)]
    assert pos_next == ["QD0R"] and ele_next == ["QD0L"]      # the same IP, passed both ways
    assert len(doc.beams) == 2 and {b.charge for b in doc.beams} == {1, -1}


# =========================================================================== components

def test_definitions_are_separate_from_instances():
    doc, _ = fixture("ring.beam.json")
    res = resolve(doc)
    quads = [r for r in res.values() if r.component.definition == "QUA1"]
    assert len(quads) == 5 and all(r.length == 0.3 and r.type == "quadrupole" for r in quads)
    assert all(any(b.profile.radius == 0.025 for b in r.boundaries) for r in quads)


def test_a_component_may_have_many_capabilities_and_diagnostics_expose_observables():
    doc, _ = fixture("linac.beam.json")
    res = resolve(doc)
    scr = res["SCRL01"]
    assert {"diagnostic", "beam_profile_measurement", "interceptive", "material_interaction",
            "retractable"} <= set(scr.capabilities)
    assert scr.component.measurement_model.type == "image"
    assert "beam.profile.x" in scr.component.observes
    assert "non_interceptive" in res["BPML01"].capabilities       # not every diagnostic intercepts
    assert scr.material.material == "YAG:Ce"


def test_vacuum_components_belong_to_the_beam_model_with_states_and_apertures():
    doc, _ = fixture("ring.beam.json")
    res = resolve(doc)
    v = res["VLVA101"]
    assert v.family == "vacuum" and {"vacuum_boundary", "vacuum_isolation", "aperture_limiting", "movable",
                                     "interlocked"} <= set(v.capabilities)
    assert [s.name for s in v.states.states] == ["OPEN", "CLOSED", "MOVING", "FAULT"]
    assert v.states.default == "OPEN"
    k = res["KCKA101"]
    assert k.states.default == "ARMED" and [s.name for s in k.states.states][:2] == ["OFF", "READY"]


def test_mechanical_supports_carry_several_components_and_define_their_fiducials():
    doc, _ = fixture("ring.beam.json")
    assert set(Q.moves_with(doc, "GIRDER_01")) >= {"QUAA101", "SXTA101", "BPSA101"}
    f = Q.fiducials_of(doc, "QUAA101")
    assert f["via_supports"]["GIRDER_01"] == ["FID_G01_A", "FID_G01_B"]
    assert Q.support_chain(doc, "QUAA101") == ["GIRDER_01"]
    al = next(c for c in doc.components if c.id == "QUAA101").geometry.alignment
    assert al.offset.dx == 0.0005 and al.surveyed.z == 0.0002


def test_native_information_and_value_provenance_survive():
    doc, _ = fixture("ring.beam.json")
    design = next(d for d in doc.datasets if d.id == "design-2026")
    v = design.values["QUAA101"]
    assert v.native.format == "madx" and v.native.type == "QUADRUPOLE" and v.native.parameters["K1"] == 4.30926
    assert v.provenance["k1"].file == "strengths.str" and v.provenance["k1"].symbol == "qk1"
    again, rep = load(doc.to_json())
    assert rep.ok and again.to_json() == doc.to_json()            # round trip is exact


def test_several_datasets_and_fields_along_a_path_coexist():
    doc, _ = fixture("ring.beam.json")
    kinds = {d.id: d.kind for d in doc.datasets}
    assert kinds == {"design-2026": "design", "measured-2026-05": "measured", "vacuum-2026-06-01": "snapshot"}
    pressure = next(d for d in doc.datasets if d.id == "vacuum-2026-06-01").fields[0]
    assert pressure.quantity == "vacuum.pressure" and pressure.samples[2] == [16.0, 7.8e-9]
    with pytest.raises(Exception):
        load({**doc.to_json(), "datasets": [{"id": "x", "fields": [{"quantity": "q.t", "path": "accumulator-ring",
                                                                    "samples": [[2, 1], [1, 1]]}]}]})[0].fields


# =========================================================================== apertures

def test_the_limiting_aperture_is_found_whatever_produces_it():
    doc, _ = fixture("aperture.beam.json")
    whole = Q.limiting_aperture(doc, "line", "Q1", "Q2", dataset="design")
    assert whole["limit_y"]["component"] == "COL1" and whole["limit_y"]["value"] == 0.006
    assert whole["limit_y"]["family"] == "interception"
    assert whole["limit_x"]["component"] == "VLV1" and whole["limit_x"]["value"] == 0.018    # a valve, not a magnet
    upto_valve = Q.limiting_aperture(doc, "line", "Q1", "VLV1", dataset="design")
    assert upto_valve["limit_y"]["component"] == "VLV1"
    # the model aperture along the path counts where s places it (between CH1 and BL1)
    assert any(c["boundary"] == "model-aperture" for c in whole["considered"])
    # a scraper limits only when it is IN; a closed valve's open bore no longer applies
    assert not any(c["component"] == "SCP1" for c in whole["considered"])
    scraped = Q.limiting_aperture(doc, "line", "Q1", "Q2", dataset="design", states={"SCP1": "IN"})
    assert scraped["limit_x"]["component"] == "SCP1" and scraped["limit_x"]["value"] == 0.003


def test_aperture_shapes_reduce_to_one_measure():
    from app.beam_model_core.schema import Profile
    assert Q.half_apertures(Profile(shape="ellipse", semi_axis_x=0.04, semi_axis_y=0.02)) == \
        {"x": 0.04, "y": 0.02, "radius": 0.02}
    off = Q.half_apertures(Profile(shape="circle", radius=0.02, offset_x=0.005))
    assert abs(off["x"] - 0.015) < 1e-9 and abs(off["radius"] - 0.015) < 2e-4
    poly = Q.half_apertures(Profile(shape="polygon", points=[[0.01, 0.01], [-0.02, 0.01], [-0.02, -0.01],
                                                             [0.01, -0.01]]))
    assert abs(poly["x"] - 0.01) < 1e-9 and abs(poly["y"] - 0.01) < 1e-9
    with pytest.raises(Exception):
        Profile(shape="circle")


# =========================================================================== versions and validation

def test_v1_documents_upgrade_without_loss():
    v1 = json.loads((FX / "dafne_accumulator.json").read_text())
    v2 = upgrade(v1)
    doc, rep = load(v2)
    assert rep.ok and v2["schema_version"] == SCHEMA_VERSION
    assert len(doc.components) == len(v1["elements"])
    assert {c.type for c in doc.components} >= {"beam_dump", "septum", "bpm"}
    assert doc.connections[0].kind == "branch" and doc.connections[0].from_.component == "SEPA102"
    q = next(c for c in doc.components if c.id == "QUAA101")
    assert "particle_transport" in resolve(doc)["QUAA101"].capabilities and q.native.format == "madx"
    laser1 = json.loads((FX / "laser_transport.json").read_text())
    ldoc, lrep = load(laser1)
    assert lrep.ok and any("photon_transport" in r.capabilities for r in resolve(ldoc).values())


def test_models_with_incomplete_information_stay_valid():
    doc, rep = load({"schema_version": SCHEMA_VERSION, "model": {"id": "bare"},
                     "components": [{"id": "Q1", "type": "quadrupole"}, {"id": "M1", "type": "marker"}],
                     "paths": [{"id": "p", "placements": ["Q1", "M1"]}]})
    assert rep.ok and rep.levels == ["TOPOLOGY"]
    assert rep.gaps["LATTICE"] == ["Q1"]
    odd, rep2 = load({"schema_version": SCHEMA_VERSION, "model": {"id": "odd"},
                      "components": [{"id": "X1", "type": "plasma_lens", "capabilities": ["focusing"]}],
                      "paths": [{"id": "p", "placements": ["X1"]}]})
    assert rep2.ok and any("plasma_lens" in w for w in rep2.warnings)   # unknown types are kept, not refused


def test_references_are_checked():
    _doc, rep = load({"schema_version": SCHEMA_VERSION, "model": {"id": "bad"},
                      "components": [{"id": "Q1", "type": "quadrupole", "mounted_on": "G9", "observes": ["beam.zap"]}],
                      "paths": [{"id": "p", "placements": ["Q1", "Q2"]}],
                      "connections": [{"kind": "branch", "from": {"path": "p", "component": "Q1"}, "to": {"path": "nope"}}],
                      "external_bindings": [{"component": "Q1", "relation": "owned_by", "target": {"id": "x"}}]})
    text = " ".join(rep.errors)
    for needle in ("unknown component G9", "beam.zap", "unknown component Q2", "unknown path nope", "owned_by"):
        assert needle in text, needle


def test_the_json_schema_is_generated_from_the_object_model():
    s = json_schema()
    assert s["title"].endswith("(argus.beam-model/2)")
    assert {"components", "paths", "connections", "definitions", "datasets", "external_bindings"} <= set(s["properties"])


def test_the_vocabulary_covers_the_required_families():
    for t in ("dipole", "octupole", "wiggler", "crab_cavity", "wall_current_monitor", "faraday_cup",
              "stripping_foil", "beam_stopper", "gate_valve", "differential_pumping_section", "gas_jet",
              "waveplate", "optical_amplifier", "ion_source", "interaction_point", "girder", "fiducial"):
        assert t in V.TYPES, t
    assert V.is_virtual("marker") and V.is_virtual("interaction_point") and not V.is_virtual("quadrupole")


# =========================================================================== asset matching

def test_exact_name_alias_convention_and_normalised_names():
    p, _ = sync()
    assert p["QUAA102"]["asset"]["name"] == "QUAA102" and "exact_name" in p["QUAA102"]["evidence"]
    assert p["QUAA101"]["asset"]["name"] == "MAG-ACC-QF01" and p["QUAA101"]["confidence"] >= 0.9
    assert p["VLVA101"]["asset"]["name"] == "VV-ACC-01" and "exact_alias_match" in p["VLVA101"]["evidence"]
    assert p["QUAA104"]["asset"]["name"] == "MAG-ACC-QF04" and "naming_convention" in p["QUAA104"]["evidence"]
    assert p["QUAA105"]["asset"]["name"] == "quaa-0105" and "normalized_name" in p["QUAA105"]["evidence"]


def test_different_names_match_on_type_beamline_and_position_but_never_auto():
    p, _ = sync()
    q = p["QUAA103"]
    assert q["status"] == "proposed" and q["asset"]["name"] == "ACC-QF-03"
    assert {"type_match", "beamline_match", "position_match"} <= set(q["evidence"]) and q["delta_s"] < 0.01
    assert not q["auto_acceptable"]        # no identity evidence: a person decides


def test_geometry_alone_proposes_for_review():
    p, _ = sync()
    assert p["BLWA101"]["asset"]["name"] == "BELLOWS-A1" and "geometry_match" in p["BLWA101"]["evidence"]
    assert not p["BLWA101"]["auto_acceptable"]


def test_the_same_name_on_another_beamline_does_not_win():
    p, _ = sync()
    assert p["QUAA101"]["asset"]["id"] == "a-qf01"
    doc, _ = fixture("ring.beam.json")
    e = next(x for x in M.expectations(doc, "design-2026") if x.id == "QUAA101")
    main = next(a for a in assets()["assets"] if a["id"] == "a-main-quaa101")
    conf, ev = M.score(e, main, M.Config(), M.context_names(doc))
    assert "exact_name" in [x["kind"] for x in ev] and "other_beamline" in [x["kind"] for x in ev]
    assert conf < 0.5


def test_multiple_candidates_are_ambiguous_and_none_is_unmatched():
    p, _ = sync()
    assert p["BPSA103"]["status"] == "ambiguous" and p["BPSA103"]["asset"] is None
    assert {c["asset"]["name"] for c in p["BPSA103"]["candidates"][:2]} == {"BPM-BPSA103-A", "BPM-BPSA103-B"}
    assert p["SEPA101"]["status"] == "unmatched"


def test_existing_confirmed_bindings_are_kept_and_differences_reported():
    p, _ = sync()
    assert p["CHHA101"]["status"] == "confirmed" and p["CHHA101"]["diff"] == "unchanged"
    k = p["KCKA101"]
    # the unit was replaced: the binding is not silently moved; the replacement is shown for review
    assert k["status"] == "confirmed" and k["diff"] == "missing_asset" and k["asset"]["id"] == "a-kck-old"
    assert k["candidates"][0]["asset"]["name"] == "KCK-NEW"


def test_physics_without_asset_and_asset_without_physics():
    p, r = sync()
    assert p["MARK_INJ"]["expects_asset"] is False and p["MARK_INJ"]["status"] == "unmatched"
    assert "ION-PUMP-07" in [a["name"] for a in r["unmodelled_assets"]]
    assert r["summary"]["virtual_components"] == 1


def test_a_diagnostic_binds_to_its_primary_asset_not_its_electronics():
    p, r = sync()
    assert p["BPSA101"]["asset"]["name"] == "BPM-BPSA101"
    assert all(c["asset"]["name"] != "LIBERA-BPSA101" for c in p["BPSA101"]["candidates"])
    assert "LIBERA-BPSA101" not in [a["name"] for a in r["unmodelled_assets"]]


def test_low_confidence_never_becomes_authoritative_and_auto_needs_identity():
    _p, r = sync()
    for x in r["proposals"]:
        if x["auto_acceptable"]:
            assert x["confidence"] >= 0.9 and set(x["evidence"]) & M.IDENTITY and "type_match" in x["evidence"]
        if x["status"] != "confirmed":
            assert x["authority"] in (None, "suggestion")
    # position alone, however close, is never auto-accepted
    loose = [{"id": "a-x", "name": "THING-7", "type": "Magnet Assembly",
              "attributes": {"beamline": "DAFNE Accumulator", "s": 1.5833}}]
    p, _ = sync(existing=[], assets_=loose)
    assert not p["QUAA101"]["auto_acceptable"]


def test_rejected_pairs_are_not_proposed_again_and_confirmed_survive_resync():
    fx = assets()
    rejected = [*fx["existing"], {"component": "QUAA102", "asset": "a-quaa102", "status": "rejected"}]
    p, r = sync(existing=rejected)
    assert p["QUAA102"]["status"] == "unmatched" and r["summary"]["rejected"] == 1
    confirmed = [*fx["existing"], {"component": "QUAA101", "asset": "a-qf01", "status": "confirmed",
                                   "authority": "human_confirmed", "snapshot": {"name": "MAG-ACC-QF01"}}]
    renamed = copy.deepcopy(fx["assets"])
    next(a for a in renamed if a["id"] == "a-qf01")["name"] = "MAG-ACC-QF01-NEW"
    p2, _ = sync(existing=confirmed, assets_=renamed)
    assert p2["QUAA101"]["status"] == "confirmed" and p2["QUAA101"]["asset"]["id"] == "a-qf01"
    assert p2["QUAA101"]["diff"] == "changed" and "renamed" in p2["QUAA101"]["notes"][0]


def test_incremental_sync_reports_new_changed_and_stale():
    fx = assets()
    previous = [*fx["existing"], {"component": "QUAA103", "asset": "a-qf01", "status": "proposed"},
                {"component": "GONE01", "asset": "a-ip07", "status": "confirmed"}]
    p, r = sync(existing=previous)
    assert p["QUAA103"]["diff"] == "changed_candidate"
    assert p["DHRA101"]["diff"] == "new_match"
    assert r["stale_bindings"][0]["component"] == "GONE01"


def test_summary_and_filters():
    _p, r = sync()
    s = r["summary"]
    assert s["model_components"] == s["confirmed"] + s["proposed"] + s["ambiguous"] + s["unmatched"]
    assert s["physical_candidates"] == len([a for a in assets()["assets"] if not a.get("retired")])
    mags = M.filter_proposals(r["proposals"], "magnets")
    assert mags and all(x["family"] == "magnet" for x in mags)
    assert {x["component"] for x in M.filter_proposals(r["proposals"], "vacuum")} >= {"VLVA101", "BLWA101"}
    assert all(x["status"] == "ambiguous" for x in M.filter_proposals(r["proposals"], "ambiguous"))
