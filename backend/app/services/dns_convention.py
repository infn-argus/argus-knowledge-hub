"""What an INFN hostname says about the machine behind it.

INFN's DNS naming convention (Confluence, space LDCG, "Naming Convention DNS Elements –
PROPOSAL –") writes a name as four fields with no separator, in lower case:

    prefix(2) + facility/group + functionality/family + sequential(3 digits)
      sc         sparc           moxa                     002       scsparcmoxa002

The first field is the class of machine, and it is the only field read here. The facility and
family fields are free text in practice (`mxa`, `chlmxa`, `enea` for a Moxa; `icp` for an ICPDAS
module the page calls `icpdas`), and the digit count is loosely followed, so none of them is parsed
for meaning.

It is a proposal, and not everyone follows it: ELI's power-supply hosts are named
`lel-mag-cpsu01.int.eli-np.ro`, which has no class prefix at all. A name that does not fit is
returned as unclassified, never guessed at.
"""
import re
from dataclasses import dataclass
from typing import Optional

IPV4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

# class prefix -> (what the page says it is, is it virtual)
CLASSES = {
    "vl": ("Virtual Linux machine", True), "pl": ("Physical Linux machine", False),
    "vw": ("Virtual Windows machine", True), "pw": ("Physical Windows machine", False),
    "dl": ("Docker Linux", True), "dw": ("Docker Windows", True),
    "sw": ("Switch", False), "il": ("iLO management controller", False),
    "mv": ("Motor controller", False), "cc": ("Camera", False),
    "sc": ("Serial converter", False), "gd": ("Generic device", False),
    "ps": ("Power supply", False), "bd": ("Beam instrumentation", False),
    "fd": ("Fluid device controller", False), "rd": ("RF device", False),
    "vd": ("Vacuum device", False), "qd": ("Cryogenic device", False),
    "un": ("Undulator device", False), "sd": ("Safety device, radioprotection, access", False),
    "ns": ("Storage device (NAS)", False), "dd": ("DAQ device", False),
    "da": ("DAC device", False), "mp": ("Machine protection / PLC device", False),
}
HOSTS = {"vl", "pl", "vw", "pw", "dl", "dw", "ns", "il"}
INSTRUMENTS = {"mv", "gd", "ps", "bd", "fd", "rd", "vd", "qd", "un", "sd", "dd", "da", "mp"}
# A console is a family, not a class: `pwsparcco001` is a physical Windows machine in the
# control room, `plsparcmagnuc001` a small PC for the magnets' console.
CONSOLE_FAMILIES = ("co", "nuc", "pc")

# Moxa's default: serial port N answers on TCP port 4000 + N. An address that is only a number
# says nothing about what it is, and a port in this range is the best evidence there is.
MOXA_PORTS = range(4001, 5000)

_NAME = re.compile(r"^(?P<cls>" + "|".join(CLASSES) + r")(?P<rest>[a-z][a-z0-9-]*?)(?P<seq>\d+)$")


@dataclass(frozen=True)
class Parsed:
    prefix: str
    rest: str            # facility and family, undivided
    sequence: str
    label: str
    virtual: bool

    @property
    def is_console(self) -> bool:
        return self.prefix in HOSTS and self.rest.endswith(CONSOLE_FAMILIES)


def short_name(hostname: str) -> str:
    """The first label, lower case: `SCSPARCMOXA002.lnf.infn.it` -> `scsparcmoxa002`."""
    return (hostname or "").strip().lower().rstrip(".").split(".")[0]


def parse(hostname: str) -> Optional[Parsed]:
    """The class of machine a name says, or None if it names none (or is an address)."""
    text = (hostname or "").strip()
    if not text or IPV4.match(text):
        return None
    found = _NAME.match(short_name(text))
    if not found:
        return None
    label, virtual = CLASSES[found["cls"]]
    return Parsed(found["cls"], found["rest"], found["seq"], label, virtual)


def endpoint_kind(address: str, port=None) -> tuple:
    """(kind, how it was read) for an Access Point: Serial converter, Host, Instrument, Camera or
    Unknown, and the evidence, so a person can see whether to believe it."""
    text = (address or "").strip()
    if text and IPV4.match(text):
        try:
            if int(port) in MOXA_PORTS:
                return ("Serial converter",
                        f"the address is a bare IP and port {int(port)} is in Moxa's 4001-4999 range")
        except (TypeError, ValueError):
            pass
        return ("Unknown", "")
    parsed = parse(text)
    if parsed is None:
        return ("Unknown", "")
    how = f"the class prefix `{parsed.prefix}` ({parsed.label}) of the DNS naming convention"
    if parsed.prefix == "sc":
        return ("Serial converter", how)
    if parsed.prefix == "cc":
        return ("Camera", how)
    if parsed.prefix in HOSTS:
        return ("Host", how)
    if parsed.prefix in INSTRUMENTS:
        return ("Instrument", how)
    return ("Unknown", how)


def it_equipment(hostname: str) -> Optional[tuple]:
    """(catalogue type, attributes, evidence) for the IT equipment this hostname names, or None where
    it names an instrument, a camera or nothing: those keep their own type and are not IT."""
    parsed = parse(hostname)
    if parsed is None:
        return None
    how = f"the class prefix `{parsed.prefix}` ({parsed.label}) of INFN's DNS naming convention"
    if parsed.prefix == "sc":
        return ("Serial Converter", {}, how)
    if parsed.prefix == "sw":
        return ("Switch", {}, how)
    if parsed.prefix == "ns":
        return ("Server", {"is_virtual": False, "role": "Storage"}, how)
    if parsed.prefix in ("vl", "pl", "vw", "pw", "dl", "dw"):
        if parsed.is_console:
            return ("Workstation", {"workstation_role": "Operator console"},
                    how + ", and a family of `co`, `nuc` or `pc`: a console")
        return ("Server", {"is_virtual": parsed.virtual}, how)
    return None
