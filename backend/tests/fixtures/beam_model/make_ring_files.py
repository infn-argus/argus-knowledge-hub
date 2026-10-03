"""Writes the DAΦNE-accumulator-like ring as a MAD-X sequence, an Elegant lattice and a MAD-X TFS twiss table,
from one element order (the real accumulator's naming), so the converters can be checked against each other.
Lengths and strengths are illustrative; the layout closes (eight 45° dipoles). Run it to regenerate."""
import math
from pathlib import Path

HERE = Path(__file__).parent
C = 32.56
ORDER = """SPTA1001 DIPA11 BPSA11 SXPA101 QUAA101 SXPA102 QUAA102 QUAA103 BPSA12 CHV11 DIPA12 BPSA13 KCKA1001 CHV12
KCKA2001 BPSA21 DIPA21 CHV21 BPSA22 QUAA201 QUAA202 SXPA201 QUAA203 SXPA202 BPSA23 DIPA22 SPTA2001
CHV31 BPSA31 DIPA31 BPSA32 SXPA301 QUAA301 SXPA302 QUAA302 QUAA303 CHV32 DIPA32 BPSA33 KCKA3001
CHV41 KCKA4001 BPSA41 DIPA41 CHV42 QUAA401 QUAA402 SXPA401 QUAA403 SXPA402 BPSA42 DIPA42 BPSA43 CHV43""".split()


def kind(n):
    return {"SPT": "septum", "DIP": "dipole", "BPS": "bpm", "SXP": "sextupole", "QUA": "quadrupole", "CHV": "corrector",
            "KCK": "kicker"}[n[:3]]


LEN = {"septum": 0.6, "dipole": 1.2, "bpm": 0.0, "sextupole": 0.1, "quadrupole": 0.3, "corrector": 0.1, "kicker": 0.3}
ANGLE = 2 * math.pi / 8
lengths = [LEN[kind(n)] for n in ORDER]
# Four-fold symmetry, so the layout closes as a real ring does: each quadrant has its two dipoles at the same
# places (an arc span between them, a straight after), and the other elements are spread evenly between dipoles.
ARC, OFFSET = 4.2, 0.9
dipoles = [i for i, n in enumerate(ORDER) if kind(n) == "dipole"]
fixed = {i: (j // 2) * C / 4 + OFFSET + (ARC if j % 2 else 0.0) for j, i in enumerate(dipoles)}
fixed[0] = 0.0                                               # the injection septum is s = 0
entries = [0.0] * len(ORDER)
anchors = sorted(fixed) + [len(ORDER)]
for a, b in zip(anchors, anchors[1:]):
    entries[a] = fixed[a]
    start = fixed[a] + lengths[a]
    end = fixed[b] if b < len(ORDER) else C
    inner = list(range(a + 1, b))
    free = end - start - sum(lengths[i] for i in inner)
    gap = free / (len(inner) + 1)
    pos = start + gap
    for i in inner:
        entries[i] = pos
        pos += lengths[i] + gap
assert all(x < y for x, y in zip(entries, entries[1:]))

k1 = {n: (4.30926 if n == "QUAA101" else round(4.0 + 0.3 * ((i % 3) - 1), 5) * (1 if i % 2 else -1))
      for i, n in enumerate(o for o in ORDER if kind(o) == "quadrupole")}


def madx():
    out = ["! DAΦNE-accumulator-like ring (illustrative strengths)", "beam, particle=electron, energy=0.51;",
           "ang := twopi/8;", "lb = 1.2;", "kqf = 4.30926;", "dip: sbend, l=lb, angle=ang;",
           "quad: quadrupole, l=0.3;", "sxp: sextupole, l=0.1, k2=12.5;", "chv: kicker, l=0.1;",
           "kck: hkicker, l=0.3;", "spt: rbend, l=0.6, angle=0;", "bpm: monitor;"]
    for n in ORDER:
        if kind(n) == "quadrupole":
            out.append(f"{n}: quad, k1={'kqf' if n == 'QUAA101' else k1[n]};")
    out.append(f"acc: sequence, l={C}, refer=centre;")
    cls = {"septum": "spt", "dipole": "dip", "bpm": "bpm", "sextupole": "sxp", "corrector": "chv", "kicker": "kck"}
    for n, L, e in zip(ORDER, lengths, entries):
        at = round(e + L / 2, 6)
        out.append(f"  {n}, at={at};" if kind(n) == "quadrupole" else f"  {n}: {cls[kind(n)]}, at={at};")
    out += ["endsequence;", "use, sequence=acc;", "twiss, file=acc.tfs;"]
    return "\n".join(out) + "\n"


def elegant():
    out = ["! DAΦNE-accumulator-like ring (illustrative strengths)", 'DIP: CSBEND, L=1.2, ANGLE="pi 4 /"',
           "SXP: KSEXT, L=0.1, K2=12.5", "CHV: KICKER, L=0.1", "KCK: KICKER, L=0.3", "SPT: CSBEND, L=0.6, ANGLE=0",
           "BPM: MONI, L=0"]
    names, pos = [], 0.0
    for i, (n, L, e) in enumerate(zip(ORDER, lengths, entries)):
        gap = round(e - pos, 9)
        if gap > 1e-9:
            out.append(f"D{i}: DRIF, L={gap}")
            names.append(f"D{i}")
        c = {"septum": "SPT", "dipole": "DIP", "bpm": "BPM", "sextupole": "SXP", "corrector": "CHV", "kicker": "KCK"}
        if kind(n) == "quadrupole":
            out.append(f"{n}: KQUAD, L=0.3, K1={k1[n]}")
        else:
            out.append(f"{n}: {c[kind(n)]}" if False else f'{n}: {"KQUAD" if 0 else {"SPT": "CSBEND", "DIP": "CSBEND", "BPM": "MONI", "SXP": "KSEXT", "CHV": "KICKER", "KCK": "KICKER"}[c[kind(n)]]}, &')
            out.append({"SPT": "  L=0.6, ANGLE=0", "DIP": '  L=1.2, ANGLE="pi 4 /"', "BPM": "  L=0",
                        "SXP": "  L=0.1, K2=12.5", "CHV": "  L=0.1", "KCK": "  L=0.3"}[c[kind(n)]])
        names.append(n)
        pos = e + L
    tail = round(C - pos, 9)
    if tail > 1e-9:
        out.append(f"DEND: DRIF, L={tail}")
        names.append("DEND")
    chunks = [", ".join(names[i:i + 8]) for i in range(0, len(names), 8)]
    out.append("ACC: LINE=(" + ", &\n  ".join(chunks) + ")")
    return "\n".join(out) + "\n"


def tfs():
    cols = ["NAME", "KEYWORD", "S", "L", "ANGLE", "K1L", "K2L", "BETX", "BETY", "ALFX", "ALFY", "DX", "MUX", "MUY"]
    rows = ['"$START" "MARKER" 0 0 0 0 0 3.2 4.1 0 0 0 0 0']
    for n, L, e in zip(ORDER, lengths, entries):
        sx = e + L
        ph = 2 * math.pi * sx / C
        kw = {"septum": "RBEND", "dipole": "SBEND", "bpm": "MONITOR", "sextupole": "SEXTUPOLE",
              "quadrupole": "QUADRUPOLE", "corrector": "KICKER", "kicker": "HKICKER"}[kind(n)]
        ang = ANGLE if kind(n) == "dipole" else 0
        k1l = k1.get(n, 0) * L if kind(n) == "quadrupole" else 0
        k2l = 12.5 * L if kind(n) == "sextupole" else 0
        bx = 3 + 2 * math.sin(4 * ph) ** 2
        by = 4 + 1.5 * math.cos(4 * ph) ** 2
        dx = 0.4 * abs(math.sin(8 * ph))
        rows.append(f'"{n}:1" "{kw}" {sx:.6f} {L} {ang:.9f} {k1l:.6f} {k2l:.6f} {bx:.4f} {by:.4f} 0 0 {dx:.4f} '
                    f'{sx / C * 3.1:.5f} {sx / C * 2.2:.5f}')
    head = ['@ NAME %05s "TWISS"', '@ TYPE %05s "TWISS"', '@ SEQUENCE %03s "ACC"', '@ PARTICLE %08s "ELECTRON"',
            '@ ENERGY %le 0.51', f'@ LENGTH %le {C}', '@ Q1 %le 3.1', '@ Q2 %le 2.2', '@ ORIGIN %16s "5.09.00 Linux 64"']
    return "\n".join(head + ["* " + " ".join(cols), "$ " + " ".join(["%s", "%s"] + ["%le"] * 12)] + rows) + "\n"


if __name__ == "__main__":
    (HERE / "dafne_accumulator.madx").write_text(madx())
    (HERE / "dafne_accumulator.lte").write_text(elegant())
    (HERE / "dafne_accumulator_twiss.tfs").write_text(tfs())
    print("written")
