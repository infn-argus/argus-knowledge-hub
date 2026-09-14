"""What a device acts on, read from what it is called.

Names here are not labels, they are a code: `QUATB002` is quadrupole 002
in transfer line B, `CHHLL015` a horizontal corrector in the linac,
`GUNSIP01` the gun's first sputter-ion pump. The element is the thing that
matters to a physicist — the magnet, the pump, the screen — while the
device is what drives it, and the inventory needs both.

Two conventions are in use. SPARC and BTF put the function first
(`QUA`+`TB`+`002`); EUAPS separates with hyphens and puts the zone first
(`FI8-CAM-06`). Both are read here, and a name that matches neither gets
no element rather than a guess, because a quadrupole that is really a
corrector is worse in an inventory than an unlabelled one.
"""
import re
from typing import NamedTuple, Optional


class Element(NamedTuple):
    kind: str
    # The part of the name the reading is based on, so somebody checking
    # can see why it was read that way.
    matched_on: str


# Function codes, longest first so DHS is tried before DH.
FUNCTION_CODES: list[tuple[str, str]] = [
    ("QUA", "Quadrupole"),
    ("SEX", "Sextupole"),
    ("SOL", "Solenoid"),
    ("DHP", "Dipole (pulsed)"),
    ("DHS", "Dipole"),
    ("DHR", "Dipole"),
    ("DHY", "Dipole"),
    ("DVR", "Dipole (vertical)"),
    ("CHH", "Corrector (horizontal)"),
    ("CVV", "Corrector (vertical)"),
    ("UFS", "Corrector (fast)"),
    ("SLT", "Slit"),
    ("TGT", "Target"),
    ("FLG", "Flag"),
    ("SCR", "Screen"),
    ("SIP", "Ion pump"),
    ("NEG", "NEG pump"),
    ("TRB", "Turbomolecular pump"),
    ("PRY", "Primary pump"),
    ("VGA", "Vacuum gauge"),
    ("VUG", "Vacuum gauge"),
    ("VGC", "Vacuum gauge"),
    ("BPM", "Beam position monitor"),
    ("BCM", "Beam charge monitor"),
    ("CAM", "Camera"),
    ("CHL", "Chiller"),
    ("LAS", "Laser"),
    ("UND", "Undulator"),
    ("MOD", "Modulator"),
    ("KLY", "Klystron"),
]

# EUAPS motion axes, where the middle group names the movement.
AXIS_CODES: dict[str, str] = {
    "HMN": "Mirror mount (horizontal)",
    "VMN": "Mirror mount (vertical)",
    "HPB": "Piezo (horizontal)",
    "VPB": "Piezo (vertical)",
    "MMR": "Mirror",
    "MPB": "Parabolic mirror",
    "HEX": "Hexapod axis",
    "DIP": "Diagnostic insert",
    "SLT": "Slit",
    "PBM": "Beam probe",
    "PRH": "Probe (horizontal)",
    "PRV": "Probe (vertical)",
    "CTR": "Controller",
}

HYPHENATED = re.compile(r"^([A-Z]{1,3}\d*)-([A-Z]{2,4})-?(\d*)$")


def element_of(name: str) -> Optional[Element]:
    """The beamline element this device name refers to, where it is legible."""
    text = (name or "").strip().upper()
    if not text:
        return None

    hyphenated = HYPHENATED.match(text)
    if hyphenated:
        code = hyphenated.group(2)
        if code in AXIS_CODES:
            return Element(AXIS_CODES[code], code)
        for prefix, kind in FUNCTION_CODES:
            if code.startswith(prefix):
                return Element(kind, prefix)
        return None

    for prefix, kind in FUNCTION_CODES:
        if text.startswith(prefix):
            return Element(kind, prefix)
    # The code is not always first: W1KSIP01 is a waveguide ion pump, and
    # AC1VGA01 an accelerating-section gauge.
    for prefix, kind in FUNCTION_CODES:
        if prefix in text[1:]:
            return Element(kind, prefix)
    return None
