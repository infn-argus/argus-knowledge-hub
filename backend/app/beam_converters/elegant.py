"""Elegant: lattice files (.lte).

Read: comments (`!`), continuation (`&` at a line's end), element definitions `NAME: TYPE, PARAM=value, …` with
numbers or quoted RPN expressions (`"0.5 2 *"`, with `sto` variables and the usual operators), `LINE = (…)`
with repetition and reversal, and `USE` when present. Elegant's twiss output is SDDS, read by the
Accelerator Model Toolbox rather than here; the lattice gives positions, lengths and strengths.
"""
from __future__ import annotations

import math
import re

from app.beam_converters import ConversionError, Converter, Options, register
from app.beam_converters.common import Placed, build, expand_line, hint, split_top

KINDS = {
    **{t: "drift" for t in ("DRIF", "DRIFT", "EDRIFT", "CSRDRIFT", "LSCDRIFT")},
    **{t: "quadrupole" for t in ("QUAD", "KQUAD", "QUADRUPOLE")},
    **{t: "sextupole" for t in ("SEXT", "KSEXT", "SEXTUPOLE")},
    **{t: "generic" for t in ("OCTU", "KOCT", "MULT", "FMULT", "KQUSE", "MATR", "EMATRIX", "ILMATRIX", "BRANCH")},
    **{t: "dipole" for t in ("SBEN", "SBEND", "RBEN", "RBEND", "CSBEND", "CSRCSBEND", "KSBEND", "NIBEND", "CCBEND",
                             "TUBEND", "BRAT")},
    **{t: "corrector" for t in ("HKICK", "VKICK", "KICKER", "EHKICK", "EVKICK", "EKICKER", "HKICKER", "VKICKER")},
    **{t: "bpm" for t in ("MONI", "HMON", "VMON", "MONITOR")},
    **{t: "rf_cavity" for t in ("RFCA", "RFCW", "RFDF", "TWLA", "TWMTA", "RFMODE", "TWPL", "RAMPRF", "RFTMEZ0", "MODRF")},
    **{t: "marker" for t in ("MARK", "MARKER", "WATCH", "CHARGE", "MALIGN", "CENTER", "ENERGY", "SCRIPT", "STRAY",
                             "SCATTER", "WAKE", "TRWAKE", "LSRMDLTR", "TWISS", "ROTATE", "FLOOR", "MAGNIFY")},
    **{t: "solenoid" for t in ("SOLE", "SOLENOID")},
    **{t: "collimator" for t in ("RCOL", "ECOL", "SCRAPER", "MAXAMP", "TAPERAPC", "TAPERAPE")},
}
NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


class _RPN:
    """Elegant's reverse-Polish expressions, with the variables `sto` defines."""
    BIN = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a / b,
           "pow": lambda a, b: a ** b, "^": lambda a, b: a ** b, "atan2": math.atan2}
    UN = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
          "atan": math.atan, "exp": math.exp, "ln": math.log, "log": math.log10, "abs": abs, "chs": lambda a: -a,
          "sqr": lambda a: a * a, "rec": lambda a: 1 / a}

    def __init__(self):
        self.vars = {"pi": math.pi, "c_mks": 299792458.0, "mev": 0.51099895, "e_mks": 1.602176634e-19}

    def eval(self, text: str) -> float:
        stack: list[float] = []
        tokens = text.split()
        i = 0
        while i < len(tokens):
            t = tokens[i]
            lt = t.lower()
            if NUM.match(t):
                stack.append(float(t))
            elif lt == "sto" and i + 1 < len(tokens):
                self.vars[tokens[i + 1].lower()] = stack[-1]
                i += 1
            elif lt in self.BIN:
                b, a = stack.pop(), stack.pop()
                stack.append(self.BIN[lt](a, b))
            elif lt in self.UN:
                stack.append(self.UN[lt](stack.pop()))
            elif lt in self.vars:
                stack.append(self.vars[lt])
            elif lt == "pop":
                stack.pop()
            else:
                raise ConversionError(f"cannot read the RPN expression {text!r} (at {t})")
            i += 1
        if not stack:
            raise ConversionError(f"the RPN expression {text!r} gives no value")
        return stack[-1]


def _join(text: str) -> list[str]:
    """Statements, with `&` continuations joined and comments dropped."""
    out, cur = [], ""
    for line in text.splitlines():
        line = line.split("!", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.endswith("&"):
            cur += line[:-1] + " "
            continue
        cur += line
        out.append(cur.strip())
        cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def parse(text: str):
    rpn = _RPN()
    defs: dict[str, tuple[str, dict]] = {}
    lines: dict[str, list[str]] = {}
    use = None
    for st in _join(text):
        if st.startswith("%"):
            rpn.eval(st[1:])
            continue
        m = re.match(r"^\"?([^\":]+?)\"?\s*:\s*line\s*=\s*\((.*)\)\s*$", st, re.I)
        if m:
            lines[m.group(1).strip().lower()] = split_top(m.group(2))
            continue
        m = re.match(r"^\"?([^\":]+?)\"?\s*:\s*([A-Za-z_]\w*)\s*(?:,(.*))?$", st)
        if m:
            attrs = {}
            for part in split_top(m.group(3) or ""):
                if "=" in part:
                    k, v = part.split("=", 1)
                    attrs[k.strip().upper()] = v.strip()
            defs[m.group(1).strip().lower()] = (m.group(2).upper(), attrs)
            continue
        m = re.match(r"^use\s*,\s*\"?([^\"]+)\"?", st, re.I)
        if m:
            use = m.group(1).strip().lower()
    return rpn, defs, lines, use


def _value(rpn: _RPN, raw: str):
    v = raw.strip()
    if NUM.match(v):
        return float(v)
    if v.startswith('"') and v.endswith('"'):
        inner = v[1:-1]
        try:
            return rpn.eval(inner)
        except ConversionError:
            return inner                       # a file name or a string parameter, kept as written
    return v


def convert_elegant(text: str, filename: str, options: Options) -> dict:
    rpn, defs, lines, use = parse(text)
    choice = (options.beamline or use or (list(lines)[-1] if lines else "")).lower()
    if not choice or choice not in lines:
        raise ConversionError(f"{filename}: no beam line {choice or '(LINE)'} to read")
    placed, pos = [], 0.0
    for name in expand_line(choice, lines):
        if name not in defs:
            raise ConversionError(f"the line {choice} uses {name}, which is not defined")
        etype, raw = defs[name]
        params = {k: _value(rpn, v) for k, v in raw.items()}
        num = lambda k, d=0.0: float(params[k]) if isinstance(params.get(k), (int, float)) else d  # noqa: E731
        length = num("L")
        base = KINDS.get(etype, "generic")
        if (base == "drift" and not options.keep_drifts) or (base == "marker" and not options.keep_markers):
            pos += length
            continue
        physics: dict = {}
        if base == "dipole":
            physics["angle"] = num("ANGLE")
            for k in ("E1", "E2", "K1", "TILT"):
                if k in params:
                    physics[k.lower()] = num(k)
        elif base == "quadrupole":
            physics["k1"] = num("K1")
        elif base == "sextupole":
            physics["k2"] = num("K2")
        elif base == "corrector":
            kick = num("KICK") or num("HKICK") or num("VKICK")
            if kick:
                physics["kick"] = kick
        elif base == "rf_cavity":
            for k, out in (("VOLT", "voltage"), ("FREQ", "frequency"), ("PHASE", "phase")):
                if k in params:
                    physics[out] = num(k)
        elif base == "solenoid":
            physics["ks"] = num("KS")
        kind = hint(name, base, options)
        caps = None
        if base == "corrector":
            plane = {"HKICK": ["horizontal_steering"], "EHKICK": ["horizontal_steering"], "VKICK": ["vertical_steering"],
                     "EVKICK": ["vertical_steering"]}.get(etype, ["horizontal_steering", "vertical_steering"])
            caps = ["beam_transport", "steering", "powered", *plane] + (["pulsed"] if kind == "kicker" else [])
        placed.append(Placed(name=name, kind=kind, s=pos, length=length, native_type=etype,
                             native={k: v for k, v in params.items()}, physics=physics, capabilities=caps))
        pos += length
    return build(placed, source="elegant", filename=filename, options=options, line_name=choice, total_length=pos,
                 beam={})


register(Converter(name="elegant", label="Elegant lattice (.lte)", extensions=(".lte", ".ele.lte"),
                   detect=lambda t: bool(re.search(r":\s*(kquad|csbend|drif|ksext|moni|rfca)\b", t, re.I)),
                   convert=convert_elegant))
