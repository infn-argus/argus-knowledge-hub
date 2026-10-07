"""Xsuite: a line saved as JSON (`line.to_json(...)` / `line.to_dict()`).

Read: `element_names` in order and `elements` (a dict by name, or a list in the same order), each with its
`__class__`; `particle_ref` (mass0 and p0c in eV, q0) for the beam. Lengths give `s`; thick and thin magnets,
cavities and solenoids map to their kinds; markers are kept only when asked. Xsuite's aperture elements
(`LimitEllipse`, `LimitRect`, `LimitRectEllipse`, `LimitRacetrack`, `LimitPolygon`) become boundaries along
the path at their `s`, so the limiting-aperture query sees them. Everything else of an element is kept in
`native`.
"""
from __future__ import annotations

import json

from app.beam_converters import ConversionError, Converter, Options, register
from app.beam_converters.common import Placed, build, hint

KINDS = {"Drift": "drift", "Quadrupole": "quadrupole", "Bend": "dipole", "RBend": "dipole", "Sextupole": "sextupole",
         "Octupole": "octupole", "Cavity": "rf_cavity", "Solenoid": "solenoid", "Marker": "marker",
         "UniformSolenoid": "solenoid", "CrabCavity": "crab_cavity", "Wiggler": "wiggler",
         "BeamPositionMonitor": "bpm", "Multipole": "multipole", "SimpleThinBend": "dipole",
         "SimpleThinQuadrupole": "quadrupole", "Exciter": "kicker"}
APERTURES = {"LimitEllipse", "LimitRect", "LimitRectEllipse", "LimitRacetrack", "LimitPolygon"}
SKIP = {"DipoleEdge", "SRotation", "XYShift", "YRotation", "ZetaShift", "Replica", "ParticlesMonitor",
        "LastTurnsMonitor", "BeamElement"}
MASSES = {"electron": 0.51099895e6, "proton": 938.27208816e6, "muon": 105.6583755e6}


def _profile(cls: str, e: dict):
    if cls == "LimitEllipse" and e.get("a") and e.get("b"):
        return {"shape": "ellipse", "semi_axis_x": float(e["a"]), "semi_axis_y": float(e["b"])}
    if cls in ("LimitRect", "LimitRectEllipse"):
        mx, Mx, my, My = (float(e.get(k, 0) or 0) for k in ("min_x", "max_x", "min_y", "max_y"))
        if Mx > mx and My > my:
            return {"shape": "rectangle", "half_width_x": (Mx - mx) / 2, "half_height_y": (My - my) / 2,
                    **({"offset_x": (Mx + mx) / 2} if Mx + mx else {}), **({"offset_y": (My + my) / 2} if My + my else {})}
    if cls == "LimitRacetrack":
        mx, Mx, my, My = (float(e.get(k, 0) or 0) for k in ("min_x", "max_x", "min_y", "max_y"))
        if Mx > mx and My > my:
            return {"shape": "racetrack", "half_width_x": (Mx - mx) / 2, "half_height_y": (My - my) / 2,
                    "corner_radius": min(float(e.get("a", 0) or 0), (Mx - mx) / 2, (My - my) / 2)}
    if cls == "LimitPolygon" and e.get("x_vertices") and e.get("y_vertices"):
        return {"shape": "polygon", "points": [[float(x), float(y)] for x, y in zip(e["x_vertices"], e["y_vertices"])]}
    return None


def convert_xsuite(text: str, filename: str, options: Options) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConversionError(f"{filename}: not JSON ({e.msg})") from e
    line = data.get("line", data) if isinstance(data, dict) else None
    if not isinstance(line, dict) or "element_names" not in line or "elements" not in line:
        raise ConversionError(f"{filename}: an Xsuite line needs element_names and elements")
    names = list(line["element_names"])
    raw = line["elements"]
    elements = raw if isinstance(raw, dict) else dict(zip(names, raw))
    placed, boundaries, pos = [], [], 0.0
    for name in names:
        e = elements.get(name)
        if e is None:
            raise ConversionError(f"{filename}: element {name} is named but not defined")
        cls = e.get("__class__", "")
        length = float(e.get("length", 0.0) or 0.0)
        if cls in APERTURES:
            prof = _profile(cls, e)
            if prof:
                boundaries.append({"id": f"{name}", "s_start": round(pos, 9), "s_end": round(pos, 9),
                                   "profile": prof, "kind": "physical", "note": f"Xsuite {cls}"})
            continue
        if cls in SKIP:
            continue
        kind = KINDS.get(cls, "generic")
        physics: dict = {}
        if kind == "multipole":
            knl, ksl = list(e.get("knl") or []), list(e.get("ksl") or [])
            hxl = float(e.get("hxl", 0) or 0)
            if hxl:
                kind, physics["angle"] = "dipole", hxl
            elif len(knl) <= 1 and len(ksl) <= 1:
                # order 0: a dipole kick only — how an Xsuite line carries a corrector
                kind = "corrector"
                if knl and knl[0]:
                    physics["hkick"] = -float(knl[0])
                if ksl and ksl[0]:
                    physics["vkick"] = float(ksl[0])
            elif len(knl) > 1 and knl[1] and not any(knl[2:]):
                kind, physics["k1"] = "quadrupole", float(knl[1]) / length if length else float(knl[1])
        if (kind == "drift" and not options.keep_drifts) or (kind == "marker" and not options.keep_markers):
            pos += length
            continue
        if kind == "dipole" and "angle" not in physics:
            h = e.get("h", e.get("k0"))
            physics["angle"] = float(e["angle"]) if e.get("angle") is not None else (float(h) * length if h else 0.0)
        for k in ("k1", "k2", "k3", "ks"):
            if e.get(k) is not None and kind != "multipole":
                physics[k] = float(e[k])
        if kind in ("rf_cavity", "crab_cavity"):
            for k, out in (("voltage", "voltage"), ("frequency", "frequency"), ("lag", "phase")):
                if e.get(k) is not None:
                    physics[out] = float(e[k])
        kind = hint(name, kind, options) if kind in ("generic", "corrector", "dipole", "marker") else kind
        native = {k: v for k, v in e.items() if k != "__class__"}
        placed.append(Placed(name=name, kind=kind, s=pos, length=length, native_type=cls, native=native,
                             physics=physics))
        pos += length
    beam = {}
    ref = line.get("particle_ref") or data.get("particle_ref") or {}
    if ref:
        first = lambda v: (v[0] if isinstance(v, list) and v else v)  # noqa: E731
        mass, q, p0c = first(ref.get("mass0")), first(ref.get("q0")), first(ref.get("p0c"))
        species = next((s for s, m in MASSES.items() if mass and abs(float(mass) - m) / m < 1e-3), None)
        beam = {k: v for k, v in {"species": "positron" if species == "electron" and q and float(q) > 0 else species,
                                  "charge": float(q) if q is not None else None,
                                  "rest_mass": float(mass) / 1e6 if mass else None,
                                  "reference_momentum": float(p0c) / 1e9 if p0c else None}.items() if v is not None}
    doc = build(placed, source="xsuite", filename=filename, options=options,
                line_name=options.beamline or data.get("name") or "line", total_length=pos, beam=beam)
    if boundaries and options.output != "1":
        path = doc["paths"][0]["id"]
        doc["boundaries"] = [{**b, "path": path} for b in boundaries]
    return doc


register(Converter(name="xsuite", label="Xsuite line (.json)", extensions=(".json", ".xsuite.json"),
                   detect=lambda t: '"element_names"' in t and '"__class__"' in t, convert=convert_xsuite))
