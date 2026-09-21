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

Five kinds of thing come out:

  Facility          the beamline
  IOC               the deployable unit
  Control Device    the channel, axis or gauge that actually fails
  Access Point      what sits between EPICS and the metal
  Control Service   archiver, gateways, alarm server, logbook

The device is first-class rather than the IOC, because "GUNSIP01 tripped"
is the sentence people actually write.
"""
import hashlib
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
    def __init__(self, db: Session, job: ImportJob, workspace_id: str, source_ref: str):
        self.db = db
        self.job = job
        self.workspace_id = workspace_id
        self.source_ref = source_ref
        self.schemas: dict[str, Schema] = {}
        self.index = NetworkIndex(db, workspace_id)
        self.counts = {
            "facilities": 0, "iocs": 0, "devices": 0, "services": 0,
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
        existing = {
            s.name: s for s in self.db.scalars(
                select(Schema).where(
                    Schema.workspace_id == self.workspace_id, Schema.applies_to == "objects"
                )
            )
        }
        for name, description in TYPES.items():
            schema = existing.get(name)
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

        self._services(epics.get("services") or {}, facility, tag)
        self._iocs(epics.get("iocs"), defaults, facility, tag, beamline, create_missing)
        self._cross_references(tag)

        self.db.commit()

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
                },
            )
            self.relate(service, facility, "deployed on")
            self.counts["services"] += 1

    def _iocs(self, iocs: Any, defaults: dict, facility: Asset, tag: str,
              beamline: str, create_missing: bool) -> None:
        for entry in _ioc_entries(iocs):
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
                },
            )
            self.relate(ioc, facility, "deployed on")
            self.counts["iocs"] += 1

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
                continue

            for device in devices:
                if not isinstance(device, dict) or not device.get("name"):
                    continue
                self._device(device, merged, ioc, ioc_access, tag, beamline, create_missing)

    def _device(self, device: dict, ioc: dict, ioc_asset: Asset,
                ioc_access: Optional[Asset], tag: str, beamline: str,
                create_missing: bool) -> None:
        device_name = str(device["name"]).strip()
        pv = _pv_prefix(ioc, device_name)
        key = f"{tag}:DEV:{ioc['name']}:{device_name}"
        zones = _as_list(device.get("zones")) or _as_list(ioc.get("zones"))
        address, port = _endpoint_of(device, {})

        asset = self.upsert(
            "Control Device", key, device_name,
            {
                "beamline": tag,
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
            self.pv_index[pv] = asset

        self.relate(asset, ioc_asset, "provided by")

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

        importer = _Importer(db, job, workspace_id, f"{repo_url}@{branch}:{path}")
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
