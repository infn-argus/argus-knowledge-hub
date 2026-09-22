"""Turning an alarm feed into symptoms `root_cause.root_causes` can use.

There is no live connection here — no alarm server, no archiver, nothing on a network. What this
does is the translation a live connection would still need afterwards: an alarm names a PV, and the
graph deals in objects, so something has to say which object a PV is about, and what kind of loss
the alarm actually reports. That translation is what makes wiring in a real feed later a matter of
calling `symptoms_from_alarms` with what it returns, not a second design.

**What a PV is, here.** `Control Device.pv` is the full PV the import derived from the configuration
(`SPARC:VAC:GUNVPC:GUNSIP01`), and it is what an alarm handler names too — Phoebus, the EPICS
alarm server, or a CA/PVA client all report the same string. `IOC.pv_prefix` is the coarser name a
heartbeat or a connection alarm uses. Both are read from the objects already in the hub; nothing new
has to be imported for this to work.

**What a severity means.** This is EPICS convention, not a guess: `INVALID` means the record could
not determine a value at all, almost always because the channel could not be reached — a lost
*readout*. `MINOR`/`MAJOR` mean the record has a value and it is out of the range someone set — a
lost *function*. `OK` is not a symptom; it is evidence the object works, and is treated as `healthy`.
A status that says outright that the channel is disconnected is read as `INVALID` regardless of the
severity field, because some sources put that fact in the status text instead.

**What is deliberately not inferred.** A `permit` symptom — "this will not run because a condition
is not met" — has no severity of its own in this scheme, and is never guessed from one. It is used
only when the caller states it, because guessing it would claim a machine-protection fact from a
value alarm, which is a different kind of claim than this module is willing to make silently.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation
from app.services.causal_model import CONTROL, FUNCTION, PERMIT
from app.services.root_cause import root_causes

DISCONNECT_WORDS = ("disconnect", "timeout", "not connect", "unreachable", "no_alarm_no_server")
HEALTHY_SEVERITIES = {"OK", "NO_ALARM", ""}
KNOWN_KINDS = {CONTROL, FUNCTION, PERMIT}


@dataclass(frozen=True)
class Alarm:
    pv: str
    severity: str = ""
    status: str = ""
    # The caller's own word for what is lost, when they know it (e.g. `permit`, which is never
    # guessed). Overrides whatever the severity would otherwise say.
    kind: Optional[str] = None


def infer_kind(severity: str, status: str) -> Optional[str]:
    """`control` when the record could not be read (`INVALID`, or the status names a disconnect);
    `function` when it could be read and the value itself is out of range (`MINOR`/`MAJOR`); `None`
    when the severity says neither — reported as unclassified rather than guessed."""
    if any(word in (status or "").lower() for word in DISCONNECT_WORDS):
        return CONTROL
    severity = (severity or "").strip().upper()
    if severity == "INVALID":
        return CONTROL
    if severity in ("MINOR", "MAJOR"):
        return FUNCTION
    return None


def is_healthy(severity: str) -> bool:
    return (severity or "").strip().upper() in HEALTHY_SEVERITIES


class PVIndex:
    """PVs and prefixes, read once and used for every alarm in a batch."""

    def __init__(self, device_by_pv: dict, duplicate_pvs: set, acts_on: dict, ioc_prefixes: list):
        self.device_by_pv = device_by_pv
        self.duplicate_pvs = duplicate_pvs
        self.acts_on = acts_on                    # device uid -> Asset it acts on
        self.ioc_prefixes = ioc_prefixes           # [(prefix, Asset)], longest first


def build_index(db: Session, workspace_id: str) -> PVIndex:
    device_by_pv: dict[str, Asset] = {}
    duplicate_pvs: set = set()
    for asset in db.scalars(select(Asset).where(
            Asset.workspace_id == workspace_id, Asset.type == "Control Device",
            Asset.deleted_at.is_(None))):
        pv = (asset.attributes or {}).get("pv")
        if not pv:
            continue
        if pv in device_by_pv:
            duplicate_pvs.add(pv)
            continue
        device_by_pv[pv] = asset

    acts_on: dict[str, Asset] = {}
    device_uids = {a.uid for a in device_by_pv.values()}
    if device_uids:
        targets = {}
        for chunk_start in range(0, len(device_uids), 500):
            chunk = list(device_uids)[chunk_start:chunk_start + 500]
            for r in db.scalars(select(Relation).where(
                    Relation.workspace_id == workspace_id, Relation.relation_type == "acts on",
                    Relation.from_asset_uid.in_(chunk))):
                targets.setdefault(r.from_asset_uid, r.to_asset_uid)
        if targets:
            for asset in db.scalars(select(Asset).where(Asset.uid.in_(set(targets.values())))):
                acts_on.update({k: asset for k, v in targets.items() if v == asset.uid})

    prefixes = []
    for asset in db.scalars(select(Asset).where(
            Asset.workspace_id == workspace_id, Asset.type == "IOC", Asset.deleted_at.is_(None))):
        prefix = (asset.attributes or {}).get("pv_prefix")
        if prefix:
            prefixes.append((str(prefix).rstrip(":"), asset))
    prefixes.sort(key=lambda p: -len(p[0]))

    return PVIndex(device_by_pv, duplicate_pvs, acts_on, prefixes)


@dataclass
class Resolution:
    key: Optional[str] = None
    kind: Optional[str] = None
    note: str = ""


def resolve(alarm: Alarm, index: PVIndex) -> Resolution:
    """The object an alarm is about, and what it lost — never guessed past what the alarm states."""
    device = index.device_by_pv.get(alarm.pv)
    if device is not None:
        kind = alarm.kind or infer_kind(alarm.severity, alarm.status)
        if kind is None:
            return Resolution(note=f"severity “{alarm.severity}” is not INVALID/MINOR/MAJOR, "
                                    f"and no kind was given")
        note = f"{alarm.pv} is read by more than one device; used {device.key}" \
            if alarm.pv in index.duplicate_pvs else ""
        if kind == CONTROL:
            return Resolution(device.key, CONTROL, note)
        target = index.acts_on.get(device.uid)
        if target is not None:
            return Resolution(target.key, kind, note)
        return Resolution(device.key, kind,
                          (note + "; " if note else "") + "no asset it acts on is known — "
                          "treated as the channel's own fault")
    prefix_match = next((asset for prefix, asset in index.ioc_prefixes
                         if alarm.pv == prefix or alarm.pv.startswith(prefix + ":")), None)
    if prefix_match is not None:
        kind = alarm.kind or infer_kind(alarm.severity, alarm.status) or CONTROL
        return Resolution(prefix_match.key, kind, "matched by IOC prefix, not an exact device PV")
    return Resolution(note="no object in this workspace carries this PV")


def symptoms_from_alarms(db: Session, workspace_id: str, alarms: list[Alarm]) -> dict:
    """Alarms resolved against the object graph: ready to hand to `root_causes`, plus what could not
    be placed, so a gap in the model is visible rather than silently dropped. A PV reported `OK`
    becomes `healthy` automatically — the caller does not have to say twice that something works."""
    index = build_index(db, workspace_id)
    symptoms: dict[str, str] = {}
    healthy: list[str] = []
    unresolved: list[dict] = []
    for alarm in alarms:
        if not alarm.pv:
            continue
        if alarm.kind is None and is_healthy(alarm.severity):
            resolution = resolve(Alarm(alarm.pv, "INVALID", "", None), index)   # placement only
            if resolution.key:
                healthy.append(resolution.key)
            else:
                unresolved.append({"pv": alarm.pv, "severity": alarm.severity, "status": alarm.status,
                                   "reason": resolution.note})
            continue
        resolution = resolve(alarm, index)
        if resolution.key is None:
            unresolved.append({"pv": alarm.pv, "severity": alarm.severity, "status": alarm.status,
                               "reason": resolution.note})
            continue
        # The worse of two kinds reported for the same object wins; a lost function says more
        # than a lost readout inferred for the same thing from a different alarm.
        if resolution.key not in symptoms or (symptoms[resolution.key] == CONTROL
                                              and resolution.kind != CONTROL):
            symptoms[resolution.key] = resolution.kind
    return {"symptoms": symptoms, "healthy": sorted(set(healthy) - set(symptoms)),
            "unresolved": unresolved, "placed": len(symptoms)}


def root_cause_from_alarms(
    db: Session, workspace_id: str, alarms: list[dict], layers: Optional[list] = None,
    max_depth: int = 6, top: int = 10,
) -> dict:
    """The end-to-end call: raw alarm rows in, `root_causes`'s answer out, with the placement
    reported alongside it so an assistant can say which alarms it could not use."""
    parsed = [Alarm(str(a.get("pv") or ""), str(a.get("severity") or ""), str(a.get("status") or ""),
                    a.get("kind") if a.get("kind") in KNOWN_KINDS else None)
             for a in alarms]
    placed = symptoms_from_alarms(db, workspace_id, parsed)
    if not placed["symptoms"]:
        return {**placed, "symptoms": [], "candidates": [], "hypotheses": [], "not_found": []}
    result = root_causes(
        db, workspace_id, list(placed["symptoms"]), healthy=placed["healthy"], layers=layers,
        max_depth=max_depth, top=top, symptom_kind=placed["symptoms"],
    )
    return {**result, "unresolved": placed["unresolved"], "placed": placed["placed"]}
