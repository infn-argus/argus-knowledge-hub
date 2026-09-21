"""Reading a control configuration as equipment.

The tests worth having are about the readings that could be wrong in a way
nobody notices: a bus id read as an address, a terminal server read as a
direct connection, a device rated from its IOC when it overrides the
rating, and anything classified by guesswork instead of by a template.
"""
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from epik8s_devices.catalogue import Kind, classify, load_templates  # noqa: E402
from epik8s_devices.elements import element_of  # noqa: E402
from epik8s_devices.match import Inventory  # noqa: E402
from epik8s_devices.scan import scan  # noqa: E402

TEMPLATES = {
    "ocem": ("ps", "ocem"),
    "agilent-vac": ("vac", "agilent"),
    "motor": ("motor", None),
    "smc": ("cooling", "smc"),
}

VALUES = yaml.safe_load("""
beamline: sparc
iocDefaults:
  agilent-vac:
    devgroup: vac
    devtype: ipcmini
    devfunc: ion
    template: agilent-vac
epicsConfiguration:
  iocs:
    - name: vac-gunvpc
      iocprefix: SPARC:VAC
      iocroot: GUNVPC
      template: agilent-vac
      zones: [LINAC, GUN]
      iocparam:
        - name: server
          value: scsparcsipmxa001.lnf.infn.it
        - name: port
          value: 4003
      devices:
        - name: GUNSIP01
          channel: 146
          interlock: true
    - name: ocem-dvl644
      iocprefix: BTF:MAG:OCEME642
      template: ocem
      devgroup: mag
      devtype: E642
      ps:
        current: {max: 650}
        voltage: {max: 40}
      devices:
        - name: QUATB002
          id: 5
          ps:
            polarity: {mode: unipolar, sign: positive}
            current: {max: 120}
    - name: chiller-smc
      iocprefix: SPARC:CHL
      template: smc
      devgroup: cool
      devices:
        - name: CHLGUN01
          server: scsparcchlmxa001.lnf.infn.it
          port: 4001
    - name: cam
      iocprefix: BTF:CAM
      devices:
        - name: CAM01
          id: 192.168.189.79
""")


@pytest.fixture()
def devices():
    return {d.name: d for d in scan(VALUES, TEMPLATES, source="test")}


# --- what the equipment is ----------------------------------------------

def test_the_class_and_vendor_come_from_the_ibek_template_tree(devices):
    pump = devices["GUNSIP01"]
    assert (pump.device_class, pump.vendor, pump.model) == ("Vacuum", "Agilent", "IPCMini")
    assert pump.classified_from.startswith("ibek:templates/vac/agilent/")


def test_a_template_nobody_has_is_left_unclassified_rather_than_guessed():
    """An unknown device that says so gets filled in; one labelled "Power
    Supply" because it sat in the mag group is a wrong answer that looks
    right."""
    kind = classify("nothing-like-this", "mystery", None, TEMPLATES)
    assert kind == Kind(source="unknown")


def test_an_unclassified_device_says_what_it_needs(devices):
    assert any("device class" in n for n in devices["CAM01"].needs)


# --- what it acts on ----------------------------------------------------

def test_the_element_is_read_from_the_name(devices):
    assert devices["QUATB002"].element == "Quadrupole"
    assert devices["GUNSIP01"].element == "Ion pump"
    assert devices["GUNSIP01"].element_read_from == "SIP"


def test_a_name_that_matches_no_convention_gets_no_element():
    assert element_of("PLAVOLT01") is None
    assert element_of("") is None


# --- how it is reached --------------------------------------------------

def test_a_bus_id_is_not_read_as_an_address(devices):
    """`id: 5` is which unit on a serial bus, not where it is."""
    assert devices["QUATB002"].connection.get("host") is None
    assert devices["QUATB002"].connection["bus_id"] == 5


def test_an_ip_on_a_camera_is_read_as_one(devices):
    assert devices["CAM01"].connection == {"host": "192.168.189.79", "via": "direct"}


def test_a_server_is_a_terminal_server_even_when_written_on_the_device(devices):
    """The chillers put a Moxa on each device rather than on the IOC. It is
    still something they are reached through, not their own address."""
    chiller = devices["CHLGUN01"]
    assert chiller.connection["via"] == "terminal server"
    assert chiller.connection["host"] == "scsparcchlmxa001.lnf.infn.it"


def test_the_terminal_server_and_port_carry_down_from_the_ioc(devices):
    pump = devices["GUNSIP01"]
    assert pump.connection["host"] == "scsparcsipmxa001.lnf.infn.it"
    assert pump.connection["port"] == "4003"
    assert pump.connection["channel"] == 146


# --- the rating ---------------------------------------------------------

def test_a_device_overrides_its_ioc_rating_field_by_field(devices):
    """ps-schema.yaml is explicit: a supply may differ in polarity while
    sharing the line's voltage limit."""
    spec = devices["QUATB002"].model_spec["ps"]
    assert spec["current"]["max"] == 120, "the device's own rating wins"
    assert spec["voltage"]["max"] == 40, "and it still inherits the rest"
    assert spec["polarity"]["mode"] == "unipolar"


def test_the_pv_is_composed_the_way_the_chart_composes_it(devices):
    assert devices["GUNSIP01"].pv == "SPARC:VAC:GUNVPC:GUNSIP01"


def test_zones_fall_back_to_the_ioc(devices):
    assert devices["GUNSIP01"].zones == ["LINAC", "GUN"]


# --- proposing a physical asset -----------------------------------------

def test_a_device_is_matched_to_the_object_with_its_name():
    inventory = Inventory([
        {"uid": "a1", "key": "LNFMAC-1", "name": "QUATB002", "type": "Magnets",
         "attributes": {}},
    ])
    proposal = inventory.for_device({"name": "QUATB002", "connection": {}})
    assert proposal["uid"] == "a1" and proposal["matched_on"] == "name"


def test_a_shared_terminal_server_does_not_make_two_pumps_the_same_box():
    """Matching on a terminal server's address would say every device
    behind it is that device."""
    inventory = Inventory([
        {"uid": "moxa", "key": "LNFMAC-9", "name": "scsparcsipmxa001",
         "type": "Converter", "attributes": {"ip": "192.168.192.21"}},
    ])
    proposal = inventory.for_device({
        "name": "GUNSIP01",
        "connection": {"host": "scsparcsipmxa001.lnf.infn.it", "via": "terminal server"},
    })
    assert proposal == {}


def test_a_directly_addressed_device_is_matched_on_its_address():
    inventory = Inventory([
        {"uid": "cam", "key": "LNFMAC-7", "name": "btfcam01", "type": "Cameras",
         "attributes": {"ip": "192.168.189.79"}},
    ])
    proposal = inventory.for_device({
        "name": "CAM01", "connection": {"host": "192.168.189.79", "via": "direct"},
    })
    assert proposal["uid"] == "cam" and proposal["matched_on"] == "address"


def test_equipment_is_preferred_over_the_record_of_its_address():
    inventory = Inventory([
        {"uid": "lease", "key": "L-1", "name": "node", "type": "DHCP Nodes",
         "attributes": {"ip": "192.168.189.79"}},
        {"uid": "cam", "key": "L-2", "name": "camera", "type": "Cameras",
         "attributes": {"ip": "192.168.189.79"}},
    ])
    proposal = inventory.for_device({
        "name": "CAM01", "connection": {"host": "192.168.189.79", "via": "direct"},
    })
    assert proposal["uid"] == "cam"


def test_two_candidates_are_reported_rather_than_chosen_between():
    inventory = Inventory([
        {"uid": "a", "key": "L-1", "name": "QUATB002", "type": "Magnets", "attributes": {}},
        {"uid": "b", "key": "L-2", "name": "QUATB002", "type": "Linac assets", "attributes": {}},
    ])
    proposal = inventory.for_device({"name": "QUATB002", "connection": {}})
    assert "uid" not in proposal
    assert len(proposal["ambiguous"]) == 2


def test_the_real_template_tree_is_read_when_it_is_there():
    root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                        "infn-epics-ioc", "ibek-templates")
    if not os.path.isdir(root):
        pytest.skip("ibek-templates not checked out beside this repository")
    templates = load_templates(root)
    assert templates.get("ocem") == ("ps", "ocem")
    assert templates.get("agilent-vac") == ("vac", "agilent")
    assert "day-accumulator" not in templates, "global fragments are not devices"


# `epicsConfiguration.iocs` is a list in some repositories and a mapping keyed
# by IOC name in the ones that moved on. Read as a list, a mapping yields no
# devices and no error.

def _as_mapping(values, keep_names=True):
    out = yaml.safe_load(yaml.safe_dump(values))
    out["epicsConfiguration"]["iocs"] = {
        e["name"]: (e if keep_names else {k: v for k, v in e.items() if k != "name"})
        for e in values["epicsConfiguration"]["iocs"]
    }
    return out


def test_iocs_written_as_a_mapping_give_the_same_devices():
    listed = scan(VALUES, TEMPLATES)
    mapped = scan(_as_mapping(VALUES), TEMPLATES)
    assert listed and len(mapped) == len(listed)
    assert [(d.key, d.ioc, d.name) for d in mapped] == [(d.key, d.ioc, d.name) for d in listed]


def test_a_mapping_entry_without_a_name_is_called_what_its_key_is():
    mapped = scan(_as_mapping(VALUES, keep_names=False), TEMPLATES)
    assert {d.ioc for d in mapped} == {d.ioc for d in scan(VALUES, TEMPLATES)}
