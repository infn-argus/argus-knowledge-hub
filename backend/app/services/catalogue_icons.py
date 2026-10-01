"""Default icons for the catalogue's types.

Every type gets a picture: its own where the map below names one, else its
nearest ancestor's (an Ion Pump shows the pump of Vacuum Pump). Most are Tabler
Icons (MIT, `app/catalogue_icons/tabler/`); four that Tabler has no fitting
symbol for are drawn for ARGUS in the same style (`app/catalogue_icons/argus/`):
a dipole magnet, a quadrupole, a vacuum cross and a valve.

Seeding installs them in the seeded workspace's icon library, shared like the
types, and sets a type's icon only where it has none: a picture somebody chose,
or one an import brought, stays. Seeding again fills gaps and nothing else.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.icon import Icon
from app.models.schema import Schema

ICON_DIR = Path(__file__).resolve().parents[1] / "catalogue_icons"
PREFIX = "argus-"

ICONS = {
    # the root and its branches
    "Item": "tabler/box", "Engineered Item": "tabler/components",
    "Functional Element": "tabler/hierarchy-2", "Asset": "tabler/package",
    "Catalog Item": "tabler/book", "Control Item": "tabler/adjustments",
    "Engineering Record": "tabler/file-description", "Location": "tabler/map-pin",
    "IT Record": "tabler/address-book",
    # the machine, as a function
    "Facility": "tabler/building-factory-2", "Section": "tabler/section", "Machine System": "tabler/sitemap",
    "Machine Module": "tabler/puzzle", "RF Station": "tabler/antenna-bars-5",
    "Beam Element": "tabler/arrow-narrow-right",
    "Dipole": "argus/dipole-magnet", "Quadrupole": "argus/quadrupole", "Sextupole": "tabler/hexagon",
    "Corrector": "argus/dipole-magnet", "Solenoid": "tabler/spiral",
    "Accelerating Structure": "tabler/wave-sine", "RF Gun": "tabler/atom", "RF Deflector": "tabler/arrow-bear-right",
    "Undulator": "tabler/wave-square", "Plasma Module": "tabler/atom-2", "Collimator": "tabler/focus-centered",
    "Beam Stopper": "tabler/hand-stop", "Mirror": "tabler/flip-horizontal", "Vacuum Sector": "tabler/brackets-contain",
    "Diagnostic Element": "tabler/chart-line", "Screen Station": "tabler/aperture",
    "Beam Position Monitor": "tabler/crosshair", "Beam Charge Monitor": "tabler/chart-donut",
    "Faraday Cup": "tabler/cup", "Wire Scanner": "tabler/scan", "Emittance Meter": "tabler/chart-scatter",
    "Spectrometer Station": "tabler/prism", "Beam Loss Monitor": "tabler/alert-triangle",
    "Beam Arrival Monitor": "tabler/clock", "Bunch Length Monitor": "tabler/ruler-measure",
    # the equipment
    "Power Supply": "tabler/bolt", "Magnet Assembly": "argus/dipole-magnet", "RF Amplifier": "tabler/antenna",
    "Modulator": "tabler/wave-saw-tool", "Low-Level RF Unit": "tabler/cpu",
    "Waveguide Component": "tabler/arrows-right-left",
    "Vacuum Pump": "tabler/propeller", "Vacuum Gauge": "tabler/gauge", "Vacuum Valve": "argus/vacuum-valve",
    "Vacuum Chamber": "tabler/cylinder", "Vacuum Component": "argus/vacuum-cross", "Vacuum Controller": "tabler/settings-automation",
    "Motion Controller": "tabler/adjustments-horizontal", "Motor Axis": "tabler/engine",
    "Actuator": "tabler/arrows-move-horizontal", "Camera": "tabler/camera", "Optical Assembly": "tabler/eye",
    "Scintillator Screen": "tabler/sun", "Digitizer": "tabler/device-analytics", "Instrument": "tabler/tool",
    "I/O Module": "tabler/plug", "PLC": "tabler/cpu-2", "Timing Module": "tabler/clock",
    "Electronics Crate": "tabler/server-2", "Electronics Board": "tabler/cpu",
    "IT Equipment": "tabler/device-desktop", "Network Device": "tabler/network", "Router": "tabler/router",
    "Serial Converter": "tabler/plug-connected", "Media Converter": "tabler/transform",
    "Computing Node": "tabler/server", "Workstation": "tabler/device-desktop",
    "Chiller": "tabler/snowflake", "Cooling Circuit Component": "tabler/droplet",
    "Cryogenic Device": "tabler/temperature-minus", "Interlock Unit": "tabler/lock",
    "Radiation Monitor": "tabler/radioactive", "Laser System": "tabler/flare",
    "Cable Run": "tabler/plug-connected", "Power Cable": "tabler/plug", "HV Cable": "tabler/bolt",
    "RF Cable": "tabler/antenna", "Signal Cable": "tabler/activity", "Ethernet Cable": "tabler/network",
    "Mechanical Support": "tabler/building-bridge", "Spare Part": "tabler/box-multiple", "Other Equipment": "tabler/box",
    "Equipment Port": "tabler/plug-connected",
    # the catalogue
    "Product Model": "tabler/barcode", "Vendor": "tabler/building-store",
    # control
    "Control Configuration": "tabler/file-settings", "IOC Template": "tabler/template", "IOC": "tabler/terminal-2",
    "Control Device": "tabler/toggle-left", "Access Point": "tabler/access-point", "Serial Line": "tabler/line-dashed",
    "Communication Path": "tabler/route", "Bus Segment": "tabler/arrows-join",
    "Control Service": "tabler/cloud-computing", "Control Network": "tabler/network", "Storage Mount": "tabler/database",
    # engineering records
    "Utility Requirement": "tabler/bolt", "Procurement Record": "tabler/receipt", "Work Package": "tabler/briefcase",
    # places and addresses
    "Building": "tabler/building", "Area": "tabler/map-2", "Rack": "tabler/stack-2",
    "Storage Location": "tabler/packages", "Network Segment": "tabler/network", "Address Record": "tabler/at",
}


# The default ticket and document types (ticket_types, document_types). A type an import adds (a Jira
# "Incident") takes its base type's icon.
TICKET_ICONS = {"Ticket": "tabler/ticket", "Epic": "tabler/bolt", "Story": "tabler/bookmark", "Task": "tabler/checkbox",
                "Bug": "tabler/bug", "Sub-task": "tabler/subtask"}
DOCUMENT_ICONS = {
    "Document": "tabler/file-text", "Commissioning Record": "tabler/clipboard-check",
    "Design Report": "tabler/file-analytics", "Drawing": "tabler/vector", "Logbook Entry": "tabler/notebook",
    "Maintenance Report": "tabler/tools", "Manual": "tabler/book-2", "Meeting Minutes": "tabler/users-group",
    "Note": "tabler/note", "Procedure": "tabler/list-numbers", "Runbook": "tabler/list-check",
    "Safety Document": "tabler/shield-check", "Specification": "tabler/file-certificate",
    "Test Report": "tabler/test-pipe", "Work Instruction": "tabler/clipboard-list",
}


def ticket_icon(name: str) -> Optional[str]:
    return TICKET_ICONS.get(name, TICKET_ICONS["Ticket"])


def document_icon(name: str) -> Optional[str]:
    return DOCUMENT_ICONS.get(name, DOCUMENT_ICONS["Document"])


def icon_for(name: str) -> Optional[str]:
    """The type's icon, or its nearest ancestor's."""
    from app.services.asset_types import BY_NAME
    cur: Optional[str] = name
    while cur is not None:
        if cur in ICONS:
            return ICONS[cur]
        cur = BY_NAME[cur].parent if cur in BY_NAME else None
    return None


def _attachments_dir() -> str:
    return os.environ.get("ATTACHMENTS_DIR", "/data/attachments")


def _library_icon(db: Session, workspace_id: str, icon: str, share: bool) -> Icon:
    """The catalogue icon in this workspace's library, installed on first use. Its file is a copy in the
    attachment store, as an uploaded icon's is (deleting an icon deletes its file)."""
    source = ICON_DIR / f"{icon}.svg"
    filename = f"{PREFIX}{icon.split('/')[-1]}.svg"
    row = db.scalar(select(Icon).where(Icon.workspace_id == workspace_id, Icon.filename == filename).limit(1))
    content = source.read_bytes()
    if row is None:
        uid = str(uuid.uuid4())
        row = Icon(uid=uid, workspace_id=workspace_id, filename=filename, mime_type="image/svg+xml",
                   name=icon.split("/")[-1].replace("-", " ").capitalize(), file_size=len(content),
                   storage_path=os.path.join(_attachments_dir(), uid), is_global=share)
        db.add(row)
    elif share and not row.is_global:
        row.is_global = True
    # A fresh install, a wiped store, or a release that redrew the icon: the catalogue's own files follow it.
    current = open(row.storage_path, "rb").read() if os.path.exists(row.storage_path) else None
    if current != content:
        os.makedirs(os.path.dirname(row.storage_path), exist_ok=True)
        with open(row.storage_path, "wb") as f:
            f.write(content)
        row.file_size = len(content)
    return row


def apply(db: Session, workspace_id: str, uids: dict[str, str], share: bool, icon_of=None) -> list[str]:
    """Give each of the workspace's own types its default icon where it has none (`icon_of`: the object
    catalogue's by default, or ticket_icon / document_icon). Returns the names of the types that got one."""
    icon_for_type = icon_of or icon_for
    given = []
    cache: dict[str, Icon] = {}
    for name, uid in uids.items():
        schema = db.get(Schema, uid)
        if schema is None or schema.workspace_id != workspace_id:
            continue
        if schema.icon_uid:
            # Not this type's to fill; but if it shows one of the catalogue's own icons, keep that file current.
            icon_row = db.get(Icon, schema.icon_uid)
            default = icon_for_type(name)
            if icon_row is not None and default and icon_row.filename == f"{PREFIX}{default.split('/')[-1]}.svg" \
                    and icon_row.workspace_id == workspace_id and default not in cache:
                cache[default] = _library_icon(db, workspace_id, default, bool(icon_row.is_global))
            continue
        icon = icon_for_type(name)
        if icon is None or not (ICON_DIR / f"{icon}.svg").exists():
            continue
        if icon not in cache:
            cache[icon] = _library_icon(db, workspace_id, icon, share or bool(schema.is_global))
            db.flush()
        if (share or schema.is_global) and not cache[icon].is_global:
            cache[icon].is_global = True                         # a shared type's icon is seen wherever the type is
        schema.icon_uid = cache[icon].uid
        given.append(name)
    db.flush()
    return given
