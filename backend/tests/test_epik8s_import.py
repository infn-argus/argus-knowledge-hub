"""Importing a beamline's control configuration.

Two things carry the weight. That an address in the configuration resolves
to the equipment the inventory already holds rather than to a second copy
of it — the Moxa has a purchase order and a location, and a duplicate
splits its history in two. And that where the answer is not certain, the
import says so instead of choosing: a wrong edge in a knowledge graph is
worse than a missing one, because somebody draws a conclusion from it.
"""
import secrets

import pytest
import yaml

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset, Relation
from app.models.import_job import ImportJob
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.epik8s_import import _Importer, _pv_prefix
from app.services.network_resolve import NetworkIndex

VALUES_TEMPLATE = """
beamline: BEAMLINE
namespace: sparc
giturl: https://baltig.infn.it/lnf-da-control/epik8-sparc.git
iocDefaults:
  agilent-vac:
    devgroup: vac
    devtype: ipcmini
    asset: https://confluence.infn.it/x/nYD8DQ
epicsConfiguration:
  services:
    archiver:
      desc: EPICS Archiver Appliance for SPARC
      charturl: https://example/archiver.git
    scanserver:
      disable: true
  iocs:
    - name: vac-gunvpc
      iocprefix: SPARC:VAC
      iocroot: GUNVPC
      template: agilent-vac
      zones:
        - LINAC
        - GUN
      iocparam:
        - name: server
          value: scsparcsipmxa001.lnf.infn.it
        - name: port
          value: 4003
      devices:
        - name: GUNSIP01
          channel: 146
          interlock: true
        - name: GUNSIP02
          channel: 147
    - name: vac-kly01vpc
      iocprefix: SPARC:VAC
      iocroot: KLY1VPC
      template: agilent-vac
      iocparam:
        - name: server
          value: scsparcsipmxa001.lnf.infn.it
        - name: port
          value: 4001
      devices:
        - name: W1KSIP03
          channel: 153
    - name: eeips-dvl671
      iocprefix: BTF:MAG:EEI
      devgroup: mag
      devices:
        - name: DHPTB102
          ip: 192.168.190.157
          port: 502
"""


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def beamline():
    """Object keys are unique installation-wide and are derived from the
    beamline, so each test imports a beamline of its own."""
    return f"t{secrets.token_hex(3)}"


@pytest.fixture()
def workspace():
    """A workspace whose inventory already holds the Moxa, twice over: as a
    Converter (the box) and as a Registered Node (its address)."""
    ws = f"epik-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Divisione"))
    db.flush()
    db.add(Schema(uid=f"{ws}:net", workspace_id=ws, name="Converter", applies_to="objects"))
    db.add(Schema(uid=f"{ws}:reg", workspace_id=ws, name="Registered Nodes",
                  applies_to="objects"))
    db.flush()
    db.add(Asset(uid=f"{ws}-moxa", workspace_id=ws, schema_uid=f"{ws}:net",
                 key=f"LNFMAC-{secrets.randbelow(900000) + 100000}",
                 name="scsparcsipmxa001", type="Converter",
                 attributes={"ip": "192.168.192.21"}))
    db.add(Asset(uid=f"{ws}-reg", workspace_id=ws, schema_uid=f"{ws}:reg",
                 key=f"LNFMAC-{secrets.randbelow(900000) + 100000}",
                 name="scsparcsipmxa001", type="Registered Nodes",
                 attributes={"hostname": "scsparcsipmxa001", "ip": "192.168.192.21"}))
    db.commit()
    db.close()
    return ws


def run(ws, beamline, create_missing=True):
    values = yaml.safe_load(VALUES_TEMPLATE.replace("BEAMLINE", beamline))
    db = SessionLocal()
    job = ImportJob(uid=f"job-{secrets.token_hex(4)}", workspace_id=ws, source="epik8s")
    db.add(job)
    db.commit()
    importer = _Importer(db, job, ws, "test@main:deploy/values.yaml")
    importer.ensure_types()
    importer.run(values, create_missing)
    db.commit()
    return db, job, importer


def assets_of(db, ws, type_name):
    return {a.name: a for a in db.query(Asset).filter(
        Asset.workspace_id == ws, Asset.type == type_name)}


# --- resolving addresses ------------------------------------------------

def test_a_hostname_resolves_to_the_equipment_not_to_its_address_record(workspace, beamline):
    """Both a Converter and a Registered Node answer to this name. The fault
    will be about the Converter."""
    db, _job, importer = run(workspace, beamline)
    moxa = db.get(Asset, f"{workspace}-moxa")
    reached = [
        r for r in db.query(Relation).filter(Relation.workspace_id == workspace,
                                             Relation.relation_type == "connects to")
    ]
    assert reached, "the IOC should connect to something"
    assert all(r.to_asset_uid == moxa.uid for r in reached)
    db.close()


def test_the_fully_qualified_name_matches_the_short_one(workspace, beamline):
    """The configuration writes scsparcsipmxa001.lnf.infn.it; the inventory
    writes scsparcsipmxa001. Same host."""
    db, _job, importer = run(workspace, beamline)
    assert importer.counts["access_points_linked"] >= 2
    db.close()


def test_two_iocs_on_one_terminal_server_reach_the_same_object(workspace, beamline):
    """The edge the whole import exists for: when this Moxa dies, both
    vacuum IOCs go with it, and nothing else records that."""
    db, _job, _importer = run(workspace, beamline)
    moxa = db.get(Asset, f"{workspace}-moxa")
    connected = {
        db.get(Asset, r.from_asset_uid).name
        for r in db.query(Relation).filter(
            Relation.workspace_id == workspace,
            Relation.to_asset_uid == moxa.uid,
            Relation.relation_type == "connects to",
        )
    }
    assert connected == {"vac-gunvpc", "vac-kly01vpc"}
    db.close()


def test_devices_reach_through_whatever_their_ioc_connects_to(workspace, beamline):
    db, _job, _importer = run(workspace, beamline)
    moxa = db.get(Asset, f"{workspace}-moxa")
    through = {
        db.get(Asset, r.from_asset_uid).name
        for r in db.query(Relation).filter(
            Relation.workspace_id == workspace,
            Relation.to_asset_uid == moxa.uid,
            Relation.relation_type == "reached through",
        )
    }
    assert {"GUNSIP01", "GUNSIP02", "W1KSIP03"} <= through
    db.close()


def test_an_address_nothing_carries_becomes_an_object_to_confirm(workspace, beamline):
    """192.168.190.157 is in no inventory record. Inventing it silently
    would be wrong; leaving the gap invisible would be worse."""
    db, _job, importer = run(workspace, beamline)
    created = assets_of(db, workspace, "Access Point")
    assert "192.168.190.157" in created
    assert importer.counts["access_points_created"] == 1
    assert "Confirm what this is" in created["192.168.190.157"].attributes["argus_provenance"]
    db.close()


def test_with_creation_off_the_gap_is_only_reported(workspace, beamline):
    db, job, importer = run(workspace, beamline, create_missing=False)
    assert assets_of(db, workspace, "Access Point") == {}
    assert importer.counts["addresses_unresolved"] == 1
    assert any("192.168.190.157" in w for w in job.warnings)
    db.close()


def test_an_ambiguous_address_is_reported_and_not_linked(workspace, beamline):
    """Two Converters with the same address is a data problem, and the
    import must not resolve it by picking one."""
    db = SessionLocal()
    db.add(Asset(uid=f"{workspace}-moxa2", workspace_id=workspace, schema_uid=f"{workspace}:net",
                 key=f"LNFMAC-{secrets.randbelow(900000) + 100000}",
                 name="scsparcsipmxa001", type="Converter", attributes={}))
    db.commit()
    db.close()

    db, job, importer = run(workspace, beamline, create_missing=False)
    assert importer.counts["access_points_linked"] == 0
    assert any("more than one object" in w for w in job.warnings)
    db.close()


# --- what comes out -----------------------------------------------------

def test_the_pv_name_is_composed_the_way_the_chart_composes_it():
    ioc = {"iocprefix": "SPARC:VAC", "iocroot": "GUNVPC"}
    assert _pv_prefix(ioc, "GUNSIP01") == "SPARC:VAC:GUNVPC:GUNSIP01"
    assert _pv_prefix({"iocprefix": "BTF:MAG:EEI"}, "DHPTB102") == "BTF:MAG:EEI:DHPTB102"


def test_a_device_carries_the_settings_a_fault_turns_out_to_be_about(workspace, beamline):
    db, _job, _importer = run(workspace, beamline)
    pump = assets_of(db, workspace, "Control Device")["GUNSIP01"]
    assert pump.attributes["pv_prefix"] == "SPARC:VAC:GUNVPC:GUNSIP01"
    assert pump.attributes["channel"] == 146
    assert pump.attributes["interlock"] is True
    assert pump.attributes["system"] == "vac", "from the template, for tickets to match on"
    assert pump.attributes["zones"] == ["LINAC", "GUN"], "inherited from its IOC"
    db.close()


def test_a_disabled_service_is_not_imported_as_if_it_ran(workspace, beamline):
    db, _job, _importer = run(workspace, beamline)
    services = assets_of(db, workspace, "Control Service")
    assert f"archiver ({beamline.upper()})" in services
    assert f"scanserver ({beamline.upper()})" not in services
    db.close()


def test_an_ioc_with_no_inventory_link_is_reported_as_the_gap_it_is(workspace, beamline):
    db, job, _importer = run(workspace, beamline)
    assert any("eeips-dvl671" in w and "no `asset:`" in w for w in job.warnings)
    db.close()


def test_running_it_twice_changes_nothing(workspace, beamline):
    """The configuration is re-imported on every commit; a second run must
    update rows, not double them."""
    db, _job, _importer = run(workspace, beamline)
    first = db.query(Asset).filter(Asset.workspace_id == workspace).count()
    edges = db.query(Relation).filter(Relation.workspace_id == workspace).count()
    db.close()

    db, _job, _importer = run(workspace, beamline)
    assert db.query(Asset).filter(Asset.workspace_id == workspace).count() == first
    assert db.query(Relation).filter(Relation.workspace_id == workspace).count() == edges
    db.close()


def test_everything_says_where_it_came_from(workspace, beamline):
    """The file in git deploys the accelerator; the hub only mirrors it, and
    each row has to admit that."""
    db, _job, _importer = run(workspace, beamline)
    ioc = assets_of(db, workspace, "IOC")["vac-gunvpc"]
    assert ioc.attributes["argus_source"] == "epik8s"
    assert ioc.attributes["argus_source_ref"] == "test@main:deploy/values.yaml"
    db.close()


def test_a_bus_id_is_not_mistaken_for_a_network_address(workspace, beamline):
    """`id` means two things: where a camera is (192.168.189.79) and which
    unit on a serial bus a magnet supply is (5). Read as a host, the second
    invents an Access Point called "5" that unrelated magnets share."""
    values = yaml.safe_load(f"""
beamline: {beamline}
epicsConfiguration:
  iocs:
    - name: ocem-a
      iocprefix: BTF:MAG
      devices:
        - name: DHPTT001
          id: 5
    - name: ocem-b
      iocprefix: BTF:MAG
      devices:
        - name: DHPTT011
          id: 5
    - name: cam
      iocprefix: BTF:CAM
      devices:
        - name: CAM01
          id: 192.168.189.79
""")
    db = SessionLocal()
    job = ImportJob(uid=f"job-{secrets.token_hex(4)}", workspace_id=workspace, source="epik8s")
    db.add(job)
    db.commit()
    importer = _Importer(db, job, workspace, "test")
    importer.ensure_types()
    importer.run(values, True)
    db.commit()

    points = assets_of(db, workspace, "Access Point")
    assert "5" not in points, "a bus id is not a host"
    assert "192.168.189.79" in points
    db.close()


def test_reaching_an_address_this_run_invented_is_not_counted_as_a_match(workspace, beamline):
    """Two IOCs behind one unknown host: the first creates an Access Point,
    the second finds it. Counting the second as "matched to existing
    equipment" made an import that matched nothing report that it had."""
    values = yaml.safe_load(f"""
beamline: {beamline}
epicsConfiguration:
  iocs:
    - name: a
      iocprefix: X:A
      iocparam:
        - name: server
          value: nowhere.lnf.infn.it
      devices:
        - name: D1
    - name: b
      iocprefix: X:B
      iocparam:
        - name: server
          value: nowhere.lnf.infn.it
      devices:
        - name: D2
""")
    db = SessionLocal()
    job = ImportJob(uid=f"job-{secrets.token_hex(4)}", workspace_id=workspace, source="epik8s")
    db.add(job)
    db.commit()
    importer = _Importer(db, job, workspace, "test")
    importer.ensure_types()
    importer.run(values, True)
    db.commit()

    assert importer.counts["access_points_created"] == 1
    assert importer.counts["access_points_reused"] == 1
    assert importer.counts["access_points_linked"] == 0, \
        "nothing in the inventory carried this address"
    db.close()
