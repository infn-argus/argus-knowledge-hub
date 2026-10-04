"""Bmad: lattice files (.bmad).

Read: comments (`!`), continuation (`&`), variables (`a = 1.2`) and arithmetic in attributes, element
definitions `NAME: CLASS, attr = value, …` with inheritance from another element, `LINE = (…)` with
repetition and reversal, `USE, line`, and `parameter[particle]`, `parameter[e_tot]` / `parameter[p0c]` (eV) for
the beam. Bends take `angle`, or `g` (1/ρ) or `rho` with `l`. Collimators' `x_limit`/`y_limit` (and an
element's `aperture`) become boundaries. `call`, `superimpose`, `overlay` and `group` are not executed: they are
reported. Bmad's own name for the class is kept in `native.type`.
"""
from __future__ import annotations

import re
from typing import Optional

from app.beam_converters import ConversionError, Converter, Options, register
from app.beam_converters.common import Evaluator, Placed, build, expand_line, hint, split_top

KINDS = {"drift": "drift", "pipe": "drift", "quadrupole": "quadrupole", "sbend": "dipole", "rbend": "dipole",
         "sextupole": "sextupole", "octupole": "octupole", "hkicker": "corrector", "vkicker": "corrector",
         "kicker": "corrector", "rfcavity": "rf_cavity", "lcavity": "accelerating_structure", "solenoid": "solenoid",
         "sol_quad": "solenoid", "marker": "marker", "monitor": "bpm", "instrument": "generic_monitor",
         "ecollimator": "collimator", "rcollimator": "collimator", "wiggler": "wiggler", "undulator": "undulator",
         "multipole": "multipole", "ab_multipole": "multipole", "crab_cavity": "crab_cavity", "foil": "foil",
         "patch": "skip", "floor_shift": "skip", "fiducial": "fiducial", "photon_init": "photon_source",
         "mirror": "mirror", "crystal": "crystal", "detector": "camera", "elseparator": "kicker",
         "beginning_ele": "skip", "null_ele": "skip", "taylor": "generic", "match": "skip", "e_gun": "electron_source"}
NOT_RUN = ("call", "superimpose", "overlay", "group", "girder", "expand_lattice", "calc_reference_orbit",
           "write_digested", "no_superposition", "debug_marker", "title", "end_file")


def _statements(text: str) -> list[tuple[int, str]]:
    out, cur, start = [], "", None
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("!", 1)[0].rstrip()
        if not line.strip():
            continue
        start = start or n
        if line.endswith("&"):
            cur += line[:-1] + " "
            continue
        cur += line
        out.append((start, cur.strip()))
        cur, start = "", None
    if cur.strip():
        out.append((start or 0, cur.strip()))
    return out


class _Bmad:
    def __init__(self):
        self.ev = Evaluator(resolve_attr=self.attr)
        self.defs: dict[str, tuple[str, dict, int]] = {}
        self.lines: dict[str, list[str]] = {}
        self.params: dict[str, str] = {}
        self.use: Optional[str] = None
        self.skipped: list[str] = []

    def base(self, name: str, depth: int = 0) -> str:
        name = name.lower()
        if name in KINDS or depth > 30 or name not in self.defs:
            return name
        return self.base(self.defs[name][0], depth + 1)

    def merged(self, name: str, depth: int = 0) -> dict:
        name = name.lower()
        if name not in self.defs or depth > 30:
            return {}
        parent, attrs, _line = self.defs[name]
        return {**self.merged(parent, depth + 1), **attrs}

    def attr(self, element: str, key: str) -> Optional[float]:
        a = self.merged(element)
        return self.ev.eval(a[key]) if key in a else None


def parse(text: str) -> _Bmad:
    b = _Bmad()
    for line_no, st in _statements(text):
        low = st.lower()
        m = re.match(r"^parameter\s*\[\s*(\w+)\s*\]\s*=\s*(.+)$", low)
        if m:
            b.params[m.group(1)] = st.split("=", 1)[1].strip()
            continue
        m = re.match(r"^([\w.#]+)\s*\[\s*\w+\s*\]\s*=", low)       # beginning[beta_a] = …, q1[k1] = …
        if m:
            b.skipped.append(st[:60])
            continue
        m = re.match(r"^use\s*,\s*([\w.]+)", low)
        if m:
            b.use = m.group(1)
            continue
        if re.match(r"^(%s)\b" % "|".join(NOT_RUN), low):
            b.skipped.append(st[:60])
            continue
        m = re.match(r"^([\w.#]+)\s*:\s*line\s*=\s*\((.*)\)\s*$", st, re.I)
        if m:
            b.lines[m.group(1).lower()] = split_top(m.group(2))
            continue
        m = re.match(r"^([\w.#]+)\s*:\s*([\w.]+)\s*(?:,(.*))?$", st)
        if m:
            attrs = {}
            for part in split_top(m.group(3) or ""):
                if "=" in part:
                    k, v = part.split("=", 1)
                    attrs[k.strip().lower()] = v.strip()
                elif part.strip():
                    attrs[part.strip().lower()] = "1"            # a flag: `type = …`-less switches
            b.defs[m.group(1).lower()] = (m.group(2).lower(), attrs, line_no)
            continue
        m = re.match(r"^([A-Za-z_][\w.]*)\s*:?=\s*(.+)$", st)
        if m:
            b.ev.define(m.group(1), m.group(2))
            continue
        b.skipped.append(st[:60])
    return b


def _num(b: _Bmad, attrs: dict, key: str, default=None):
    if key not in attrs:
        return default
    try:
        return b.ev.eval(attrs[key])
    except ConversionError:
        return default


def convert_bmad(text: str, filename: str, options: Options) -> dict:
    b = parse(text)
    choice = (options.beamline or b.use or (list(b.lines)[-1] if b.lines else "")).lower()
    if not choice or choice not in b.lines:
        raise ConversionError(f"{filename}: no beam line {choice or '(LINE)'} to read (USE one, or name it)")
    placed, pos = [], 0.0
    for name in expand_line(choice, b.lines):
        if name not in b.defs:
            raise ConversionError(f"the line {choice} uses {name}, which is not defined")
        cls = b.base(name)
        attrs = b.merged(name)
        kind = KINDS.get(cls, "generic")
        length = float(_num(b, attrs, "l", 0.0) or 0.0)
        if kind == "skip" or (kind == "drift" and not options.keep_drifts) or (
                kind == "marker" and not options.keep_markers):
            pos += length
            continue
        physics: dict = {}
        if kind == "dipole":
            angle = _num(b, attrs, "angle")
            if angle is None and _num(b, attrs, "g") is not None:
                angle = _num(b, attrs, "g") * length
            if angle is None and _num(b, attrs, "rho"):
                angle = length / _num(b, attrs, "rho")
            physics["angle"] = float(angle or 0.0)
            for k in ("e1", "e2", "k1"):
                if _num(b, attrs, k) is not None:
                    physics[k] = _num(b, attrs, k)
        for k in ("k1", "k2", "k3", "ks"):
            if kind != "dipole" and _num(b, attrs, k) is not None:
                physics[k] = _num(b, attrs, k)
        for k, out in (("kick", "kick"), ("hkick", "hkick"), ("vkick", "vkick"), ("voltage", "voltage"),
                       ("rf_frequency", "frequency"), ("phi0", "phase"), ("gradient", "gradient")):
            if _num(b, attrs, k) is not None:
                physics[out] = _num(b, attrs, k)
        component: dict = {}
        xl, yl = _num(b, attrs, "x_limit"), _num(b, attrs, "y_limit")
        if xl is None and yl is None and _num(b, attrs, "aperture"):
            xl = yl = _num(b, attrs, "aperture")
        if xl and yl:
            shape = {"shape": "ellipse", "semi_axis_x": xl, "semi_axis_y": yl} if cls == "ecollimator" else \
                {"shape": "rectangle", "half_width_x": xl, "half_height_y": yl}
            component["boundaries"] = [{"profile": shape, "note": f"Bmad {cls} limits"}]
        kind = hint(name, kind, options) if kind in ("generic", "corrector", "dipole") else kind
        caps = None
        if kind == "corrector":
            plane = {"hkicker": ["horizontal_steering"], "vkicker": ["vertical_steering"]}.get(
                cls, ["horizontal_steering", "vertical_steering"])
            caps = ["particle_transport", "steering", "powered", *plane]
        parent = b.defs[name][0]
        native = {}
        for k, v in attrs.items():
            try:
                native[k.upper()] = b.ev.eval(v)
            except ConversionError:
                native[k.upper()] = v.strip("\"'")
        placed.append(Placed(name=name, kind=kind, s=pos, length=length, native_type=cls.upper(), native=native,
                             physics=physics, capabilities=caps,
                             family=parent if parent in b.defs else None,
                             location=f"{filename}:{b.defs[name][2]}", component=component))
        pos += length
    species = (b.params.get("particle") or "").strip().lower() or None
    energy = None
    for key, scale in (("e_tot", 1e-9), ("p0c", 1e-9)):
        if key in b.params:
            try:
                energy = b.ev.eval(b.params[key]) * scale
            except ConversionError:
                pass
            break
    beam = {k: v for k, v in {"species": species, "reference_energy": energy,
                              "charge": {"electron": -1, "positron": 1, "proton": 1, "antiproton": -1}.get(species or "")
                              }.items() if v is not None}
    doc = build(placed, source="bmad", filename=filename, options=options, line_name=choice, total_length=pos,
                beam=beam)
    if b.skipped and "conversion" in doc:
        doc["conversion"]["not_executed"] = b.skipped[:50]
    return doc


register(Converter(name="bmad", label="Bmad lattice (.bmad)", extensions=(".bmad", ".lat"),
                   detect=lambda t: "parameter[" in t.lower() or bool(re.search(r":\s*(sbend|lcavity|sol_quad)\b", t, re.I)),
                   convert=convert_bmad))
