"""Proposing which physical asset a control device is.

Proposing, not deciding. The inventory and the control configuration were
written by different people for different reasons, and the places they
agree — an address, a name, a serial — are evidence rather than proof. So
every match comes back with what it was matched on, and a device with two
plausible answers gets neither.
"""
import re
from typing import Iterable, Optional

IPV4 = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
LOCAL_DOMAINS = (".lnf.infn.it", ".infn.it")

# Objects that record an address rather than own one.
ADDRESS_RECORD_TYPES = {"dhcp nodes", "registered nodes", "ethernet configuration"}

IP_KEYS = {"ip", "ip_address", "indirizzo_ip", "local_ip"}
HOST_KEYS = {"hostname", "host", "fqdn"}


def short_host(value: str) -> str:
    name = (value or "").strip().lower().rstrip(".")
    for domain in LOCAL_DOMAINS:
        if name.endswith(domain):
            return name[: -len(domain)]
    return name


def _values(attributes: dict, names: set) -> Iterable[str]:
    for key, value in (attributes or {}).items():
        if key.strip().lower() not in names:
            continue
        for item in value if isinstance(value, list) else [value]:
            text = str(item).strip()
            if text:
                yield text


class Inventory:
    """The hub's objects, indexed by every handle a configuration might use."""

    def __init__(self, assets: list[dict]):
        self.by_host: dict[str, list[dict]] = {}
        self.by_ip: dict[str, list[dict]] = {}
        self.by_name: dict[str, list[dict]] = {}
        self.assets = assets

        for asset in assets:
            attributes = asset.get("attributes") or {}
            name = str(asset.get("name") or "").strip()
            if name:
                self.by_name.setdefault(name.upper(), []).append(asset)
                if not IPV4.match(name):
                    self.by_host.setdefault(short_host(name), []).append(asset)
            for value in _values(attributes, HOST_KEYS):
                self.by_host.setdefault(short_host(value), []).append(asset)
            for value in _values(attributes, IP_KEYS):
                if IPV4.match(value):
                    self.by_ip.setdefault(value, []).append(asset)
            if IPV4.match(name):
                self.by_ip.setdefault(name, []).append(asset)

    @staticmethod
    def _pick(candidates: list[dict]) -> tuple[Optional[dict], list[str]]:
        unique = {a["uid"]: a for a in candidates}
        equipment = [
            a for a in unique.values()
            if str(a.get("type") or "").strip().lower() not in ADDRESS_RECORD_TYPES
        ]
        pool = equipment or list(unique.values())
        if len(pool) == 1:
            return pool[0], []
        if len(pool) > 1:
            return None, [f"{a.get('key')} ({a.get('type')})" for a in pool[:5]]
        return None, []

    def for_device(self, device: dict) -> dict:
        """What this device might be, and on what evidence.

        The device's own name is tried before its address: two pumps behind
        one terminal server share an address and are not the same pump.
        """
        name = str(device.get("name") or "").strip().upper()
        if name and name in self.by_name:
            asset, ambiguous = self._pick(self.by_name[name])
            if asset:
                return {"uid": asset["uid"], "key": asset.get("key"),
                        "name": asset.get("name"), "type": asset.get("type"),
                        "matched_on": "name"}
            if ambiguous:
                return {"ambiguous": ambiguous, "matched_on": "name"}

        host = (device.get("connection") or {}).get("host")
        # Only where the device is addressed directly. A terminal server is
        # shared, so matching on it would say every pump behind it is the
        # same box.
        if host and (device.get("connection") or {}).get("via") == "direct":
            pool = self.by_ip.get(host.strip()) if IPV4.match(host.strip()) \
                else self.by_host.get(short_host(host))
            asset, ambiguous = self._pick(pool or [])
            if asset:
                return {"uid": asset["uid"], "key": asset.get("key"),
                        "name": asset.get("name"), "type": asset.get("type"),
                        "matched_on": "address"}
            if ambiguous:
                return {"ambiguous": ambiguous, "matched_on": "address"}
        return {}
