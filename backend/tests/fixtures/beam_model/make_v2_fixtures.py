"""Writes the argus.beam-model/2 test models (docs/beam-model-format.md §12) and the mock Knowledge Hub assets.

    python tests/fixtures/beam_model/make_v2_fixtures.py

A  ring.beam.json            DAΦNE accumulator-like ring: magnets, kickers, septa, BPMs, vacuum chambers,
                             bellows, valves, apertures, a girder with fiducials, a marker; closed path with
                             an extraction branch. ring_assets.json: mock Knowledge Hub assets with matching
                             and non-matching names.
B  linac.beam.json           source → buncher → RF → quadrupole → BPM → RF → dipole → screen → dump
C  transfer.beam.json        injector → A → B → septum, branching to line 1 → dump and line 2 → experiment
D  laser.beam.json           laser → mirror → lens → iris → beam splitter → IP, with a camera branch
E  aperture.beam.json        magnet bore, chamber, bellows, partially restrictive valve, collimator, scraper
F  collider_ir.beam.json     two counter-rotating beams sharing an interaction region (shared placements)
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from app.beam_model_core.upgrade import upgrade  # noqa: E402

V2 = "argus.beam-model/2"


def write(name: str, doc) -> None:
    (HERE / name).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- A: ring

def ring() -> tuple[dict, list]:
    v1 = json.loads((HERE / "dafne_accumulator.json").read_text())
    doc = upgrade(v1)
    doc["model"] = {**doc["model"], "id": "dafne-accumulator-v2", "version": "2026.2"}
    doc["facility"] = {"id": "dafne", "name": "DAΦNE", "namespace": "dafne/accumulator", "site": "LNF"}
    doc["provenance"] = {"created_by": "make_v2_fixtures.py", "sources": [{"file": "dafne_accumulator.madx",
                                                                          "format": "madx"}]}
    comps = {c["id"]: c for c in doc["components"]}
    design = next(d for d in doc["datasets"] if d["id"] == "design-2026")
    vals = design["values"]
    # Definitions: families the simulator reuses.
    doc["definitions"] = [
        {"id": "QUA1", "type": "quadrupole", "parameters": {"length": 0.3},
         "boundaries": [{"profile": {"shape": "circle", "radius": 0.025}, "note": "magnet bore"}],
         "native": {"format": "madx", "type": "QUADRUPOLE", "name": "QUA1", "parameters": {"L": 0.3}}},
        {"id": "DHR", "type": "dipole", "parameters": {"length": 1.0},
         "boundaries": [{"profile": {"shape": "racetrack", "half_width_x": 0.04, "half_height_y": 0.015,
                                     "corner_radius": 0.01}, "note": "dipole chamber"}]},
        {"id": "SXT", "type": "sextupole", "parameters": {"length": 0.1},
         "boundaries": [{"profile": {"shape": "circle", "radius": 0.03}}]},
    ]
    for cid, c in comps.items():
        if c["type"] == "quadrupole" and cid.startswith("QUAA"):
            c["definition"] = "QUA1"
            c["family"] = "QF" if int(cid[-1]) % 2 else "QD"
        elif c["type"] == "dipole" and cid.startswith("DHRA"):
            c["definition"] = "DHR"
        elif c["type"] == "sextupole":
            c["definition"] = "SXT"
    vals["QUAA101"]["provenance"] = {"k1": {"source": "madx", "file": "strengths.str", "symbol": "qk1", "line": 12}}
    comps["KCKA101"]["states"] = {"states": [{"name": n, "meaning": m} for n, m in (
        ("OFF", {"acts": False}), ("READY", {"acts": False}), ("ARMED", {"acts": True}), ("FAULT", {"acts": None}))],
        "default": "ARMED"}
    comps["BPSA101"]["measurement_model"] = {"type": "centroid", "observables": ["beam.position.x", "beam.position.y"]}
    # Physical components the lattice lacks, placed in the gaps (no drifts are kept).
    ring_path = next(p for p in doc["paths"] if p["id"] == "accumulator-ring")
    order = list(ring_path["placements"])
    extra = [
        # (after, id, type, length, extra fields)
        ("SEPA101", "VLVA101", "gate_valve", 0.07, {
            "boundaries": [{"profile": {"shape": "circle", "radius": 0.032}, "when_state": "OPEN",
                            "note": "open bore"}],
            "aliases": ["VV-ACC-01"]}),
        ("QUAA101", "BLWA101", "bellows", 0.05, {"boundaries": [{"profile": {"shape": "circle", "radius": 0.03}}]}),
        ("QUAA102", "CHVA_A1", "vacuum_chamber", 0.10, {
            "boundaries": [{"profile": {"shape": "ellipse", "semi_axis_x": 0.04, "semi_axis_y": 0.02}}]}),
        ("BPSA103", "VLVA102", "gate_valve", 0.07, {
            "boundaries": [{"profile": {"shape": "circle", "radius": 0.032}, "when_state": "OPEN"}]}),
        ("CHVA102", "MARK_INJ", "marker", 0.0, {}),
    ]
    for after, cid, ctype, length, fields in extra:
        # Inserted after straight elements only: the position is extrapolated along the entry heading.
        end = vals[after]["s"] + (vals[after].get("physics", {}).get("length") or 0)
        s = round(end + 0.01, 4)
        g = vals[after].get("geometry") or {}
        yaw = g.get("yaw", 0.0)
        dx = s - vals[after]["s"]
        geo = {"x": round(g.get("x", 0) + dx * math.cos(yaw), 4), "y": round(g.get("y", 0) + dx * math.sin(yaw), 4),
               "yaw": yaw}
        doc["components"].append({"id": cid, "type": ctype, **({"geometry": {"length": length}} if length else {}),
                                  **fields})
        order.insert(order.index(after) + 1, cid)
        vals[cid] = {"s": s, "geometry": geo, **({"physics": {"length": length}} if length else {})}
    ring_path["placements"] = order
    # A girder carrying three components, with fiducials; and a vacuum chamber containing the BPM.
    doc["components"] += [
        {"id": "GIRDER_01", "type": "girder", "fiducials": ["FID_G01_A", "FID_G01_B"]},
        {"id": "FID_G01_A", "type": "fiducial", "mounted_on": "GIRDER_01"},
        {"id": "FID_G01_B", "type": "fiducial", "mounted_on": "GIRDER_01"},
    ]
    for cid in ("QUAA101", "SXTA101", "BPSA101"):
        comps[cid]["mounted_on"] = "GIRDER_01"
    comps["QUAA101"]["geometry"] = {"alignment": {"design": {"x": 1.5833, "y": 0.0, "z": 0.0},
                                                  "surveyed": {"x": 1.5838, "y": 0.0, "z": 0.0002},
                                                  "offset": {"dx": 0.0005, "dz": 0.0002}, "surveyed_at": "2026-04-02"}}
    comps["QUAA101"]["aliases"] = ["MAG-ACC-QF01"]
    # A second dataset: measured optics at the BPMs.
    doc["datasets"].append({"id": "measured-2026-05", "kind": "measured", "category": "optics",
                            "path": "accumulator-ring", "source": "LOCO", "generated_at": "2026-05-12",
                            "values": {b: {"optics": {"beta_x": round(vals[b]["optics"]["beta_x"] * 1.03, 3),
                                                      "beta_y": round(vals[b]["optics"]["beta_y"] * 0.98, 3)}}
                                       for b in ("BPSA101", "BPSA102", "BPSA103", "BPSA104", "BPSA105")}})
    # Pressure along the ring: a snapshot, not telemetry.
    doc["datasets"].append({"id": "vacuum-2026-06-01", "kind": "snapshot", "category": "vacuum",
                            "path": "accumulator-ring", "generated_at": "2026-06-01T08:00:00Z",
                            "fields": [{"quantity": "vacuum.pressure", "path": "accumulator-ring", "unit": "mbar",
                                        "samples": [[0.0, 2.1e-9], [8.0, 2.3e-9], [16.0, 7.8e-9], [24.0, 2.0e-9]]}]})
    # Assets as the hub (or a test's mock) knows them.
    bl = "DAFNE Accumulator"
    sval = lambda c: round(vals[c]["s"] + (vals[c].get("physics", {}).get("length") or 0) / 2, 4)  # noqa: E731
    assets = [
        {"id": "a-qf01", "name": "MAG-ACC-QF01", "type": "Magnet Assembly", "aliases": ["QUAA101"],
         "attributes": {"beamline": bl, "s": sval("QUAA101"), "component_type": "quadrupole"}},
        {"id": "a-quaa102", "name": "QUAA102", "type": "Magnet Assembly", "attributes": {"beamline": bl}},
        {"id": "a-qf03", "name": "ACC-QF-03", "type": "Magnet Assembly",
         "attributes": {"beamline": bl, "s": sval("QUAA103") + 0.004}},
        {"id": "a-qf04", "name": "MAG-ACC-QF04", "type": "Magnet Assembly", "attributes": {"beamline": bl}},
        {"id": "a-quaa105", "name": "quaa-0105", "type": "Magnet Assembly", "attributes": {"beamline": bl}},
        # The same name in another machine: must not win.
        {"id": "a-main-quaa101", "name": "QUAA101", "type": "Magnet Assembly",
         "attributes": {"beamline": "DAFNE Main Ring", "s": 52.1}},
        *({"id": f"a-{d.lower()}", "name": f"DIP-{d}", "type": "Magnet Assembly",
           "attributes": {"beamline": bl, "lattice_name": d}} for d in ("DHRA101", "DHRA102", "DHRA103", "DHRA104")),
        # BPMs: the pickup is the primary asset; its electronics are downstream hardware.
        *({"id": f"a-pu-{b.lower()}", "name": f"BPM-{b}", "type": "Instrument",
           "attributes": {"beamline": bl, "lattice_name": b, "component_type": "bpm"}}
          for b in ("BPSA101", "BPSA102", "BPSA104", "BPSA105")),
        *({"id": f"a-el-{b.lower()}", "name": f"LIBERA-{b}", "type": "Digitizer",
           "attributes": {"beamline": bl, "lattice_name": b}} for b in ("BPSA101", "BPSA102")),
        # Two candidates for one BPM: ambiguous.
        {"id": "a-pu-bpsa103-a", "name": "BPM-BPSA103-A", "type": "Instrument",
         "attributes": {"beamline": bl, "lattice_name": "BPSA103"}},
        {"id": "a-pu-bpsa103-b", "name": "BPM-BPSA103-B", "type": "Instrument",
         "attributes": {"beamline": bl, "lattice_name": "BPSA103"}},
        # A corrector already bound by a person, and a kicker whose bound unit was replaced.
        {"id": "a-cor-h-01", "name": "COR-H-01", "type": "Magnet Assembly", "attributes": {"beamline": bl}},
        {"id": "a-kck-old", "name": "KCK-OLD", "type": "Magnet Assembly", "retired": True,
         "attributes": {"beamline": bl}},
        {"id": "a-kck-new", "name": "KCK-NEW", "type": "Magnet Assembly",
         "attributes": {"beamline": bl, "lattice_name": "KCKA101"}},
        # Vacuum: a valve by alias, a bellows by geometry only, a pump nothing in the model is.
        {"id": "a-vv01", "name": "VV-ACC-01", "type": "Vacuum Valve", "attributes": {"beamline": bl}},
        {"id": "a-bellows-a1", "name": "BELLOWS-A1", "type": "Vacuum Component",
         "attributes": {"beamline": bl, "x": vals["BLWA101"]["geometry"]["x"] + 0.02,
                        "y": vals["BLWA101"]["geometry"]["y"]}},
        {"id": "a-ip07", "name": "ION-PUMP-07", "type": "Ion Pump", "attributes": {"beamline": bl}},
        {"id": "a-gir01", "name": "GIR-ACC-01", "type": "Mechanical Support",
         "attributes": {"beamline": bl, "lattice_name": "GIRDER_01"}},
        {"id": "a-ps-qf", "name": "PS-QF", "type": "Power Supply", "attributes": {"beamline": bl}},
    ]
    existing = [
        {"component": "CHHA101", "asset": "a-cor-h-01", "relation": "implemented_by", "status": "confirmed",
         "authority": "human_confirmed", "snapshot": {"name": "COR-H-01"}},
        {"component": "KCKA101", "asset": "a-kck-old", "relation": "implemented_by", "status": "confirmed",
         "authority": "human_confirmed", "snapshot": {"name": "KCK-OLD"}},
    ]
    return doc, {"assets": assets, "existing": existing, "naming_rules": [
        {"component": r"^QUAA1(?P<n>\d{2})$", "asset": "MAG-ACC-QF{n:02d}"}]}


# --------------------------------------------------------------------------- B: linac

def linac() -> dict:
    seq = [("GUN01", "electron_source", 0.0, 0.2), ("BUN01", "buncher", 0.4, 0.3), ("ACC01", "accelerating_structure", 1.0, 3.0),
           ("QUAL01", "quadrupole", 4.3, 0.1), ("BPML01", "bpm", 4.6, 0.05), ("ACC02", "accelerating_structure", 5.0, 3.0),
           ("DIPL01", "dipole", 8.5, 0.5), ("SCRL01", "screen", 9.3, 0.02), ("DMPL01", "beam_dump", 10.0, 0.5)]
    physics = {"BUN01": {"voltage": 0.5, "frequency": 2856e6}, "ACC01": {"voltage": 60.0, "frequency": 2856e6},
               "ACC02": {"voltage": 60.0, "frequency": 2856e6}, "QUAL01": {"k1": 8.2}, "DIPL01": {"angle": 0.0}}
    return {"schema_version": V2, "model": {"id": "test-linac", "name": "Test electron linac", "version": "1"},
            "facility": {"id": "lab", "name": "Test lab"},
            "systems": [{"id": "linac", "name": "Linac", "kind": "Linac", "beams": ["e-"]}],
            "beams": [{"id": "e-", "kind": "particle", "species": "electron", "charge": -1, "reference_energy": 0.12,
                       "systems": ["linac"]}],
            "paths": [{"id": "linac-line", "system": "linac", "beams": ["e-"], "topology": "open",
                       "placements": [c for c, *_ in seq]}],
            "components": [
                *({"id": c, "type": t, "geometry": {"length": L}} for c, t, _s, L in seq if c not in ("BPML01", "SCRL01")),
                {"id": "BPML01", "type": "bpm", "observes": ["beam.position.x", "beam.position.y", "beam.charge"],
                 "measurement_model": {"type": "centroid", "observables": ["beam.position.x", "beam.position.y"]}},
                {"id": "SCRL01", "type": "screen", "observes": ["beam.profile.x", "beam.profile.y", "beam.size.x"],
                 "material": {"material": "YAG:Ce", "thickness": 1e-4, "density": 4.57},
                 "measurement_model": {"type": "image", "observables": ["beam.profile.x", "beam.profile.y"]}},
            ],
            "datasets": [{"id": "design", "kind": "design", "category": "lattice", "path": "linac-line",
                          "values": {c: {"s": s, "physics": {"length": L, **physics.get(c, {})}} for c, _t, s, L in seq}}]}


# --------------------------------------------------------------------------- C: branched transfer line

def transfer() -> dict:
    comps = [("INJ_GUN", "electron_source"), ("INJ_Q1", "quadrupole"), ("A_Q1", "quadrupole"), ("B_BPM1", "bpm"),
             ("SEPT1", "septum"), ("L1_Q1", "quadrupole"), ("L1_BPM1", "bpm"), ("DUMP1", "beam_dump"),
             ("L2_Q1", "quadrupole"), ("L2_SCR1", "screen"), ("EXP1", "experimental_target")]
    return {"schema_version": V2, "model": {"id": "test-transfer", "name": "Branched transfer line"},
            "systems": [{"id": "tl", "kind": "Transfer line", "beams": ["e-"]}],
            "beams": [{"id": "e-", "species": "electron", "charge": -1, "systems": ["tl"]}],
            "paths": [{"id": "injector", "system": "tl", "placements": ["INJ_GUN", "INJ_Q1"]},
                      {"id": "main", "system": "tl", "placements": ["A_Q1", "B_BPM1", "SEPT1"]},
                      {"id": "line1", "system": "tl", "placements": ["L1_Q1", "L1_BPM1", "DUMP1"]},
                      {"id": "line2", "system": "tl", "placements": ["L2_Q1", "L2_SCR1", "EXP1"]}],
            "connections": [{"kind": "continue", "from": {"path": "injector"}, "to": {"path": "main"}},
                            {"kind": "branch", "from": {"path": "main", "component": "SEPT1"}, "to": {"path": "line1"}},
                            {"kind": "branch", "from": {"path": "main", "component": "SEPT1"}, "to": {"path": "line2"}}],
            "components": [{"id": c, "type": t} for c, t in comps],
            # Each path has its own s, from 0: s is a coordinate, never the topology.
            "datasets": [{"id": f"design-{p}", "path": p, "values": {c: {"s": float(i)} for i, c in enumerate(cs)}}
                         for p, cs in (("main", ["A_Q1", "B_BPM1", "SEPT1"]), ("line1", ["L1_Q1", "L1_BPM1", "DUMP1"]),
                                       ("line2", ["L2_Q1", "L2_SCR1", "EXP1"]))]}


# --------------------------------------------------------------------------- D: laser transport

def laser() -> dict:
    return {"schema_version": V2, "model": {"id": "test-laser", "name": "Laser transport", "simulator": "zemax"},
            "systems": [{"id": "laser", "kind": "Laser transport", "beams": ["ti-sa"]}],
            "beams": [{"id": "ti-sa", "kind": "photon", "species": "photon", "wavelength": 800.0,
                       "parameters": {"pulse_duration_fs": 30, "repetition_rate_hz": 10}, "systems": ["laser"]}],
            "paths": [{"id": "laser-main", "system": "laser", "medium": "photon",
                       "placements": ["LSR01", "MIR01", "LNS01", "IRS01", "BSP01", "IP01"]},
                      {"id": "diagnostic-leg", "system": "laser", "medium": "photon", "placements": ["CAM01"]}],
            "connections": [{"kind": "branch", "from": {"path": "laser-main", "component": "BSP01"},
                             "to": {"path": "diagnostic-leg"}}],
            "components": [
                {"id": "LSR01", "type": "laser_source"},
                {"id": "MIR01", "type": "mirror", "parameters": {"incidence_angle": 0.785}},
                {"id": "LNS01", "type": "lens", "parameters": {"focal_length": 2.0}},
                {"id": "IRS01", "type": "iris", "boundaries": [{"profile": {"shape": "circle", "radius": 0.004}}],
                 "states": {"states": [{"name": "OPEN"}, {"name": "CLOSED", "meaning": {"beam_passes": False}}],
                            "default": "OPEN"}},
                {"id": "BSP01", "type": "beam_splitter", "parameters": {"split_ratio": 0.99}},
                {"id": "IP01", "type": "interaction_point"},
                {"id": "CAM01", "type": "camera", "observes": ["optical.profile", "optical.power"],
                 "measurement_model": {"type": "image", "observables": ["optical.profile"]},
                 "native": {"format": "zemax", "type": "DETECTOR", "name": "CAM01"}},
            ],
            "datasets": [{"id": "layout", "kind": "design", "category": "survey", "path": "laser-main",
                          "values": {c: {"s": s, "geometry": {"x": x, "y": y, "z": 1.2}} for c, s, x, y in (
                              ("LSR01", 0.0, 0.0, 0.0), ("MIR01", 1.0, 1.0, 0.0), ("LNS01", 2.0, 1.0, 1.0),
                              ("IRS01", 2.5, 1.0, 1.5), ("BSP01", 3.0, 1.0, 2.0), ("IP01", 4.0, 1.0, 3.0))}}]}


# --------------------------------------------------------------------------- E: physical apertures

def aperture() -> dict:
    comps = [
        {"id": "Q1", "type": "quadrupole", "geometry": {"length": 0.3},
         "boundaries": [{"id": "Q1-bore", "profile": {"shape": "circle", "radius": 0.025}}]},
        {"id": "CH1", "type": "vacuum_chamber", "geometry": {"length": 1.0},
         "boundaries": [{"id": "CH1-section", "profile": {"shape": "ellipse", "semi_axis_x": 0.035,
                                                           "semi_axis_y": 0.02}}]},
        {"id": "BL1", "type": "bellows", "geometry": {"length": 0.1},
         "boundaries": [{"id": "BL1-bore", "profile": {"shape": "circle", "radius": 0.03}}]},
        {"id": "VLV1", "type": "gate_valve", "geometry": {"length": 0.07},
         "boundaries": [{"id": "VLV1-open", "when_state": "OPEN", "profile": {"shape": "circle", "radius": 0.018}}]},
        {"id": "COL1", "type": "collimator", "geometry": {"length": 0.2},
         "material": {"material": "tungsten", "density": 19.3, "radiation_length": 0.0035},
         "boundaries": [{"id": "COL1-jaws", "profile": {"shape": "rectangle", "half_width_x": 0.04,
                                                         "half_height_y": 0.006}}]},
        {"id": "SCP1", "type": "scraper", "geometry": {"length": 0.05},
         "boundaries": [{"id": "SCP1-in", "when_state": "IN",
                         "profile": {"shape": "rectangle", "half_width_x": 0.003, "half_height_y": 0.05,
                                     "offset_x": 0.0}}]},
        {"id": "Q2", "type": "quadrupole", "geometry": {"length": 0.3}},
    ]
    order = ["Q1", "CH1", "BL1", "VLV1", "COL1", "SCP1", "Q2"]
    s, vals = 0.0, {}
    for c in comps:
        vals[c["id"]] = {"s": round(s, 4)}
        s += c["geometry"]["length"] + 0.05
    return {"schema_version": V2, "model": {"id": "test-aperture", "name": "Aperture example"},
            "systems": [{"id": "line", "kind": "Transfer line"}],
            "paths": [{"id": "line", "system": "line", "placements": order}],
            "components": comps,
            # An aperture along the path that no single component produces (a model aperture).
            "boundaries": [{"id": "model-aperture", "path": "line", "s_start": 0.4, "s_end": 0.6, "kind": "model",
                            "profile": {"shape": "ellipse", "semi_axis_x": 0.03, "semi_axis_y": 0.019}}],
            "datasets": [{"id": "design", "path": "line", "values": vals}]}


# --------------------------------------------------------------------------- F: collider interaction region

def collider() -> dict:
    ir = ["QD0L", "IP1", "QD0R"]
    return {"schema_version": V2, "model": {"id": "test-collider-ir", "name": "Collider interaction region"},
            "systems": [{"id": "collider", "kind": "Collider", "beams": ["e+", "e-"]}],
            "beams": [{"id": "e+", "species": "positron", "charge": 1, "reference_energy": 0.51, "systems": ["collider"]},
                      {"id": "e-", "species": "electron", "charge": -1, "reference_energy": 0.51, "systems": ["collider"]}],
            "paths": [{"id": "positron-ring", "system": "collider", "beams": ["e+"], "topology": "closed",
                       "placements": ["ARC_P1", *ir, "ARC_P2"]},
                      {"id": "electron-ring", "system": "collider", "beams": ["e-"], "topology": "closed",
                       # The same IR, passed the other way.
                       "placements": ["ARC_E1", *({"component": c, "reversed": True} for c in reversed(ir)), "ARC_E2"]}],
            "components": [{"id": "QD0L", "type": "quadrupole"}, {"id": "QD0R", "type": "quadrupole"},
                           {"id": "IP1", "type": "interaction_point"},
                           *({"id": a, "type": "dipole"} for a in ("ARC_P1", "ARC_P2", "ARC_E1", "ARC_E2"))]}


if __name__ == "__main__":
    doc, assets = ring()
    write("ring.beam.json", doc)
    write("ring_assets.json", assets)
    write("linac.beam.json", linac())
    write("transfer.beam.json", transfer())
    write("laser.beam.json", laser())
    write("aperture.beam.json", aperture())
    write("collider_ir.beam.json", collider())
    print("written")
