"""The type catalogue as one map: tree, description, attributes with where they come from, aliases,
what references mean in the graph, record counts and the equipment classes."""
import secrets

from app.db import SessionLocal
from app.models.workspace import Workspace
from app.services.asset_types import CATALOGUE, ensure_asset_types
from app.services.type_catalogue import catalogue


def test_every_type_with_its_place_attributes_aliases_and_graph_meaning():
    ws = f"map-{secrets.token_hex(3)}"
    db = SessionLocal()
    try:
        db.add(Workspace(id=ws, name=ws))
        db.flush()
        ensure_asset_types(db, ws)
        out = catalogue(db, ws)
        names = {t["name"]: t for t in out["types"]}
        assert set(names) >= {t.name for t in CATALOGUE}
        turbo = names["Turbo Pump"]
        assert turbo["path"] == ["Item", "Engineered Item", "Asset", "Vacuum Pump", "Turbo Pump"]
        assert turbo["branch"] == "equipment" and not turbo["abstract"] and turbo["icon_uid"]
        attrs = {a["key"]: a for a in turbo["attributes"]}
        assert attrs["rotation_speed"]["origin"] == "Turbo Pump"
        assert attrs["backing_pump"]["refers_to"] == "Primary Pump"
        assert attrs["serial"]["origin"] == "Asset"
        assert attrs["product_model"]["relation"] == "instance of"                   # what the graph makes of it
        assert names["Vacuum Component"]["aliases"][0] == "pipe"
        assert names["Vacuum Pump"]["abstract"] and names["IOC"]["branch"] == "control"
        assert any(c["name"] == "Unclassified" for c in out["equipment_classes"])
    finally:
        db.rollback()
        db.close()


def test_default_ticket_and_document_types_get_their_icons(tmp_path, monkeypatch):
    from app.models.icon import Icon
    from app.models.schema import Schema
    from app.services import catalogue_icons
    from app.services.document_types import ensure_document_types
    from app.services.ticket_types import DEFAULT_ISSUE_TYPES, ensure_ticket_types
    monkeypatch.setenv("ATTACHMENTS_DIR", str(tmp_path))
    for icon in {*catalogue_icons.TICKET_ICONS.values(), *catalogue_icons.DOCUMENT_ICONS.values()}:
        assert (catalogue_icons.ICON_DIR / f"{icon}.svg").exists(), icon
    ws = f"icn-{secrets.token_hex(3)}"
    db = SessionLocal()
    try:
        db.add(Workspace(id=ws, name=ws))
        db.flush()
        ensure_ticket_types(db, ws, set(DEFAULT_ISSUE_TYPES) | {"Incident"})
        ensure_document_types(db, ws)
        icons = {s.name: db.get(Icon, s.icon_uid).filename for s in db.query(Schema).filter(
            Schema.workspace_id == ws, Schema.applies_to.in_(("tickets", "documents")))}
        assert icons["Bug"] == "argus-bug.svg" and icons["Ticket"] == "argus-ticket.svg"
        assert icons["Incident"] == "argus-ticket.svg"                                 # an import's type: the base's
        assert icons["Procedure"] == "argus-list-numbers.svg" and icons["Document"] == "argus-file-text.svg"
        assert len(icons) == 7 + 15
    finally:
        db.rollback()
        db.close()
