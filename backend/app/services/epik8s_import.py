"""EPIK8s control configuration import.

A beamline's values.yaml is the only place that says how control software
reaches hardware: which IOC drives what, through which terminal server, on
which port. It deploys the accelerator, so nothing here writes back to it —
the hub mirrors it, stamped with the revision it came from.

What the import is for is the question the configuration answers and no
other record does. Thirty-one hosts in these files are shared: one Moxa
fronts ten turbo pumps, one address fronts seven magnet supplies. When it
fails, ten faults are filed and nothing connects them. That link is
mechanical — `server` plus `port` — and once it is an edge it is an answer.

Nine kinds of thing come out, of the types the object catalogue defines
(services/asset_types.py), and each is linked to what the file says it is
tied to:

  Facility               the beamline
  Control Configuration  this file, at this revision: what every object below is declared in
  IOC Template           the recipe an IOC is deployed from, named or not in iocDefaults
  IOC                    the deployable unit
  Control Device         the channel, axis or gauge that actually fails
  Access Point           what sits between EPICS and the metal
  Control Network        a network an IOC is attached to
  Control Service        archiver, gateways, alarm server, logbook
  Storage Mount          an NFS mount or backup target

With `infer_elements` the import also makes what the channels are *for*: the ion pump behind
`GUNSIP01`, the quadrupole and the power supply behind `QUATB002`, the camera, the BPM's
electronics, the LLRF and modulator units (services/element_inference.py says how each is read,
and what is deliberately left alone). Off by default: they are inferences, not statements in the
file, and every one says so and is easy to find (`argus_keywords: inferred`).

The types are found wherever the catalogue put them: this workspace's own, or a
shared one. Where the catalogue was never seeded, empty ones are made, as they
always were.

The device is first-class rather than the IOC, because "GUNSIP01 tripped"
is the sentence people actually write.
"""
import collections
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

import requests
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.asset import Asset, Relation
from app.models.import_job import ImportJob
from app.models.schema import Schema
from app.services.git_import import (
    _get_file_github,
    _get_file_gitlab,
    _parse_repo,
    github_api,
    gitlab_api,
)
from app.services.asset_types import resolve_type_uids
from app.services.element_inference import (
    ASSET_TYPES, CAMERA, ELEMENT_TYPES, LATTICE_NAME, SCREEN_NAME, infer_device, infer_ioc,
)
from app.services.network_resolve import IPV4, NetworkIndex, short_host
from app.services.relations import rebuild_asset_relations

SOURCE = "epik8s"

# The object types this import owns. Created on first run if they are not
# already there, and never touched afterwards — a type somebody has since
# given attributes to is theirs, not the importer's.
TYPES: dict[str, str] = {
    "Facility": "A beamline or accelerator facility deployed by EPIK8s.",
    "IOC": "An EPICS IOC: the deployable unit of control software.",
    "Control Device": "A channel, axis, gauge or supply an IOC drives — what fails.",
    "Access Point": "What control software reaches hardware through: a terminal "
                    "server, a converter, or the hardware's own network socket.",
    "Control Service": "A shared control service: archiver, gateway, alarm server, "
                       "logbook.",
    "Control Configuration": "One values.yaml at one git revision.",
    "IOC Template": "An iocDefaults entry: the recipe an IOC is deployed from.",
    "Control Network": "A named network and its address range.",
    "Storage Mount": "An NFS mount or backup target.",
}

# Where a device's settings end up. Everything else on a device row is a
# setpoint or a limit, kept as-is under `settings` so a change to one is
# visible without anybody having predicted which one mattered.
DEVICE_ADDRESS_KEYS = ("server", "ip", "id", "host", "addr", "port", "channel", "axid")

MAX_WARNINGS = 200


def _uid(workspace_id: str, key: str) -> str:
    """Deterministic, so a re-run updates a row instead of adding one."""
    digest = hashlib.sha1(f"{workspace_id}:{key}".encode()).hexdigest()[:24]
    return f"epik8s-{digest}"


def _note(job: ImportJob, db: Session, message: str) -> None:
    """A diagnostic that must never be the reason an import dies."""
    try:
        if len(job.warnings or []) < MAX_WARNINGS:
            job.warnings = list(job.warnings or []) + [message]
            db.commit()
    except Exception:
        db.rollback()


def _progress(db: Session, job: ImportJob, message: str, **counts) -> None:
    try:
        job.progress = message
        if counts:
            job.counts = {**(job.counts or {}), **counts}
        db.commit()
    except Exception:
        db.rollback()


def _ioc_entries(iocs: Any) -> list[dict]:
    """The IOCs as a list of dicts, whichever way the file spells them.

    `epicsConfiguration.iocs` was a list of `{name: ...}` entries and is now,
    in the beamline repositories that have moved on, a mapping keyed by the
    IOC's name. Both are in use at once, and reading one as the other yields
    no IOCs at all — with no error, since a string key simply fails the
    "is this a dict" check every entry has always had to pass. A mapping
    entry that leaves out `name` is called what its key is.
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


def _present(attributes: dict) -> dict:
    """What a configuration actually says: a key it leaves out is not a value of None."""
    return {k: v for k, v in attributes.items() if v not in (None, "", [], {})}


def _text(value: Any) -> Optional[str]:
    text = str(value).strip() if value is not None else ""
    return text or None


def _as_list(value: Any) -> list[str]:
    """`zones` is a string here and a list there, meaning the same thing."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def _params(entry: dict) -> dict[str, str]:
    """`iocparam: [{name: server, value: x}]` as a plain mapping."""
    out: dict[str, str] = {}
    for item in entry.get("iocparam") or []:
        if isinstance(item, dict) and item.get("name") is not None:
            out[str(item["name"])] = item.get("value")
    return out


def _is_network_address(value: Any) -> bool:
    """Whether this is somewhere on a network, or just a number.

    `id` means two things in these files. On a camera it is where the
    camera is — `id: 192.168.189.79`, `id: cceuapscam28.lnf.infn.it`. On an
    OCEM supply it is the unit's address on a serial bus — `id: 5` — and
    reading that as a host invents an Access Point called "5" that three
    unrelated magnets appear to share, which is worse than missing it.
    """
    if value in (None, ""):
        return False
    text = str(value).strip()
    if not text or text.isdigit():
        return False
    return bool(IPV4.match(text) or any(c.isalpha() for c in text))


def _endpoint_of(entry: dict, params: dict) -> tuple[Optional[str], Optional[str]]:
    """The address this IOC or device talks to, and the port on it.

    Four spellings for one idea, because the templates grew separately:
    `iocparam.server`, a bare `server`, `host` for an IOC that runs on the
    instrument itself, and `ip`/`id` for hardware addressed directly.
    """
    address = next(
        (
            candidate
            for candidate in (
                params.get("server"), entry.get("server"), entry.get("host"),
                entry.get("ip"), entry.get("id"),
            )
            if _is_network_address(candidate)
        ),
        None,
    )
    port = params.get("port") or entry.get("port")
    address = str(address).strip() if address not in (None, "") else None
    port = str(port).strip() if port not in (None, "") else None
    return address, port


def _pv_prefix(ioc: dict, device_name: Optional[str]) -> Optional[str]:
    """`SPARC:VAC` + `GUNVPC` + `GUNSIP01` -> `SPARC:VAC:GUNVPC:GUNSIP01`.

    The join key to the archiver, the alarm server and the logbook, so it
    is composed the same way the IOC chart composes it.
    """
    parts = [str(ioc.get("iocprefix") or "").strip(":").strip()]
    root = str(ioc.get("iocroot") or "").strip(":").strip()
    if root:
        parts.append(root)
    if device_name:
        parts.append(str(device_name).strip())
    parts = [p for p in parts if p]
    return ":".join(parts) or None


def _settings(entry: dict) -> dict:
    """Whatever a device carries beyond its identity and its address.

    Kept rather than curated: `tsh`, `dhlm`, `velo`, `TEMP_SETPT_SP` are
    the numbers a fault report turns out to be about, and which of them
    matters is not knowable in advance.
    """
    skip = {"name", "devices", "iocinit", "iocparam", "zones", "asset", "poi", *DEVICE_ADDRESS_KEYS}
    out = {}
    for key, value in entry.items():
        if key in skip:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
    for item in entry.get("iocinit") or []:
        if isinstance(item, dict) and item.get("name") is not None:
            out[f"init:{item['name']}"] = item.get("value")
    return out


class _Importer:
    def __init__(self, db: Session, job: ImportJob, workspace_id: str, source_ref: str,
                 infer_elements: bool = False):
        self.db = db
        self.infer = infer_elements
        self.job = job
        self.workspace_id = workspace_id
        self.source_ref = source_ref
        self.schemas: dict[str, Schema] = {}
        self.index = NetworkIndex(db, workspace_id)
        # Set as the walk goes: what everything below is declared in, and the
        # things several IOCs share, made once.
        self.tag = ""
        self.cfg: Optional[Asset] = None
        self.templates: dict[str, Asset] = {}
        self.networks: dict[str, Asset] = {}
        self.mounts: dict[tuple, Asset] = {}
        # What the inference had no rule for, by "devgroup/template": said, not guessed at.
        self.not_inferred: collections.Counter = collections.Counter()
        self._inferred: set = set()
        # The cameras inferred, by channel name, for the screens that are read with them.
        self._cameras: dict = {}
        # Chillers that cool every asset of a type, and the timing units, wired once all are made.
        self._acted_on: dict = {}          # control device uid -> the asset it acts on
        self._cooling: list = []
        self._timing: list = []
        # RF conditioning IOCs and the readbacks that gate them: (IOC asset, tag, entries).
        self._gates: list = []
        self.counts = {
            "facilities": 0, "iocs": 0, "devices": 0, "services": 0,
            "configurations": 0, "templates": 0, "networks": 0, "mounts": 0,
            "inferred_assets": 0, "inferred_elements": 0, "screens_paired": 0, "gates": 0, "gates_unresolved": 0,
            # Three different things, because conflating them makes the
            # report say the opposite of the truth: an import that matched
            # nothing at all read as "42 matched to existing equipment",
            # which were its own Access Points being reached a second time.
            "access_points_linked": 0,    # equipment the inventory already held
            "access_points_created": 0,   # made here, awaiting confirmation
            "access_points_reused": 0,    # created earlier in this same run
            "addresses_unresolved": 0,
            "relations": 0,
        }
        # What this run created, so re-reaching one is not counted as a match.
        self.created_access_points: set[str] = set()
        # key -> asset, for relating without re-querying.
        self.assets: dict[str, Asset] = {}
        self.pv_index: dict[str, Asset] = {}

    # --- types ----------------------------------------------------------

    def ensure_types(self) -> None:
        """Each type this import writes, found where the catalogue put it (this
        workspace's own, or a shared one), or made empty if nobody has one."""
        usable = resolve_type_uids(self.db, self.workspace_id)
        if self.infer:
            missing = [n for n in (*ASSET_TYPES, *ELEMENT_TYPES) if n not in usable]
            if missing:
                raise ValueError(
                    f"Inferring elements writes objects of the catalogue's types, and this "
                    f"workspace cannot use {len(missing)} of them (e.g. {', '.join(missing[:4])}). "
                    f"Seed the catalogue first: scripts/seed_asset_types.py.")
        for name, description in TYPES.items():
            schema = self.db.get(Schema, usable[name]) if name in usable else None
            if schema is None:
                schema = Schema(
                    uid=_uid(self.workspace_id, f"type:{name}"),
                    workspace_id=self.workspace_id,
                    name=name,
                    description=description,
                    applies_to="objects",
                    metadata_json={"source": SOURCE},
                )
                self.db.add(schema)
                self.db.flush()
            self.schemas[name] = schema
        if self.infer:
            for name in (*ASSET_TYPES, *ELEMENT_TYPES):
                self.schemas[name] = self.db.get(Schema, usable[name])
        self.db.commit()

    # --- objects --------------------------------------------------------

    def upsert(self, type_name: str, key: str, name: str, attributes: dict) -> Asset:
        uid = _uid(self.workspace_id, key)
        asset = self.db.get(Asset, uid)
        if asset is None:
            # Object keys are unique across the installation, and these are
            # derived from the beamline, so importing one beamline into two
            # workspaces collides. That is a mistake worth naming: as a
            # constraint violation halfway through it tells an operator
            # nothing about what to do.
            clash = self.db.scalar(select(Asset).where(Asset.key == key))
            if clash is not None:
                raise ValueError(
                    f"“{key}” already exists in workspace “{clash.workspace_id}”. "
                    f"This beamline's configuration is already imported there; import "
                    f"it once, into the workspace that owns the beamline."
                )
        stamped = {
            **attributes,
            # The same key tickets and documents use, so "everything about SPARC"
            # is one filter across all three.
            **({"argus_facility": self.tag} if self.tag else {}),
            "argus_source": SOURCE,
            "argus_source_ref": self.source_ref,
        }
        if asset is None:
            asset = Asset(
                uid=uid,
                workspace_id=self.workspace_id,
                schema_uid=self.schemas[type_name].uid,
                key=key,
                name=name,
                type=type_name,
                attributes=stamped,
            )
            self.db.add(asset)
        else:
            asset.name = name
            asset.type = type_name
            asset.schema_uid = self.schemas[type_name].uid
            asset.attributes = stamped
        self.db.flush()
        self.assets[key] = asset
        return asset

    def upsert_inferred(self, type_name: str, key: str, name: str, attributes: dict) -> Asset:
        """An object the configuration implies rather than states. A person's word outranks a
        guess: what is already on it stays, and inference only fills what is missing, so a
        serial number or a location entered by hand survives every later read."""
        uid = _uid(self.workspace_id, key)
        asset = self.db.get(Asset, uid)
        provenance = {"argus_facility": self.tag, "argus_source": SOURCE,
                      "argus_source_ref": self.source_ref}
        if asset is None:
            clash = self.db.scalar(select(Asset).where(Asset.key == key))
            if clash is not None:
                raise ValueError(
                    f"“{key}” already exists in workspace “{clash.workspace_id}”. Object keys "
                    f"are unique across the installation.")
            asset = Asset(uid=uid, workspace_id=self.workspace_id,
                          schema_uid=self.schemas[type_name].uid, key=key, name=name,
                          type=type_name, attributes={**attributes, **provenance})
            self.db.add(asset)
        else:
            asset.attributes = {**attributes, **(asset.attributes or {}), **provenance}
        self.db.flush()
        self.assets[key] = asset
        return asset

    def _infer_from(self, inference, control: Asset, relation: str, key_stem: str,
                    label: str, source: dict, zones: list) -> Optional[Asset]:
        """The asset a channel or an IOC drives, and the lattice element it serves. Returns
        the asset, which a unit's own channels then hang from."""
        note = (f"Inferred by the control-configuration import: {inference.why}. Nobody has "
                f"confirmed what this is, its serial number or where it is installed.")
        url = source.get("asset")
        asset = self.upsert_inferred(
            inference.asset_type, f"{self.tag}:AST:{key_stem}", f"{label} {inference.asset_type}",
            _present({**inference.asset_attrs, "description": note, "argus_keywords": ["inferred"],
                      "inventory_url": url if isinstance(url, str) and url.startswith("http") else None}))
        self.relate(control, asset, relation)
        self._acted_on[control.uid] = asset
        if inference.asset_type == CAMERA:
            self._cameras[label.upper()] = asset
        if inference.cools_type:
            self._cooling.append((asset, inference.cools_type))
        if inference.timing_role:
            self._timing.append((asset, inference.timing_role, inference.triggers_type))
        self._count_inferred("inferred_assets", f"inferred {inference.asset_type}", asset.key)
        if inference.element_type:
            element = self.upsert_inferred(
                inference.element_type, f"{self.tag}:ELM:{inference.element_name}",
                inference.element_name,
                _present({**inference.element_attrs, "argus_beamline": self.tag, "zone": zones,
                          "description": note, "argus_keywords": ["inferred"]}))
            # A supply powers its magnet and a chiller cools its structure; the electronics of a BPM
            # are what realises it; a screen station or a mirror mount is assembled from its
            # actuator or axes.
            if inference.asset_to_element:
                self.relate(asset, element, inference.element_link)
            else:
                self.relate(element, asset, inference.element_link)
            self._count_inferred("inferred_elements", f"inferred {inference.element_type}", element.key)
        return asset

    def _infer_channel_element(self, element_type: str, control: Asset, unit: Asset,
                               name: str, zones: list, why: str) -> None:
        """One channel of a unit whose channels are each an element: a Libera Spectra's BPMs."""
        note = (f"Inferred by the control-configuration import: {why}. Nobody has confirmed "
                f"what this is or where it is installed.")
        upper = name.upper()
        element = self.upsert_inferred(
            element_type, f"{self.tag}:ELM:{upper}", upper,
            _present({"lattice_name": upper if LATTICE_NAME.match(upper) else None,
                      "argus_beamline": self.tag, "zone": zones, "description": note,
                      "argus_keywords": ["inferred"]}))
        self.relate(control, element, "acts on")
        self.relate(element, unit, "realized by")
        self._count_inferred("inferred_elements", f"inferred {element_type}", element.key)

    def _wire_plant(self, tag: str) -> None:
        """What the plant feeds, from what the configuration names.

        A chiller whose channel is `MOD` cools every modulator; a timing receiver is timed by the
        beamline's event generator (when there is exactly one, since with two nothing says which);
        and one whose name says `LLRF` or `CAM` triggers those. Every object on these links is an
        inference, so the links are too."""
        own = [a for k, a in self.assets.items() if k.startswith(f"{tag}:AST:")]
        for chiller, kind in self._cooling:
            for asset in own:
                if asset.type == kind:
                    self.relate(chiller, asset, "cools")
        generators = [a for a, role, _ in self._timing if role == "generator"]
        for receiver, role, kind in self._timing:
            if role != "receiver":
                continue
            if len(generators) == 1:
                self.relate(receiver, generators[0], "timed by")
            for asset in own:
                if kind and asset.type == kind:
                    self.relate(receiver, asset, "triggers")

    def _gating(self, tag: str) -> None:
        """An RF conditioning IOC lists the pumps and gauges whose pressure it watches, and the level
        above which it will not raise power. That is the file saying, in as many words, that RF depends
        on vacuum: the IOC is `enabled by` each of them. With inference on, the pump or gauge itself is
        linked too, so a pump that fails reaches the permit as well as one whose readout is lost."""
        for ioc, entries in self._gates:
            conditions = []
            for entry in entries:
                if not isinstance(entry, dict) or not entry.get("name"):
                    continue
                pv = f"{entry.get('prefix') or ''}{entry['name']}"
                device = self.pv_index.get(pv)
                if device is None:
                    self.counts["gates_unresolved"] += 1
                    continue
                self.relate(ioc, device, "enabled by")
                asset = self._acted_on.get(device.uid)
                if asset is not None:
                    self.relate(ioc, asset, "enabled by")
                limit = entry.get("tsh")
                conditions.append(f"{pv}{entry.get('suffix') or ''} < {limit}" if limit not in (None, "")
                                  else f"{pv}{entry.get('suffix') or ''}")
                self.counts["gates"] += 1
            if conditions:
                ioc.attributes = {**(ioc.attributes or {}), "permit_conditions": conditions}
        self.db.flush()

    def _pair_screens(self, tag: str) -> None:
        """A screen station is a flag, a camera and the optics between them, and the file lists
        the flag and the camera on two IOCs with nothing joining them. The names do: `AC1FLG01`
        and `AC101`, `UTLFLG02` and `UTL02`, `FELFLG03A` and `FEL03` (both flags of a pair
        share their camera). Where the camera exists, the station is composed of it; where it
        does not (`GUNFLG01`), nothing is guessed."""
        for key, station in list(self.assets.items()):
            if station.type != "Screen Station" or not key.startswith(f"{tag}:ELM:"):
                continue
            named = SCREEN_NAME.match(key.rsplit(":", 1)[-1])
            camera = self._cameras.get(f"{named['section']}{named['n']}") if named else None
            if camera is not None:
                self.relate(station, camera, "composed of")
                self.counts["screens_paired"] += 1

    def _count_inferred(self, total: str, kind: str, key: str) -> None:
        if key in self._inferred:
            return
        self._inferred.add(key)
        self.counts[total] += 1
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def relate(self, source: Asset, target: Asset, relation_type: str) -> None:
        if source is None or target is None or source.uid == target.uid:
            return
        exists = self.db.scalar(
            select(Relation).where(
                Relation.workspace_id == self.workspace_id,
                Relation.from_asset_uid == source.uid,
                Relation.to_asset_uid == target.uid,
                Relation.relation_type == relation_type,
            )
        )
        if exists is not None:
            return
        self.db.add(Relation(
            workspace_id=self.workspace_id,
            from_asset_uid=source.uid,
            to_asset_uid=target.uid,
            relation_type=relation_type,
        ))
        self.counts["relations"] += 1

    # --- the address question -------------------------------------------

    def access_point(self, address: str, beamline: str, create_missing: bool) -> Optional[Asset]:
        """The equipment at this address: found in the inventory, or made.

        Found is the point. The Moxa is already an object with a purchase
        order and a location; a second one invented here would split the
        history of the same box in two.
        """
        match = self.index.resolve(address)
        if match.found:
            if match.asset.uid in self.created_access_points:
                self.counts["access_points_reused"] += 1
            else:
                self.counts["access_points_linked"] += 1
            return match.asset

        if match.ambiguous:
            self.counts["addresses_unresolved"] += 1
            _note(self.job, self.db,
                  f"{address}: more than one object carries this address "
                  f"({', '.join(match.ambiguous[:4])}) — not linked, because guessing "
                  f"which would put a wrong edge in the graph")
            return None

        if not create_missing:
            self.counts["addresses_unresolved"] += 1
            _note(self.job, self.db,
                  f"{address}: nothing in this workspace has this address")
            return None

        # Keyed per workspace, unlike everything else here. A beamline's own
        # objects carry names that mean one thing across INFN, but a shared
        # terminal server is legitimately recorded by more than one workspace,
        # and each record is that workspace's to confirm and to own. The key
        # is fixed rather than chosen on collision, so a re-run finds the row
        # it made last time instead of making another.
        key = f"NET:{self.workspace_id}:{short_host(address).upper()}"
        attributes: dict[str, Any] = {"address": address, "beamline": beamline}
        if IPV4.match(address.strip()):
            attributes["ip"] = address.strip()
        else:
            attributes["hostname"] = short_host(address)
            attributes["fqdn"] = address.strip()
        # Said plainly on the object: it exists because a configuration
        # referred to it, and nobody has confirmed what it is.
        attributes["argus_provenance"] = (
            "Created by the control-configuration import: the configuration reaches "
            "hardware at this address and no object in the inventory carries it. "
            "Confirm what this is and link it to the real equipment."
        )
        asset = self.upsert("Access Point", key, short_host(address), attributes)
        self.index.add(asset, address)
        self.created_access_points.add(asset.uid)
        self.counts["access_points_created"] += 1
        return asset

    # --- the walk -------------------------------------------------------

    def run(self, values: dict, create_missing: bool) -> None:
        beamline = str(values.get("beamline") or "").strip() or "unknown"
        tag = beamline.upper()
        self.tag = tag

        facility = self.upsert(
            "Facility", f"{tag}", beamline,
            {
                "beamline": beamline,
                "namespace": values.get("namespace"),
                "cluster": values.get("epik8namespace"),
                "git_url": values.get("giturl"),
                "git_revision": values.get("gitrev"),
            },
        )
        self.counts["facilities"] += 1

        defaults = values.get("iocDefaults") or {}
        epics = values.get("epicsConfiguration") or {}
        ioc_entries = _ioc_entries(epics.get("iocs"))

        self._configuration(values, epics, beamline, tag, facility)
        self._templates(defaults, ioc_entries, tag)
        self._mounts(values, tag, facility)
        self._services(epics.get("services") or {}, facility, tag)
        self._iocs(ioc_entries, defaults, facility, tag, beamline, create_missing)
        if self.infer:
            self._pair_screens(tag)
            self._wire_plant(tag)
        self._gating(tag)
        self._cross_references(tag)

        self.db.commit()

    # --- what the file is, and what it is made of --------------------------------

    def _configuration(self, values: dict, epics: dict, beamline: str, tag: str,
                       facility: Asset) -> None:
        """This file at this revision: the one thing every other object is declared
        in, so "what did the configuration say when this broke" has an answer."""
        max_bytes = epics.get("max_array_bytes")
        self.cfg = self.upsert(
            "Control Configuration", f"{tag}:CFG", f"{beamline} configuration",
            _present({
                "beamline": beamline,
                "git_url": values.get("giturl"),
                "git_revision": values.get("gitrev"),
                "config_path": self.source_ref.rsplit(":", 1)[-1],
                "namespace": values.get("namespace"),
                "cluster": values.get("epik8namespace"),
                "argocd_project": values.get("argocdProject"),
                "epics_address_list": _text(epics.get("address_list")),
                "max_array_bytes": int(max_bytes) if str(max_bytes or "").isdigit() else None,
                "base_ip": values.get("baseIp"),
                "ingress_class": values.get("ingressClassName"),
                "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }),
        )
        self.relate(self.cfg, facility, "configures")
        self.counts["configurations"] += 1

    def _templates(self, defaults: dict, ioc_entries: list, tag: str) -> None:
        """A template is a thing in its own right: ten IOCs deployed from one recipe
        share its fate. Named in iocDefaults, or only referred to by the IOCs that
        use it (the recipe then lives in the chart repository), it is one object."""
        names = list(defaults) + [
            str(e["template"]) for e in ioc_entries
            if e.get("template") and str(e["template"]) not in defaults
        ]
        for name in dict.fromkeys(names):
            body = defaults.get(name) if isinstance(defaults.get(name), dict) else {}
            self.templates[name] = self.upsert(
                "IOC Template", f"{tag}:TPL:{name}", name,
                _present({
                    "beamline": tag,
                    "template_name": name,
                    "chart_url": body.get("charturl"),
                    "image": body.get("image"),
                    "devgroup": body.get("devgroup"),
                    "devtype": body.get("devtype"),
                    "devfunc": body.get("devfunc"),
                    "opi": body.get("opi"),
                    "autosync": body.get("autosync") if isinstance(body.get("autosync"), bool) else None,
                    "pva": body.get("pva") if isinstance(body.get("pva"), bool) else None,
                    "inventory_url": body.get("asset") or None,
                }),
            )
            self.relate(self.templates[name], self.cfg, "declared in")
            self.counts["templates"] += 1

    def _mounts(self, values: dict, tag: str, facility: Asset) -> None:
        for backup, entries in ((False, values.get("nfsMounts")), (True, values.get("nfsBackups"))):
            for entry in entries if isinstance(entries, list) else []:
                self._mount(entry, tag, facility, backup)

    def _mount(self, entry: Any, tag: str, facility: Asset, backup: bool,
               owner: Optional[str] = None) -> Optional[Asset]:
        """One mount, made once however many things name it: the same server and
        path is the same storage."""
        if not isinstance(entry, dict) or not entry.get("name"):
            return None
        identity = (str(entry.get("server") or ""), str(entry.get("path") or ""))
        if identity[0] and identity in self.mounts:
            return self.mounts[identity]
        key = f"{tag}:MNT:{owner + ':' if owner else ''}{entry['name']}"
        mount = self.upsert(
            "Storage Mount", key, f"{entry['name']} ({tag})",
            _present({
                "beamline": tag,
                "mount_kind": "NFS",
                "server": entry.get("server"),
                "export_path": entry.get("path"),
                "mount_path": entry.get("mountPath"),
                "is_backup": backup,
            }),
        )
        self.relate(mount, facility, "part of")
        self.relate(mount, self.cfg, "declared in")
        if identity[0]:
            self.mounts[identity] = mount
        self.counts["mounts"] += 1
        return mount

    def _network(self, entry: Any, tag: str) -> Optional[Asset]:
        """`{name: control, annotation: sparc-magnets}`: the annotation is what tells
        two networks both called `control` apart."""
        if not isinstance(entry, dict) or not (entry.get("annotation") or entry.get("name")):
            return None
        identity = str(entry.get("annotation") or entry["name"])
        if identity not in self.networks:
            vlan = re.match(r"^vlan-(\d+)$", str(entry.get("name") or ""))
            self.networks[identity] = self.upsert(
                "Control Network", f"{tag}:NET:{identity}", identity,
                _present({
                    "beamline": tag,
                    "network_name": entry.get("name"),
                    "annotation": entry.get("annotation"),
                    "vlan": int(vlan.group(1)) if vlan else None,
                }),
            )
            self.relate(self.networks[identity], self.cfg, "declared in")
            self.counts["networks"] += 1
        return self.networks[identity]

    def _services(self, services: dict, facility: Asset, tag: str) -> None:
        for name, body in services.items():
            if not isinstance(body, dict):
                continue
            if body.get("disable") is True:
                continue
            service = self.upsert(
                "Control Service", f"{tag}:SVC:{name}", f"{name} ({tag})",
                {
                    "service": name,
                    "beamline": tag,
                    "description": body.get("desc") or body.get("asset"),
                    "chart_url": body.get("charturl"),
                    "loadbalancer_ip": body.get("loadbalancer"),
                    "ingress": bool(body.get("enable_ingress") or (body.get("ingress") or {}).get("enabled")),
                    "image": body.get("image") if isinstance(body.get("image"), str) else None,
                    "chart_revision": _text(body.get("targetRevision")),
                    "replicas": body.get("replicaCount") if isinstance(body.get("replicaCount"), int) else None,
                },
            )
            self.relate(service, facility, "deployed on")
            self.relate(service, self.cfg, "declared in")
            for entry in body.get("nfsMounts") if isinstance(body.get("nfsMounts"), list) else []:
                mount = self._mount(entry, tag, facility, False, owner=name)
                if mount is not None:
                    self.relate(service, mount, "mounts")
            self.counts["services"] += 1

    def _iocs(self, iocs: Any, defaults: dict, facility: Asset, tag: str,
              beamline: str, create_missing: bool) -> None:
        for entry in iocs if isinstance(iocs, list) else _ioc_entries(iocs):
            if not entry.get("name"):
                continue
            # A template supplies what the IOC leaves out; the IOC always wins.
            template = defaults.get(entry.get("template")) or {}
            merged = {**template, **entry}
            name = str(entry["name"]).strip()
            params = _params(merged)
            address, port = _endpoint_of(merged, params)

            ioc = self.upsert(
                "IOC", f"{tag}:IOC:{name}", name,
                {
                    "beamline": tag,
                    "iocprefix": merged.get("iocprefix"),
                    "iocroot": merged.get("iocroot"),
                    "pv_prefix": _pv_prefix(merged, None),
                    "template": merged.get("template"),
                    "devtype": merged.get("devtype"),
                    "system": merged.get("devgroup"),
                    "zones": _as_list(merged.get("zones")),
                    "address": address,
                    "port": port,
                    "chart_url": merged.get("charturl"),
                    "opi": merged.get("opi"),
                    "inventory_url": merged.get("asset") or None,
                    "image": merged.get("image") if isinstance(merged.get("image"), str) else None,
                    "host": _text(merged.get("host")),
                    "autosync": merged.get("autosync") if isinstance(merged.get("autosync"), bool) else None,
                    "pva": merged.get("pva") if isinstance(merged.get("pva"), bool) else None,
                    "networks": [str(n.get("annotation") or n.get("name"))
                                 for n in merged.get("networks") or []
                                 if isinstance(n, dict) and (n.get("annotation") or n.get("name"))],
                    "ioc_init": json.dumps(merged["iocinit"]) if merged.get("iocinit") else None,
                    "ssh_nodeport": _text(merged.get("ssh_nodeport")),
                },
            )
            self.relate(ioc, facility, "deployed on")
            self.relate(ioc, self.cfg, "declared in")
            recipe = self.templates.get(str(entry.get("template") or ""))
            if recipe is not None:
                self.relate(ioc, recipe, "templated from")
            for net in merged.get("networks") or []:
                network = self._network(net, tag)
                if network is not None:
                    self.relate(ioc, network, "on network")
            self.counts["iocs"] += 1
            if isinstance(merged.get("pump"), list) and merged["pump"]:
                self._gates.append((ioc, merged["pump"]))

            # An IOC that is one unit (a BPM's electronics, an LLRF chassis, a modulator): its
            # channels are that unit's, not more things.
            unit = infer_ioc(merged) if self.infer else None
            unit_asset = None
            if unit is not None:
                unit_asset = self._infer_from(unit, ioc, "drives", name, name, merged,
                                              _as_list(merged.get("zones")))

            if not merged.get("asset"):
                _note(self.job, self.db,
                      f"{tag}:IOC:{name} has no `asset:` link — the control layer does "
                      f"not say which physical unit it drives")

            ioc_access = None
            if address:
                ioc_access = self.access_point(address, tag, create_missing)
                if ioc_access is not None:
                    self.relate(ioc, ioc_access, "connects to")

            devices = merged.get("devices") or []
            if not devices:
                # An IOC with no device list still drives something; the IOC
                # is the only handle on it.
                if self.infer and unit is None:
                    self.not_inferred[self._kind_of(merged)] += 1
                continue

            for device in devices:
                if not isinstance(device, dict) or not device.get("name"):
                    continue
                self._device(device, merged, ioc, ioc_access, tag, beamline, create_missing,
                             unit=unit, unit_asset=unit_asset)

    @staticmethod
    def _kind_of(entry: dict) -> str:
        return f"{_text(entry.get('devgroup')) or '-'}/{_text(entry.get('template')) or '-'}"

    def _device(self, device: dict, ioc: dict, ioc_asset: Asset,
                ioc_access: Optional[Asset], tag: str, beamline: str,
                create_missing: bool, unit=None, unit_asset: Optional[Asset] = None) -> None:
        device_name = str(device["name"]).strip()
        pv = _pv_prefix(ioc, device_name)
        key = f"{tag}:DEV:{ioc['name']}:{device_name}"
        zones = _as_list(device.get("zones")) or _as_list(ioc.get("zones"))
        address, port = _endpoint_of(device, {})

        asset = self.upsert(
            "Control Device", key, device_name,
            {
                "beamline": tag,
                "pv": pv,
                "pv_prefix": pv,
                # The same vocabulary tickets use for argus_system, so a
                # ticket about "vac" reaches the pumps it is about.
                "system": ioc.get("devgroup"),
                "function": ioc.get("devfunc"),
                "devtype": device.get("devtype") or ioc.get("devtype"),
                "zones": zones,
                "channel": device.get("channel"),
                "axis": device.get("axid"),
                "address": address or ioc.get("_resolved_address"),
                "port": port,
                "interlock": bool(device.get("interlock")),
                "geo": device.get("geo"),
                "ioc": ioc.get("name"),
                "inventory_url": device.get("asset") or ioc.get("asset") or None,
                "settings": _settings(device),
            },
        )
        self.counts["devices"] += 1
        if pv:
            other = self.pv_index.get(pv)
            if other is not None and other.uid != asset.uid:
                # Two IOCs configured to serve one PV: EPICS clients will find whichever
                # answers first. Both are recorded, because both are in the file.
                _note(self.job, self.db,
                      f"PV {pv} is configured on two IOCs: {other.key} and {asset.key}")
            self.pv_index[pv] = asset

        self.relate(asset, ioc_asset, "provided by")
        self.relate(asset, self.cfg, "declared in")

        if self.infer and unit is not None:
            # The IOC is one unit and its channels are its own; but where each channel is an
            # element (a Libera Spectra's BPMs), each one is made.
            if unit.channel_element:
                self._infer_channel_element(unit.channel_element, asset, unit_asset, device_name, zones,
                                            f"channel {device_name} of {unit.why}")
        elif self.infer:
            inference = infer_device(ioc, device)
            if inference is None:
                self.not_inferred[self._kind_of({**ioc, **{k: v for k, v in device.items()
                                                           if k in ("devgroup", "template")}})] += 1
            else:
                self._infer_from(inference, asset, "acts on", f"{ioc['name']}:{device_name}",
                                 device_name, {**ioc, **device}, zones)

        # Addressed directly, or through whatever the IOC connects to.
        if address:
            own = self.access_point(address, tag, create_missing)
            if own is not None:
                self.relate(asset, own, "reached through")
        elif ioc_access is not None:
            self.relate(asset, ioc_access, "reached through")

    # --- what the configuration says depends on what ---------------------

    def _cross_references(self, tag: str) -> None:
        """Dependencies the configuration states outright.

        An RF conditioning IOC names nine ion pumps and the pressure above
        which it will not raise power; a BCM channel names the PV that
        enables it. These are causal links between systems, written down in
        a file nobody can query, and they are the edges a root-cause walk
        most wants.
        """
        if not self.pv_index:
            return
        by_suffix: dict[str, list[Asset]] = {}
        for pv, asset in self.pv_index.items():
            by_suffix.setdefault(pv.rsplit(":", 1)[-1], []).append(asset)

        for key, asset in list(self.assets.items()):
            if asset.type != "Control Device":
                continue
            settings = (asset.attributes or {}).get("settings") or {}
            for field_name, value in settings.items():
                if not isinstance(value, str) or ":" not in value:
                    continue
                if field_name not in ("enablepv", "pv"):
                    continue
                target = self.pv_index.get(value.rsplit(".", 1)[0])
                if target is None:
                    candidates = by_suffix.get(value.rsplit(":", 1)[-1].split(".")[0], [])
                    target = candidates[0] if len(candidates) == 1 else None
                if target is not None:
                    self.relate(asset, target, "enabled by")


def _fetch(provider: str, repo_url: str, pat: Optional[str], branch: str, path: str) -> str:
    """One file from the repository, with a token only if there is one.

    These configurations live on baltig.infn.it, so the API address comes
    from the repository URL; and several of them are readable without a
    credential, so an absent token means no header rather than an empty one.
    """
    session = requests.Session()
    owner, repo = _parse_repo(repo_url)
    if provider == "github":
        if pat:
            session.headers.update({"Authorization": f"Bearer {pat}"})
        return _get_file_github(session, owner, repo, path, branch, github_api(repo_url))
    if pat:
        session.headers.update({"PRIVATE-TOKEN": pat})
    return _get_file_gitlab(session, f"{owner}/{repo}", path, branch, gitlab_api(repo_url))


def run_epik8s_import(
    job_uid: str,
    workspace_id: str,
    provider: str,
    repo_url: str,
    pat: str,
    branch: str = "main",
    path: str = "deploy/values.yaml",
    merge_strategy: str = "override",
    create_missing_nodes: bool = True,
    infer_elements: bool = False,
):
    """Read one beamline's values.yaml and mirror what it describes."""
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        _progress(db, job, f"Reading {path} from {repo_url}@{branch}")
        text = _fetch(provider, repo_url, pat, branch, path)
        values = yaml.safe_load(text)
        if not isinstance(values, dict):
            raise ValueError(f"{path} did not parse as a mapping — is that the right file?")

        importer = _Importer(db, job, workspace_id, f"{repo_url}@{branch}:{path}",
                             infer_elements=infer_elements)
        importer.ensure_types()

        if merge_strategy == "remove_all_before":
            beamline = str(values.get("beamline") or "").strip().upper()
            removed = 0
            for asset in db.scalars(
                select(Asset).where(
                    Asset.workspace_id == workspace_id,
                    Asset.attributes["argus_source"].astext == SOURCE,
                )
            ):
                if not beamline or (asset.key or "").startswith(f"{beamline}:") \
                        or asset.key == beamline:
                    db.delete(asset)
                    removed += 1
            db.commit()
            _progress(db, job, f"Removed {removed} previously-imported object(s)")

        _progress(db, job, "Walking the configuration")
        importer.run(values, create_missing_nodes)

        for asset in importer.assets.values():
            rebuild_asset_relations(db, asset.uid)
        db.commit()

        job.counts = {**(job.counts or {}), **importer.counts}
        job.status = "completed"
        linked = importer.counts["access_points_linked"]
        created = importer.counts["access_points_created"]
        job.progress = (
            f"{importer.counts['iocs']} IOC(s) and {importer.counts['devices']} device(s) "
            f"in workspace {workspace_id}. "
            + (
                f"{linked} address(es) matched equipment already in this workspace"
                if linked
                else "No address matched anything already in this workspace"
            )
            + f"; {created} Access Point(s) created and awaiting confirmation."
        )
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        job = db.get(ImportJob, job_uid)
        if job is not None:
            job.status = "failed"
            job.error = f"{type(e).__name__}: {e}"[:2000]
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
