"""Accelerator Toolbox: a lattice saved as JSON by pyAT (`lattice.save("ring.json")`).

Read: `properties` (name, energy in eV, particle, periodicity) and `elements`, each with `Class`, `FamName`,
`Length` and AT's parameters: `BendingAngle`, `EntranceAngle`/`ExitAngle`, `PolynomB` (AT stores k_n / n!,
so k1 = PolynomB[1], k2 = 2·PolynomB[2], k3 = 6·PolynomB[3]), `K`, `KickAngle`, `Voltage`, `Frequency`,
`PhaseLag`, `HarmNumber`. `FamName` is the family: elements of a family share a definition. Apertures given
on an element (`EApertures` = ellipse semi-axes, `RApertures` = x−, x+, y−, y+) become its boundaries.
"""
from __future__ import annotations

import json

from app.beam_converters import ConversionError, Converter, Options, register
from app.beam_converters.common import Placed, build, hint

KINDS = {"Drift": "drift", "Dipole": "dipole", "Bend": "dipole", "Quadrupole": "quadrupole",
         "Sextupole": "sextupole", "Octupole": "octupole", "Multipole": "multipole", "ThinMultipole": "multipole",
         "Corrector": "corrector", "RFCavity": "rf_cavity", "Monitor": "bpm", "Marker": "marker",
         "Solenoid": "solenoid", "Wiggler": "wiggler", "Collimator": "collimator", "Aperture": "marker",
         "M66": "generic"}
FACT = {1: 1.0, 2: 2.0, 3: 6.0}


def _pb(e: dict, n: int):
    pb = e.get("PolynomB") or []
    return float(pb[n]) * FACT[n] if len(pb) > n and pb[n] else None


def convert_at(text: str, filename: str, options: Options) -> dict:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConversionError(f"{filename}: not JSON ({e.msg})") from e
    elements = data.get("elements") if isinstance(data, dict) else data
    if not isinstance(elements, list) or not elements or "FamName" not in elements[0]:
        raise ConversionError(f"{filename}: an AT lattice needs elements with FamName")
    props = data.get("properties", {}) if isinstance(data, dict) else {}
    placed, pos = [], 0.0
    for e in elements:
        cls = e.get("Class") or ("Drift" if e.get("PassMethod") == "DriftPass" else "Marker")
        length = float(e.get("Length", 0.0) or 0.0)
        kind = KINDS.get(cls, "generic")
        if (kind == "drift" and not options.keep_drifts) or (kind == "marker" and not options.keep_markers):
            pos += length
            continue
        physics: dict = {}
        if kind == "dipole":
            physics["angle"] = float(e.get("BendingAngle", 0.0) or 0.0)
            for k, out in (("EntranceAngle", "e1"), ("ExitAngle", "e2")):
                if e.get(k) is not None:
                    physics[out] = float(e[k])
            if _pb(e, 1):
                physics["k1"] = _pb(e, 1)
        elif kind == "quadrupole":
            physics["k1"] = float(e["K"]) if e.get("K") is not None else (_pb(e, 1) or 0.0)
        elif kind == "sextupole":
            physics["k2"] = _pb(e, 2) or 0.0
        elif kind == "octupole":
            physics["k3"] = _pb(e, 3) or 0.0
        elif kind == "corrector" and e.get("KickAngle") is not None:
            kx, ky = (list(e["KickAngle"]) + [0, 0])[:2]
            physics.update({k: float(v) for k, v in (("hkick", kx), ("vkick", ky)) if v})
        elif kind == "rf_cavity":
            for k, out in (("Voltage", "voltage"), ("Frequency", "frequency"), ("PhaseLag", "phase"),
                           ("HarmNumber", "harmonic")):
                if e.get(k) is not None:
                    physics[out] = float(e[k])
        elif kind == "solenoid" and e.get("K") is not None:
            physics["ks"] = float(e["K"])
        bounds = []
        if e.get("EApertures"):
            ax, ay = e["EApertures"][:2]
            bounds.append({"profile": {"shape": "ellipse", "semi_axis_x": float(ax), "semi_axis_y": float(ay)},
                           "note": "AT EApertures"})
        if e.get("RApertures"):
            x0, x1, y0, y1 = (float(v) for v in e["RApertures"][:4])
            prof = {"shape": "rectangle", "half_width_x": (x1 - x0) / 2, "half_height_y": (y1 - y0) / 2}
            if x0 + x1:
                prof["offset_x"] = (x1 + x0) / 2
            if y0 + y1:
                prof["offset_y"] = (y1 + y0) / 2
            bounds.append({"profile": prof, "note": "AT RApertures"})
        name = e.get("FamName") or cls
        kind = hint(name, kind, options) if kind in ("generic", "corrector", "dipole", "marker") else kind
        caps = None
        if kind == "corrector":
            caps = ["particle_transport", "steering", "powered", "horizontal_steering", "vertical_steering"]
        placed.append(Placed(name=name, kind=kind, s=pos, length=length, native_type=cls,
                             native={k: v for k, v in e.items() if k != "Class"}, physics=physics, capabilities=caps,
                             family=name, component={"boundaries": bounds} if bounds else {}))
        pos += length
    particle = props.get("particle") or {}
    pname = particle.get("name") if isinstance(particle, dict) else particle
    beam = {k: v for k, v in {"species": pname, "reference_energy": float(props["energy"]) / 1e9
                              if props.get("energy") else None,
                              "charge": (particle.get("charge") if isinstance(particle, dict) else None)}.items()
            if v is not None}
    return build(placed, source="at", filename=filename, options=options,
                 line_name=options.beamline or props.get("name") or "ring", total_length=pos, beam=beam)


register(Converter(name="at", label="Accelerator Toolbox (pyAT .json)", extensions=(".json", ".at.json"),
                   detect=lambda t: '"FamName"' in t and '"PassMethod"' in t or '"atjson"' in t, convert=convert_at))
