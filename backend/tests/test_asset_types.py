"""The object catalogue.

What is worth testing is what could be wrong without anybody noticing: a key
spelled differently from the one tickets use (so "everything about the vacuum
system" quietly stops being answerable), a control-plane key the importer
writes that no type declares, a reference pointing at a type that is not
there, and a seeder that duplicates or overwrites what a workspace already
holds.
"""
import re
import secrets

import pytest
import yaml
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.import_job import ImportJob
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services import asset_types as at
from app.services.attribute_validation import check_attributes, effective_attributes
from app.services.document_types import BASE_ATTRIBUTES as DOCUMENT_ATTRIBUTES
from app.services.epik8s_import import _Importer
from app.services.ticket_types import BASE_ATTRIBUTES as TICKET_ATTRIBUTES
from tests.test_epik8s_import import VALUES_TEMPLATE

pytestmark = pytest.mark.usefixtures("_schema")


@pytest.fixture(scope="module")
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def workspace(db):
    ws = f"cat-{secrets.token_hex(4)}"
    db.add(Workspace(id=ws, name="Catalogue"))
    db.commit()
    return ws


def keys_of(name):
    return {a["key"] for a in at.BY_NAME[name].attributes}


def effective_keys(db, ws, name):
    schema = db.get(Schema, at.type_uid(ws, name))
    return {a["key"] for a in effective_attributes(db, schema)}


# --- the shape --------------------------------------------------------------

def test_the_catalogue_is_the_size_the_design_says():
    assert len(at.CATALOGUE) == 103
    assert sum(t.abstract for t in at.CATALOGUE) == 12
    assert max(at.depth(t.name) for t in at.CATALOGUE) == 6


def test_names_are_unique_and_so_are_their_uids():
    names = [t.name for t in at.CATALOGUE]
    assert len(names) == len(set(names))
    slugs = [at.type_uid("ws", n) for n in names]
    assert len(slugs) == len(set(slugs))


def test_parents_come_before_children_so_a_copy_can_resolve_them():
    seen = set()
    for spec in at.CATALOGUE:
        assert spec.parent is None or spec.parent in seen, spec.name
        seen.add(spec.name)


def test_every_reference_names_a_type_that_exists():
    for spec in at.CATALOGUE:
        for attr in spec.attributes:
            if attr["type"] == "reference":
                assert attr["referenceType"] in at.BY_NAME, (spec.name, attr["key"])


def test_a_pattern_is_anchored_or_it_matches_a_substring():
    for spec in at.CATALOGUE:
        for attr in spec.attributes:
            if attr.get("regex"):
                assert attr["regex"].startswith("^") and attr["regex"].endswith("$"), attr["key"]
                re.compile(attr["regex"])


def test_no_type_declares_the_same_key_twice():
    for spec in at.CATALOGUE:
        keys = [a["key"] for a in spec.attributes]
        assert len(keys) == len(set(keys)), spec.name


def test_only_the_root_and_the_five_branches_sit_directly_under_it():
    assert {t.name for t in at.CATALOGUE if t.parent == "Item"} == {
        "Engineered Item", "Catalog Item", "Control Item", "Engineering Record", "Place"}


# --- keys other parts of the hub already depend on --------------------------

def test_the_keys_shared_with_tickets_and_documents_are_spelled_the_same():
    item = {a["key"]: a for a in at.BY_NAME["Item"].attributes}
    for key, _name, type_, extra in TICKET_ATTRIBUTES + DOCUMENT_ATTRIBUTES:
        if key in ("argus_system", "argus_subsystem", "argus_facility", "argus_keywords"):
            assert key in item
            assert item[key]["type"] == type_
            assert item[key]["indexed"] == extra.get("indexed", False)
            assert item[key]["multiValue"] == extra.get("multiValue", False)
    assert {"argus_system", "argus_subsystem", "argus_facility", "argus_keywords"} <= set(item)


def test_the_keys_photo_identification_writes_are_declared():
    # asset_vision fills these four on a new object, unprefixed.
    assert "description" in keys_of("Item")
    assert {"manufacturer", "model", "serial"} <= keys_of("Equipment Item")


def test_every_enumeration_option_has_a_unique_id():
    for spec in at.CATALOGUE:
        for attr in spec.attributes:
            if attr["type"] == "enumeration":
                ids = [o["id"] for o in attr["options"]]
                assert ids and len(ids) == len(set(ids)), (spec.name, attr["key"])


def test_the_source_options_include_the_ones_the_importers_write():
    ids = {o["id"] for o in next(a for a in at.BY_NAME["Item"].attributes
                                  if a["key"] == "argus_source")["options"]}
    assert {"epik8s", "epik8s-devices", "pbs"} <= ids


# --- seeding ------------------------------------------------------------------

def test_seeding_creates_the_whole_tree(db, workspace):
    result = at.ensure_asset_types(db, workspace)
    db.commit()
    assert len(result.created) == 103 and not result.adopted and not result.duplicates
    rows = db.query(Schema).filter(Schema.workspace_id == workspace).all()
    assert len(rows) == 103
    by_name = {s.name: s for s in rows}
    assert by_name["Ion Pump"].parent_schema_uid == at.type_uid(workspace, "Vacuum Pump")
    assert by_name["Vacuum Pump"].parent_schema_uid == at.type_uid(workspace, "Equipment Item")
    assert by_name["Item"].parent_schema_uid is None
    assert by_name["Vacuum Pump"].is_concrete is False and by_name["Ion Pump"].is_concrete is True
    assert all(s.applies_to == "objects" for s in rows)


def test_seeding_twice_changes_nothing(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    again = at.ensure_asset_types(db, workspace)
    db.commit()
    assert not again.created and not again.adopted and not again.extended
    assert db.query(Schema).filter(Schema.workspace_id == workspace).count() == 103


def test_a_leaf_inherits_what_the_ancestors_declare(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    ion_pump = effective_keys(db, workspace, "Ion Pump")
    assert {"pumping_speed", "serial", "manufacturer", "pbs_code", "argus_system",
            "argus_lifecycle", "description"} <= ion_pump
    # and nothing from another branch
    assert "gradient" not in ion_pump and "pv" not in ion_pump


def test_a_reference_is_bound_to_the_type_in_this_workspace(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    schema = db.get(Schema, at.type_uid(workspace, "Equipment Item"))
    located = next(a for a in schema.attributes if a["key"] == "argus_location")
    assert located["referenceSchemaUid"] == at.type_uid(workspace, "Place")
    assert located["includeChildren"] is True


def test_seeding_adds_what_is_missing_and_never_overwrites(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    uid = at.type_uid(workspace, "Ion Pump")
    schema = db.get(Schema, uid)
    edited = [dict(a) for a in schema.attributes]
    edited[0]["name"] = "Pumping speed, as this beamline writes it"
    schema.attributes = edited[:2]          # one edited, one removed
    db.commit()
    again = at.ensure_asset_types(db, workspace)
    db.commit()
    db.expire_all()
    after = db.get(Schema, uid).attributes
    assert after[0]["name"] == "Pumping speed, as this beamline writes it"
    assert {a["key"] for a in after} == keys_of("Ion Pump")
    assert again.extended == ["Ion Pump"]


def test_a_type_an_importer_made_is_adopted_not_duplicated(db, workspace):
    # uids are primary keys across the whole installation, so they carry the
    # workspace here as the real ones should.
    ioc_uid = f"epik8s-{workspace}-ioc"
    db.add(Schema(uid=ioc_uid, workspace_id=workspace, name="IOC",
                  applies_to="objects", metadata_json={"source": "epik8s"}, attributes=[]))
    db.add(Schema(uid=f"epik8s-{workspace}-power-supply", workspace_id=workspace,
                  name="Power Supply", applies_to="objects", attributes=[]))
    db.commit()
    result = at.ensure_asset_types(db, workspace)
    db.commit()
    assert sorted(result.adopted) == ["IOC", "Power Supply"]
    assert result.uids["IOC"] == ioc_uid
    rows = db.query(Schema).filter(Schema.workspace_id == workspace).all()
    assert len(rows) == 103 and sum(1 for s in rows if s.name == "IOC") == 1
    ioc = db.get(Schema, ioc_uid)
    assert ioc.parent_schema_uid == at.type_uid(workspace, "Control Item")
    assert {a["key"] for a in ioc.attributes} == keys_of("IOC")
    # a child reaches its adopted parent by the adopted uid, not by a new one
    assert db.get(Schema, at.type_uid(workspace, "Camera")).parent_schema_uid == \
        at.type_uid(workspace, "Equipment Item")


def test_somebody_elses_type_of_the_same_name_is_left_alone_and_reported(db, workspace):
    db.add(Schema(uid=f"{workspace}:mine", workspace_id=workspace, name="Camera",
                  applies_to="objects", parent_schema_uid=None,
                  attributes=[{"key": "lens_mount", "name": "Lens mount", "type": "string"}]))
    db.commit()
    result = at.ensure_asset_types(db, workspace)
    db.commit()
    assert result.duplicates == ["Camera"]
    mine = db.get(Schema, f"{workspace}:mine")
    assert mine.parent_schema_uid is None
    assert [a["key"] for a in mine.attributes] == ["lens_mount"]


# --- the catalogue has to describe what the importers actually store ---------

def run_import(db, ws):
    beamline = f"t{secrets.token_hex(3)}"
    values = yaml.safe_load(VALUES_TEMPLATE.replace("BEAMLINE", beamline))
    job = ImportJob(uid=f"job-{secrets.token_hex(4)}", workspace_id=ws, source="epik8s")
    db.add(job)
    db.commit()
    importer = _Importer(db, job, ws, "test@main:deploy/values.yaml")
    importer.ensure_types()
    importer.run(values, True)
    db.commit()
    return importer


def test_the_importer_adopts_the_typed_types_when_they_are_seeded_first(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    run_import(db, workspace)
    for name in ("Facility", "IOC", "Control Device", "Access Point", "Control Service"):
        found = db.query(Schema).filter(Schema.workspace_id == workspace, Schema.name == name).all()
        assert len(found) == 1, name
        assert found[0].uid == at.type_uid(workspace, name)


def test_every_key_the_importer_writes_is_declared_by_the_type_it_writes_to(db, workspace):
    from app.models.asset import Asset

    at.ensure_asset_types(db, workspace)
    db.commit()
    run_import(db, workspace)
    declared = {name: effective_keys(db, workspace, name)
                for name in ("Facility", "IOC", "Control Device", "Access Point", "Control Service")}
    undeclared = {}
    for asset in db.query(Asset).filter(Asset.workspace_id == workspace):
        missing = set(asset.attributes) - declared[asset.type]
        if missing:
            undeclared.setdefault(asset.type, set()).update(missing)
    assert not undeclared, undeclared


def test_seeded_after_the_importer_the_result_is_the_same(db, workspace):
    run_import(db, workspace)              # makes its own empty, epik8s-... types
    result = at.ensure_asset_types(db, workspace)
    db.commit()
    assert set(result.adopted) == {"Facility", "IOC", "Control Device", "Access Point",
                                   "Control Service"}
    for name in ("Facility", "IOC", "Control Device", "Access Point", "Control Service"):
        assert db.query(Schema).filter(Schema.workspace_id == workspace,
                                       Schema.name == name).count() == 1


# --- the rules that reach an object ---------------------------------------------

def test_a_real_pbs_code_passes_and_a_wrong_one_does_not(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    schema = db.get(Schema, at.type_uid(workspace, "RF Load"))
    from app.models.asset import Asset
    for code in ("INJ-A-ACC-SB3M-001", "INJ-A-ACC-SB1.5M-003", "MHX-R-RFX-XBND-003",
                 "MHX3-R-RF-LOAD-001"):
        assert not check_attributes(db, schema, {"pbs_code": code}, workspace, Asset,
                                    skip_unique=True), code
    assert check_attributes(db, schema, {"pbs_code": "not a code"}, workspace, Asset,
                            skip_unique=True)


def test_an_enumeration_rejects_a_value_it_does_not_list(db, workspace):
    at.ensure_asset_types(db, workspace)
    db.commit()
    schema = db.get(Schema, at.type_uid(workspace, "Ion Pump"))
    from app.models.asset import Asset
    assert not check_attributes(db, schema, {"argus_lifecycle": "In service"}, workspace, Asset,
                                skip_unique=True)
    assert check_attributes(db, schema, {"argus_lifecycle": "Very much alive"}, workspace, Asset,
                            skip_unique=True)


# --- through the REST API, as a beamline would use it -------------------------

client = TestClient(app)


@pytest.fixture()
def seeded(db, workspace):
    at.ensure_asset_types(db, workspace)
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=workspace, token_hash=hash_token(raw)))
    db.commit()
    return workspace, {"Authorization": f"Bearer {raw}"}


def make(ws, headers, type_name, prefix, attributes=None, name=None):
    uid = f"{prefix}-{secrets.token_hex(4)}"
    resp = client.post("/v1/assets", headers=headers, json={
        "uid": uid, "schema_uid": at.type_uid(ws, type_name),
        "key": f"{prefix.upper()}-{secrets.randbelow(10**7) + 10**6}",
        "name": name or type_name, "type": type_name, "attributes": attributes or {}})
    return uid, resp


def test_the_seeded_types_are_listed_and_an_object_of_one_can_be_made(seeded):
    ws, headers = seeded
    listed = client.get("/v1/schemas", headers=headers).json()
    assert len([s for s in listed if s["workspace_id"] == ws]) == 103
    _, resp = make(ws, headers, "Ion Pump", "pump", {
        "serial": "IPC-1234", "manufacturer": "Agilent", "pumping_speed": 55.0,
        "argus_lifecycle": "In service", "pbs_code": "INJ-A-VAC-PUMP-001"})
    assert resp.status_code == 201, resp.text


def test_an_object_of_a_seeded_type_is_held_to_the_types_rules(seeded):
    ws, headers = seeded
    _, bad_enum = make(ws, headers, "Ion Pump", "pump", {"argus_lifecycle": "Very much alive"})
    assert bad_enum.status_code == 422
    _, bad_code = make(ws, headers, "Ion Pump", "pump", {"pbs_code": "not a code"})
    assert bad_code.status_code == 422


def test_a_location_reference_accepts_a_rack_and_refuses_a_pump(seeded):
    ws, headers = seeded
    rack, made = make(ws, headers, "Rack", "rack")
    assert made.status_code == 201
    pump, _ = make(ws, headers, "Ion Pump", "pump")
    # Rack is a Place, and `Located in` accepts any Place descendant.
    _, ok = make(ws, headers, "Ion Pump", "pump", {"argus_location": rack})
    assert ok.status_code == 201, ok.text
    _, wrong = make(ws, headers, "Ion Pump", "pump", {"argus_location": pump})
    assert wrong.status_code == 422


def test_a_screen_station_is_composed_of_its_parts(seeded):
    ws, headers = seeded
    station, _ = make(ws, headers, "Screen Station", "flg",
                      {"screen_type": "YAG:Ce", "calibration_um_per_px": 16.67,
                       "insertion_positions": ["IN", "OUT"]})
    camera, _ = make(ws, headers, "Camera", "cam", {"interface": "GigE"})
    actuator, _ = make(ws, headers, "Actuator", "act", {"n_positions": 2})
    for part in (camera, actuator):
        resp = client.post("/v1/relations", headers=headers, json={
            "from_asset_uid": station, "to_asset_uid": part, "relation_type": "composed of"})
        assert resp.status_code == 201, resp.text
    edges = [r for r in client.get("/v1/relations", headers=headers).json()
             if r["from_asset_uid"] == station]
    assert {(e["to_asset_uid"], e["relation_type"]) for e in edges} == {
        (camera, "composed of"), (actuator, "composed of")}
