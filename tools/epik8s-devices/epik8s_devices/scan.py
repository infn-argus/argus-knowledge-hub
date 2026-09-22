"""Reading a beamline's control configuration as an inventory of equipment.

One row per thing that can fail. The configuration is organised around
IOCs — software — but an IOC drives eight ion pumps and it is a pump that
trips, so the device is the row and the IOC is a field on it.

Everything here is read, never inferred beyond what the configuration and
the ibek templates state. Where a reading is uncertain the field is empty
and `needs` names what a person has to supply, because a half-filled row
somebody can finish is worth more than a full row somebody has to audit.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml

from .catalogue import classify, load_templates
from .elements import element_of

# The same four spellings of "where this is" the configuration uses.
ADDRESS_FIELDS = ("server", "host", "ip", "id")

SYSTEM_LABELS = {
    "mag": "Magnets", "vac": "Vacuum", "mot": "Motion", "cam": "Cameras",
    "diag": "Diagnostics", "bpm": "Diagnostics", "rf": "RF", "cool": "Cooling",
    "io": "I/O", "timing": "Timing", "modulator": "RF",
}

# Structured blocks that describe the hardware rather than the deployment:
# the ps: block is documented in ibek-templates/ps-schema.yaml, motor: is
# its older equivalent. These are what a device model is made of.
MODEL_BLOCKS = ("ps", "motor")


def _is_network_address(value: Any) -> bool:
    """`id: 192.168.189.79` is where a camera is; `id: 5` is which unit on
    a serial bus a supply is. Only one of them is an address."""
    if value in (None, ""):
        return False
    text = str(value).strip()
    return bool(text) and not text.isdigit() and any(
        c.isalpha() or c == "." for c in text
    )


def _ioc_entries(iocs: Any) -> list[dict]:
    """The IOCs as a list of dicts, whichever way the file spells them.

    `epicsConfiguration.iocs` was a list of `{name: ...}` entries and is now,
    in the beamline repositories that have moved on, a mapping keyed by the
    IOC's name. Both are in use at once, and reading one as the other yields
    no IOCs at all, silently. A mapping entry that leaves out `name` is
    called what its key is.
    """
    if isinstance(iocs, dict):
        out = []
        for key, entry in iocs.items():
            if not isinstance(entry, dict):
                continue
            out.append(entry if entry.get("name") else {**entry, "name": key})
        return out
    if isinstance(iocs, list):
        return [entry for entry in iocs if isinstance(entry, dict)]
    return []


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _params(entry: dict) -> dict:
    return {
        str(item["name"]): item.get("value")
        for item in entry.get("iocparam") or []
        if isinstance(item, dict) and item.get("name") is not None
    }


def _merge_model(ioc: dict, device: dict) -> dict:
    """The hardware's rating, field by field.

    ps-schema.yaml is explicit that a device overrides an IOC's block
    field-by-field and not block-by-block: a supply may differ in polarity
    while sharing the line's current limit.
    """
    merged: dict[str, Any] = {}
    for block in MODEL_BLOCKS:
        base = ioc.get(block) if isinstance(ioc.get(block), dict) else {}
        own = device.get(block) if isinstance(device.get(block), dict) else {}
        if not base and not own:
            continue
        combined = {**base}
        for key, value in own.items():
            if isinstance(value, dict) and isinstance(combined.get(key), dict):
                combined[key] = {**combined[key], **value}
            else:
                combined[key] = value
        merged[block] = combined
    return merged


@dataclass
class Device:
    beamline: str = ""
    ioc: str = ""
    name: str = ""
    key: str = ""
    pv: Optional[str] = None

    device_class: str = ""
    vendor: Optional[str] = None
    model: Optional[str] = None
    category: str = ""
    classified_from: str = "unknown"

    element: Optional[str] = None
    element_read_from: Optional[str] = None

    system: Optional[str] = None
    function: Optional[str] = None
    zones: list[str] = field(default_factory=list)

    connection: dict = field(default_factory=dict)
    model_spec: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)

    # Filled in by a person, or proposed by `match`. Never invented here.
    physical_asset: Optional[str] = None
    model_asset: Optional[str] = None
    needs: list[str] = field(default_factory=list)
    source: str = ""

    # An IOC that lists no devices is the only handle on what it drives, so it is
    # the row. `push` writes it as an IOC, not as a device with the IOC's name.
    ioc_only: bool = False

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _pv(ioc: dict, device_name: Optional[str]) -> Optional[str]:
    parts = [str(ioc.get("iocprefix") or "").strip(": ")]
    root = str(ioc.get("iocroot") or "").strip(": ")
    if root:
        parts.append(root)
    if device_name:
        parts.append(str(device_name).strip())
    return ":".join(p for p in parts if p) or None


# Which field the address came from says what the address *is*. `ip` and
# `id` are the hardware's own place on the network; `server` is something
# it is reached through, whether written on the IOC or on the device (the
# SMC chillers put one Moxa on each device); `host` is a machine the IOC
# itself runs on, which is how the Libera BPMs work.
VIA_BY_FIELD = {
    "ip": "direct",
    "id": "direct",
    "server": "terminal server",
    "host": "instrument",
}


def _connection(ioc: dict, device: dict, params: dict) -> dict:
    """How this device is reached, and through what."""
    address = via = None
    for source in (device, params, ioc):
        for field_name in ADDRESS_FIELDS:
            value = source.get(field_name)
            if _is_network_address(value):
                address, via = str(value).strip(), VIA_BY_FIELD[field_name]
                break
        if address:
            break

    out: dict[str, Any] = {}
    if address:
        out["host"] = address
        out["via"] = via
    port = device.get("port") or params.get("port") or ioc.get("port")
    if port not in (None, ""):
        out["port"] = str(port).strip()
    for key, source_key in (("channel", "channel"), ("axis", "axid"),
                            ("bus_id", "id"), ("bus_address", "addr")):
        value = device.get(source_key)
        if value not in (None, "") and not _is_network_address(value):
            out[key] = value
    return out


def _settings(device: dict) -> dict:
    skip = {"name", "devices", "iocinit", "iocparam", "zones", "asset", "poi",
            "channel", "axid", "addr", "port", *ADDRESS_FIELDS, *MODEL_BLOCKS}
    out = {
        k: v for k, v in device.items()
        if k not in skip and isinstance(v, (str, int, float, bool, type(None)))
    }
    for item in device.get("iocinit") or []:
        if isinstance(item, dict) and item.get("name") is not None:
            out[f"init:{item['name']}"] = item.get("value")
    return out


def scan(values: dict, templates: Optional[dict] = None,
         source: str = "") -> list[Device]:
    """Every device one beamline's configuration drives."""
    templates = templates if templates is not None else {}
    beamline = str(values.get("beamline") or "").strip() or "unknown"
    tag = beamline.upper()
    defaults = values.get("iocDefaults") or {}
    iocs = _ioc_entries((values.get("epicsConfiguration") or {}).get("iocs"))

    devices: list[Device] = []
    for entry in iocs:
        if not entry.get("name"):
            continue
        merged = {**(defaults.get(entry.get("template")) or {}), **entry}
        params = _params(merged)
        ioc_name = str(entry["name"]).strip()

        listed = [d for d in (merged.get("devices") or []) if isinstance(d, dict) and d.get("name")]
        # An IOC with no device list still drives one thing; the IOC is the
        # only handle anybody has on it, so it becomes the row.
        for device in listed or [{"name": ioc_name, "_from_ioc": True}]:
            device_name = str(device["name"]).strip()
            kind = classify(
                merged.get("template"),
                device.get("devtype") or merged.get("devtype"),
                merged.get("devfunc"),
                templates,
            )
            element = element_of(device_name)
            record = Device(
                beamline=tag,
                ioc=ioc_name,
                name=device_name,
                key=f"{tag}:{ioc_name}:{device_name}",
                ioc_only=bool(device.get("_from_ioc")),
                pv=_pv(merged, None if device.get("_from_ioc") else device_name),
                device_class=kind.device_class,
                vendor=kind.vendor,
                model=kind.model,
                category=kind.category,
                classified_from=kind.source,
                element=element.kind if element else None,
                element_read_from=element.matched_on if element else None,
                system=SYSTEM_LABELS.get(str(merged.get("devgroup") or ""),
                                         merged.get("devgroup")),
                function=merged.get("devfunc"),
                zones=_as_list(device.get("zones")) or _as_list(merged.get("zones")),
                connection=_connection(merged, device, params),
                model_spec=_merge_model(merged, device),
                settings=_settings(device),
                source=source,
            )
            needs = []
            if not record.device_class:
                needs.append("device class — no ibek template matched")
            if not record.model:
                needs.append("model")
            if not record.element:
                needs.append("element it serves")
            if not (merged.get("asset") or device.get("asset")):
                needs.append("link to the physical asset")
            record.needs = needs
            devices.append(record)
    return devices


def scan_file(path: str, templates: Optional[dict] = None) -> list[Device]:
    with open(path) as handle:
        values = yaml.safe_load(handle)
    if not isinstance(values, dict):
        raise ValueError(f"{path} did not parse as a mapping — is that the right file?")
    return scan(values, templates, source=path)
