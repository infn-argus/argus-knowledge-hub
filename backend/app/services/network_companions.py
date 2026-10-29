"""A new record's network port and address, made with it.

A unit's MAC address is not one of its own fields: it identifies one network interface, so it belongs to the unit's
Equipment Port (`port of` the unit), and a registered address (IP, hostname) to an Address Record the unit is
`described by` — as imports already do (record_mapping.COMPANIONS). When someone creates a record, the port is
offered where it makes sense: proposed (and ticked) when a MAC was read from the nameplate or the description,
offered (unticked) for the kinds of equipment that are on a network, and not offered otherwise.
"""
from __future__ import annotations

import ipaddress
import re
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.schema import Schema

PORT_TYPE, ADDRESS_TYPE = "Equipment Port", "Address Record"
PORT_VERB, ADDRESS_VERB = "port of", "described by"
# Kinds of equipment that are usually on a network, by their place in the type tree (any type below one of
# these), and by their fields (a MAC of their own, or an Ethernet-like interface choice).
NETWORKED_LINEAGE = {"IT Equipment", "Network Device", "Computing Node", "Camera", "PLC", "Digitizer",
                     "Motion Controller", "Timing Module", "Electronics Crate", "I/O Module", "Low-Level RF Unit",
                     "Vacuum Controller", "Access Controller"}
NETWORKY_CHOICES = {"ethernet", "gige", "modbus_tcp", "ethercat", "gige_vision"}
# What a port may be made with besides its label, kind and MAC: a serial port's settings, its role and socket.
PORT_FIELDS = ("link_speed", "port_role", "tcp_port", "operating_mode", "baud", "framing", "flow_control",
               "port_settings")
SERIAL_KINDS = {"rs-232": "RS-232", "rs232": "RS-232", "rs-422": "RS-422", "rs422": "RS-422",
                "rs-485": "RS-485-2w", "rs485": "RS-485-2w", "rs-485-2w": "RS-485-2w", "rs-485-4w": "RS-485-4w"}
HOSTNAME = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$",
                      re.I)


class CompanionError(ValueError):
    pass


def normalise_mac(value) -> Optional[str]:
    """A MAC address in any of the usual spellings, as aa:bb:cc:dd:ee:ff (upper case), or None."""
    if not isinstance(value, str):
        return None
    hexes = re.sub(r"[^0-9a-fA-F]", "", value)
    if len(hexes) != 12 or not re.fullmatch(r"[\s0-9a-fA-F:.\-]+", value.strip()):
        return None
    if hexes in ("000000000000", "FFFFFFFFFFFF", "ffffffffffff"):
        return None
    return ":".join(hexes[i:i + 2] for i in range(0, 12, 2)).upper()


def normalise_ip(value) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        return None


def normalise_hostname(value) -> Optional[str]:
    v = str(value or "").strip().rstrip(".")
    return v.lower() if v and HOSTNAME.match(v) and not normalise_ip(v) else None


def _lineage(db: Session, schema: Optional[Schema]) -> list[Schema]:
    out, seen = [], set()
    while schema is not None and schema.uid not in seen:
        seen.add(schema.uid)
        out.append(schema)
        schema = db.get(Schema, schema.parent_schema_uid) if schema.parent_schema_uid else None
    return out


def networked(db: Session, schema: Optional[Schema]) -> bool:
    """Whether records of this type usually have a network port of their own."""
    if schema is None or schema.applies_to not in (None, "objects"):
        return False
    lineage = _lineage(db, schema)
    names = {s.name for s in lineage}
    if names & NETWORKED_LINEAGE:
        return True
    if PORT_TYPE in names or ADDRESS_TYPE in names:
        return False
    from app.services.attribute_validation import effective_attributes
    for a in effective_attributes(db, schema):
        key = a.get("key") or a.get("name")
        if key == "mac":
            return True
        if key == "interface" and a.get("type") == "enumeration":
            ids = {str(o.get("id", "")).lower() for o in a.get("options") or []}
            if ids & NETWORKY_CHOICES:
                return True
    return False


def types(db: Session, workspace_id: str) -> dict[str, Optional[str]]:
    """The port and address types this workspace can use (its own, or its catalogue's)."""
    from app.services.asset_types import resolve_type_uids
    usable = resolve_type_uids(db, workspace_id)
    return {"port": usable.get(PORT_TYPE), "address": usable.get(ADDRESS_TYPE)}


def ports_of(db: Session, owner_uid: str) -> list[Asset]:
    """The unit's recorded ports (each `port of` it)."""
    from app.models.asset import Relation
    q = (select(Asset).join(Relation, Relation.from_asset_uid == Asset.uid)
         .where(Relation.to_asset_uid == owner_uid, Relation.relation_type == PORT_VERB, Asset.deleted_at.is_(None)))
    return list(db.scalars(q))


def addresses_of(db: Session, owner_uid: str) -> list[Asset]:
    """The addresses the unit is `described by`."""
    from app.models.asset import Relation
    q = (select(Asset).join(Relation, Relation.to_asset_uid == Asset.uid)
         .where(Relation.from_asset_uid == owner_uid, Relation.relation_type == ADDRESS_VERB,
                Asset.type == ADDRESS_TYPE, Asset.deleted_at.is_(None)))
    return list(db.scalars(q))


def port_with_mac(db: Session, mac: str) -> Optional[Asset]:
    """A port already recorded with this MAC (anywhere: a MAC is one interface in the world)."""
    for a in db.scalars(select(Asset).where(Asset.attributes["mac"].astext.isnot(None), Asset.deleted_at.is_(None),
                                            Asset.type == PORT_TYPE)):
        if normalise_mac(a.attributes.get("mac")) == mac:
            return a
    return None


def offer(db: Session, workspace_id: str, schema: Optional[Schema]) -> dict:
    """What the form offers for a record of this type: a network port, and whether it can be made here."""
    t = types(db, workspace_id)
    return {"offered": bool(t["port"]) and networked(db, schema), "port_type_uid": t["port"],
            "address_type_uid": t["address"]}


def create(db: Session, workspace_id: str, actor: str, owner: Asset, ports: list[dict],
           addresses: list[dict], reason: str = "of a new record") -> dict:
    """The ports and addresses, made with the record (through the ledger, in the caller's transaction):
    each port `port of` the record, the record `described by` each address."""
    from app.ledger import service as ledger
    from app.services import asset_keys
    t = types(db, workspace_id)
    made = {"ports": [], "addresses": []}
    if ports and not t["port"]:
        raise CompanionError("this workspace has no Equipment Port type (core-objects)")
    if addresses and not t["address"]:
        raise CompanionError("this workspace has no Address Record type (the it package)")
    for p in ports:
        mac = normalise_mac(p.get("mac")) if p.get("mac") else None
        if p.get("mac") and mac is None:
            raise CompanionError(f"{p.get('mac')!r} is not a MAC address (aa:bb:cc:dd:ee:ff)")
        if mac:
            other = port_with_mac(db, mac)
            if other is not None:
                raise CompanionError(f"the MAC {mac} is already on {other.key} ({other.name})")
        label = (p.get("port_label") or "eth0").strip()
        schema = db.get(Schema, t["port"])
        attrs = {"port_label": label, "port_kind": p.get("port_kind") or "RJ45"}
        if mac:
            attrs["mac"] = mac
        for k in PORT_FIELDS:
            if p.get(k) not in (None, ""):
                attrs[k] = p[k]
        from app.services.attribute_validation import check_attributes
        problems = check_attributes(db, schema, attrs, workspace_id, Asset)
        if problems:
            raise CompanionError(f"port {label}: {problems[0]}")
        uid = str(uuid.uuid4())
        port = ledger.create_record(db, workspace_id, actor, uid=uid, schema_uid=schema.uid,
                                    key=asset_keys.allocate(db, workspace_id, schema),
                                    name=f"{owner.name} · {label}", type_name=schema.name, attributes=attrs,
                                    is_global=owner.is_global)
        ledger.relate(db, workspace_id, actor, port.uid, PORT_VERB, owner.uid, reason=f"port {reason}")
        made["ports"].append({"uid": port.uid, "key": port.key, "name": port.name})
    for a in addresses:
        ip = normalise_ip(a.get("ip")) if a.get("ip") else None
        host = normalise_hostname(a.get("hostname")) if a.get("hostname") else None
        if a.get("ip") and ip is None:
            raise CompanionError(f"{a.get('ip')!r} is not an IP address")
        if a.get("hostname") and host is None:
            raise CompanionError(f"{a.get('hostname')!r} is not a hostname")
        if not ip and not host:
            continue
        schema = db.get(Schema, t["address"])
        attrs = {"record_kind": "Ethernet configuration", **({"ip": ip} if ip else {}), **({"hostname": host} if host else {})}
        uid = str(uuid.uuid4())
        rec = ledger.create_record(db, workspace_id, actor, uid=uid, schema_uid=schema.uid,
                                   key=asset_keys.allocate(db, workspace_id, schema),
                                   name=f"{owner.name} · {host or ip}", type_name=schema.name, attributes=attrs,
                                   is_global=owner.is_global)
        ledger.relate(db, workspace_id, actor, owner.uid, ADDRESS_VERB, rec.uid, reason=f"address {reason}")
        made["addresses"].append({"uid": rec.uid, "key": rec.key, "name": rec.name})
    return made
