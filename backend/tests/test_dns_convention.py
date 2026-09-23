"""What a hostname says, by INFN's DNS naming convention, and what it does not.

The names are real ones from the four beamlines' configurations.
"""
import pytest

from app.services import dns_convention as dns


@pytest.mark.parametrize("name,prefix", [
    ("scsparcsipmxa001.lnf.infn.it", "sc"), ("scflameprmoxa001.lnf.infn.it", "sc"),
    ("scelimxa16001.int.eli-np.ro", "sc"), ("plsparcllrfs001.lnf.infn.it", "pl"),
    ("pwsparcco001", "pw"), ("vdflameprtpg001.lnf.infn.it", "vd"), ("cceuapscam28.lnf.infn.it", "cc"),
    ("bdsparcac1bpm001.lnf.infn.it", "bd"), ("ddcgicp006.lnf.infn.it", "dd"),
    ("SCSPARCMOXA002", "sc"),                                    # case does not matter
])
def test_the_class_prefix_is_read_from_the_first_label(name, prefix):
    assert dns.parse(name).prefix == prefix


@pytest.mark.parametrize("name", [
    "lel-mag-cpsu01.int.eli-np.ro",      # ELI's power supplies do not follow the convention
    "192.168.192.40", "", "k8sda.lnf.infn.it", "orbit",
])
def test_a_name_that_fits_no_class_is_unclassified_not_guessed(name):
    assert dns.parse(name) is None
    assert dns.it_equipment(name) is None


@pytest.mark.parametrize("name,kind", [
    ("scsparcsipmxa001.lnf.infn.it", "Serial converter"), ("cceuapscam28.lnf.infn.it", "Camera"),
    ("plsparcllrfs001.lnf.infn.it", "Host"), ("pwelimod001.int.eli-np.ro", "Host"),
    ("bdsparcac1bpm001.lnf.infn.it", "Instrument"), ("vdflameprtpg001.lnf.infn.it", "Instrument"),
    ("swsparccore001", "Unknown"),                                # a switch is not an endpoint of control
])
def test_an_endpoint_is_a_converter_a_camera_a_host_or_an_instrument_by_its_class(name, kind):
    assert dns.endpoint_kind(name)[0] == kind


def test_a_bare_ip_is_a_converter_only_on_the_evidence_of_a_port_in_moxas_range():
    kind, how = dns.endpoint_kind("192.168.192.40", 4001)
    assert kind == "Serial converter" and "4001-4999" in how
    assert dns.endpoint_kind("192.168.192.40", 502)[0] == "Unknown"       # Modbus TCP: an instrument
    assert dns.endpoint_kind("192.168.192.40", None)[0] == "Unknown"
    assert dns.endpoint_kind("192.168.192.40", "not a port")[0] == "Unknown"


@pytest.mark.parametrize("name,type_name,attrs", [
    ("scsparcsipmxa001.lnf.infn.it", "Serial Converter", {}),
    ("swsparccore001.lnf.infn.it", "Switch", {}),
    ("plsparcllrfs001.lnf.infn.it", "Server", {"is_virtual": False}),
    ("vlsparcdb001.lnf.infn.it", "Server", {"is_virtual": True}),
    ("dlsparcweb001.lnf.infn.it", "Server", {"is_virtual": True}),
    ("nssparcstorage001.lnf.infn.it", "Server", {"is_virtual": False, "role": "Storage"}),
    ("pwsparcco001.lnf.infn.it", "Workstation", {"workstation_role": "Operator console"}),
    ("plsparcmagnuc001.lnf.infn.it", "Workstation", {"workstation_role": "Operator console"}),
    ("pldanteco109.lnf.infn.it", "Workstation", {"workstation_role": "Operator console"}),
])
def test_only_network_equipment_becomes_it_equipment_and_a_console_is_a_workstation(name, type_name, attrs):
    found = dns.it_equipment(name)
    assert found[0] == type_name and found[1] == attrs
    assert "DNS naming convention" in found[2]


@pytest.mark.parametrize("name", [
    "cceuapscam28.lnf.infn.it",             # a camera keeps its Camera type
    "bdsparcac1bpm001.lnf.infn.it",         # an instrument keeps its own
    "ilsparcmag001.lnf.infn.it",            # a management controller is not a box of its own here
])
def test_a_camera_an_instrument_or_a_management_controller_is_not_it_equipment(name):
    assert dns.parse(name) is not None and dns.it_equipment(name) is None
