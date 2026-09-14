"""What a control template actually is, as equipment.

The configuration says `template: ocem`. An inventory wants "a magnet
power supply made by OCEM". That translation is not guesswork and does not
belong in a table here: infn-epics-ioc/ibek-templates already states it,
in the shape of its own directory tree —

    templates/<category>/<vendor>/<template>.yaml.j2
    templates/ps/ocem/ocem.yaml.j2
    templates/vac/agilent/agilent-vac.yaml.j2

so the catalogue is read from that repository and stays true as templates
are added. The fallback below covers only the handful of templates that
have no ibek file because the IOC runs on the instrument itself over ssh.

Anything still unknown comes out with its category unset rather than
guessed. An unknown device that says so gets filled in by a person; one
labelled "Power Supply" because it sat in the `mag` group is a wrong
answer wearing the clothes of a right one.
"""
import os
from typing import NamedTuple, Optional

CATEGORY_LABELS: dict[str, str] = {
    "ps": "Power Supply",
    "motor": "Motion Controller",
    "vac": "Vacuum",
    "daq": "Data Acquisition",
    "io": "I/O",
    "cooling": "Cooling",
    "modulator": "Modulator",
    "mps": "Machine Protection",
    "synch": "Synchronisation",
}

# Not devices: shared record fragments every IOC can include.
NON_DEVICE_CATEGORIES = {"global"}


class Kind(NamedTuple):
    category: str = ""        # ps | vac | motor | daq | …
    device_class: str = ""    # "Power Supply", "Vacuum", …
    vendor: Optional[str] = None
    model: Optional[str] = None
    # Where the reading came from, so it can be checked.
    source: str = "unknown"


# Templates with no ibek file: the IOC runs on the instrument over ssh, or
# the device is driven by a hand-written soft IOC.
FALLBACK: dict[str, Kind] = {
    "libera-llrf": Kind("rf", "Low-Level RF", "Instrumentation Technologies",
                        "Libera LLRF", "built-in"),
    "libera-sppp": Kind("daq", "Data Acquisition", "Instrumentation Technologies",
                        "Libera Single Pass", "built-in"),
    "STEMlab125": Kind("daq", "Data Acquisition", "Red Pitaya", "STEMlab 125",
                       "built-in"),
    "mrf-utca-300": Kind("timing", "Timing", "Micro-Research Finland",
                         "uTCA EVR/EVG", "built-in"),
}

# Vendors whose directory name is not how the vendor spells itself.
VENDOR_NAMES: dict[str, str] = {
    "psEEI": "EEI",
    "TTI": "Aim-TTi",
    "iTest": "Bilt iTest",
    "caenels": "CAEN ELS",
    "icpdas": "ICP DAS",
    "smc": "SMC",
    "ppt": "PPT",
    "sigmaphi": "Sigmaphi",
    "polyscience": "PolyScience",
    "agilent": "Agilent",
    "pfeiffer": "Pfeiffer",
    "danfysik": "Danfysik",
    "hazemeyer": "Hazemeyer",
    "ocem": "OCEM",
    "kima": "Kyma",
    "menlo": "Menlo Systems",
    "modbus": None,          # a protocol, not a maker
    "modbus-generic": None,
    "midivac": None,
    "tektronix": "Tektronix",
    "bergoz-bcm": "Bergoz",
    "adcamera": None,        # a driver family, not a maker
    "adcamera2": None,
    "danfysik_hallprobes": "Danfysik",
    "plceli": None,
    "ptu": None,
    "ssrip-mps": None,
    "scandinova-mod-k400": "ScandiNova",
    "scandinova-scandicat-mod": "ScandiNova",
}

# devtype tells the model apart where one template serves several.
MODELS_BY_DEVTYPE: dict[str, str] = {
    "E642": "E642",
    "modbusps": "Modbus PS",
    "modbusps4chan": "Modbus PS 4-channel",
    "sys8x00": "System 8000",
    "fastps": "FAST-PS",
    "easydriver": "EASY-DRIVER",
    "histar": "Hi-Star",
    "haz-ser": "serial",
    "haz-iocast": "IOCast",
    "ipcmini": "IPCMini",
    "twistorr305": "TwisTorr 305",
    "tpg366": "TPG 366",
    "tpg300": "TPG 300",
    "icp7215": "I-7215 (RTD input)",
    "icp7226": "I-7226 (analogue output)",
    "icp7250": "I-7250 (digital I/O)",
    "icp7060": "I-7060 (relay output)",
    "mso58lp-asyn": "MSO58LP",
    "pollux": "Pollux",
    "pigcs2": "Mercury GCS2",
    "thorlabs": "KIM piezo inertia",
    "technosoft-asyn": "TML",
    "smc": "HECR",
}

# What a vacuum device is for, where the configuration says so.
FUNCTIONS: dict[str, str] = {
    "ion": "Ion pump controller",
    "turbo": "Turbomolecular pump",
    "scroll": "Scroll pump",
    "pig": "Penning gauge controller",
}


def load_templates(root: Optional[str]) -> dict[str, tuple[str, Optional[str]]]:
    """template name -> (category, vendor directory), from the ibek repo.

    Returns an empty map when the repository is not to hand, which leaves
    every reading to the fallback and says so in each device's `source`.
    """
    found: dict[str, tuple[str, Optional[str]]] = {}
    if not root:
        return found
    base = os.path.join(root, "templates") if os.path.isdir(os.path.join(root, "templates")) else root
    if not os.path.isdir(base):
        return found

    for category in sorted(os.listdir(base)):
        category_path = os.path.join(base, category)
        if not os.path.isdir(category_path) or category in NON_DEVICE_CATEGORIES:
            continue
        for entry in sorted(os.listdir(category_path)):
            entry_path = os.path.join(category_path, entry)
            if entry.endswith(".yaml.j2"):
                # templates/motor/motor.yaml.j2 — no vendor level.
                found[entry[: -len(".yaml.j2")]] = (category, None)
            elif os.path.isdir(entry_path):
                for leaf in sorted(os.listdir(entry_path)):
                    if leaf.endswith(".yaml.j2"):
                        found[leaf[: -len(".yaml.j2")]] = (category, entry)
    return found


def classify(template: Optional[str], devtype: Optional[str],
             devfunc: Optional[str],
             templates: Optional[dict] = None) -> Kind:
    """The equipment a control entry describes, or an honest blank."""
    templates = templates or {}
    name = (template or "").strip()

    if name in templates:
        category, vendor_dir = templates[name]
        vendor = VENDOR_NAMES.get(vendor_dir or "", vendor_dir) if vendor_dir else None
        model = MODELS_BY_DEVTYPE.get(devtype or "")
        if not model and devfunc in FUNCTIONS:
            model = FUNCTIONS[devfunc]
        return Kind(
            category=category,
            device_class=CATEGORY_LABELS.get(category, category.title()),
            vendor=vendor,
            model=model,
            source=f"ibek:templates/{category}/{vendor_dir + '/' if vendor_dir else ''}{name}.yaml.j2",
        )

    if name in FALLBACK:
        kind = FALLBACK[name]
        return kind._replace(model=MODELS_BY_DEVTYPE.get(devtype or "") or kind.model)

    return Kind(source="unknown")
