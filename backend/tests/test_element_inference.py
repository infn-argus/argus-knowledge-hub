"""Reading control channels back into what they drive.

The cases are names and metadata as they appear in the SPARC, BTF, EuAPS and ELI
configurations. What is worth pinning is the judgement calls: a NEG pump on an
ion-pump controller, a simulated camera, a magnet supply whose name says nothing,
and a dipole code hiding inside a longer word.
"""
import os

import pytest
import yaml

from app.services import asset_types as at
from app.services.element_inference import (
    ASSET_TYPES, ELEMENT_TYPES, infer_device, infer_ioc,
)
from app.services.epik8s_import import _ioc_entries

VAC = {"name": "vac", "template": "agilent-vac", "devgroup": "vac", "devfunc": "ion", "devtype": "ipcmini"}
MAG = {"name": "mag", "template": "caenels", "devgroup": "mag", "devtype": "histar"}
CAM = {"name": "cam", "template": "adcamera", "devgroup": "cam", "devtype": "camera"}


def asset_of(ioc, name, **device):
    found = infer_device(ioc, {"name": name, **device})
    return found.asset_type if found else None


# --- vacuum ------------------------------------------------------------------------------

@pytest.mark.parametrize("ioc,name,expected", [
    (VAC, "GUNSIP01", "Ion Pump"),                                   # SPARC
    (VAC, "W1KSIP03", "Ion Pump"),                                   # the code is not first
    (VAC, "GUNNEG01", "NEG Cartridge"),           # a channel of an `ion` controller: the name decides
    ({**VAC, "devfunc": "turbo", "devtype": "twistorr305"}, "FI31TRB01", "Turbo Pump"),     # EuAPS
    ({"template": "pfeiffer-hiscroll6", "devgroup": "vac", "devfunc": "scroll"}, "FP31PRY01", "Primary Pump"),
    ({"template": "pfeiffer-tpg", "devgroup": "vac", "devfunc": "pig", "devtype": "tpg366"}, "FP31VUG01", "Vacuum Gauge"),
    ({"template": "pfeiffer-tpg", "devgroup": "vac", "devfunc": "pig"}, "AC1VGA01", "Vacuum Gauge"),
    ({"template": "agilent-vac", "devgroup": "vac", "devtype": "4uhv"}, "WGS01IONP01", "Ion Pump"),   # ELI
    ({"template": "agilent-vac", "devgroup": "vac", "devtype": "img"}, "CC08", "Vacuum Gauge"),        # ELI
    ({"template": "agilent-vac", "devgroup": "vac", "devfunc": "turbo"}, "ODDNAME", "Turbo Pump"),     # only the function says
    ({"template": "agilent-vac", "devgroup": "vac"}, "ODDNAME", None),      # nothing says: not guessed
])
def test_a_vacuum_channel_is_the_pump_or_gauge_it_drives(ioc, name, expected):
    assert asset_of(ioc, name) == expected


def test_a_turbo_pump_carries_the_product_it_is_and_an_ion_pump_does_not():
    turbo = infer_device({**VAC, "devfunc": "turbo", "devtype": "twistorr305"}, {"name": "FI31TRB01"})
    assert (turbo.asset_attrs["manufacturer"], turbo.asset_attrs["model"]) == ("Agilent", "TwisTorr 305")
    ion = infer_device(VAC, {"name": "GUNSIP01"})
    assert "manufacturer" not in ion.asset_attrs          # IPCMini is the controller, not the pump


# --- magnets ---------------------------------------------------------------------------------

@pytest.mark.parametrize("name,element,plane", [
    ("GUNQUA01", "Quadrupole", None), ("QUATB002", "Quadrupole", None),      # SPARC, BTF
    ("GUNQSK01", "Quadrupole", None),                                          # skew
    ("DPLSOL01", "Solenoid", None), ("SBNSEX01", "Sextupole", None),
    ("AC1VCR1A", "Corrector", "V"), ("GUNHCR01", "Corrector", "H"),
    ("CHHTM001", "Corrector", "H"), ("CVVTB002", "Corrector", "V"),
    ("HCOR01", "Corrector", "H"), ("VCOR06", "Corrector", "V"),                # ELI
    ("DHPTT001", "Dipole", None), ("DHSTB001", "Dipole", None), ("PTLDPL01", "Dipole", None),
    ("DIP01", "Dipole", None),                                                 # ELI
])
def test_a_magnet_supply_is_also_the_element_its_name_says(name, element, plane):
    found = infer_device(MAG, {"name": name})
    assert found.asset_type == "Power Supply" and found.element_type == element
    assert found.element_name == name.upper()
    assert found.element_attrs.get("plane") == plane
    assert found.element_attrs["lattice_name"] == name.upper()


def test_a_dipole_code_inside_a_longer_word_is_not_a_dipole():
    found = infer_device(MAG, {"name": "XDHPRODUCT"})
    assert found.asset_type == "Power Supply" and found.element_type is None


def test_a_supply_whose_name_says_nothing_is_still_a_supply_and_no_element_is_made_up():
    found = infer_device({**MAG, "template": "caenelsfast"}, {"name": "PS"})
    assert found.asset_type == "Power Supply" and found.element_type is None and found.element_name is None


def test_a_supplys_limits_come_from_the_ps_block_the_channels_own_over_its_iocs():
    ioc = {**MAG, "ps": {"current": {"max": 100}, "voltage": {"max": 25}}}
    plain = infer_device(ioc, {"name": "QUATM001"}).asset_attrs
    assert (plain["current_max"], plain["voltage_max"]) == (100.0, 25.0)
    own = infer_device(ioc, {"name": "DHSTB002", "ps": {"current": {"max": 700}}}).asset_attrs
    assert (own["current_max"], own["voltage_max"]) == (700.0, 25.0)    # its own current, its unit's voltage
    bipolar = infer_device({**MAG, "ps": {"polarity": {"mode": "bipolar-native"}}}, {"name": "DHPTB101"})
    assert bipolar.asset_attrs["bipolar"] is True


def test_a_supply_says_who_made_it_where_the_template_is_the_product():
    assert infer_device(MAG, {"name": "GUNQUA01"}).asset_attrs["manufacturer"] == "CAEN ELS"
    ocem = infer_device({"template": "ocem", "devgroup": "mag", "devtype": "E642"}, {"name": "QUATB002"})
    assert (ocem.asset_attrs["manufacturer"], ocem.asset_attrs["model"]) == ("OCEM", "E642")


# --- cameras ---------------------------------------------------------------------------------------

def test_a_camera_says_who_made_it_when_its_devtype_does():
    found = infer_device({**CAM, "devtype": "Basler-scA640-70gm"}, {"name": "AC101"})
    assert found.asset_type == "Camera"
    assert (found.asset_attrs["manufacturer"], found.asset_attrs["model"]) == ("Basler", "scA640-70gm")
    assert "manufacturer" not in infer_device(CAM, {"name": "FI8-CAM-06"}).asset_attrs


@pytest.mark.parametrize("ioc,name", [({**CAM, "devtype": "camerasim"}, "SIM01"), (CAM, "SIM01")])
def test_a_simulated_camera_is_not_hardware(ioc, name):
    assert infer_device(ioc, {"name": name}) is None


# --- IOCs that are one unit -------------------------------------------------------------------------

def test_a_bpm_ioc_is_a_beam_position_monitor_and_the_electronics_that_realise_it():
    found = infer_ioc({"name": "ac1bpm01", "template": "libera-sppp", "iocprefix": "AC1BPM01"})
    assert (found.element_type, found.element_name, found.asset_type) == ("Beam Position Monitor", "AC1BPM01", "Digitizer")
    assert found.asset_attrs["model"] == "Libera Single Pass"
    assert found.element_attrs["lattice_name"] == "AC1BPM01"


@pytest.mark.parametrize("ioc,expected", [
    ({"name": "llrfs01", "template": "libera-llrf"}, "Low-Level RF Unit"),           # SPARC
    ({"name": "llrf", "template": "libera-llrf2", "devtype": "llrf"}, "Low-Level RF Unit"),   # ELI
    ({"name": "ppt-mod1", "template": "ppt", "devgroup": "modulator"}, "Modulator"),
    ({"name": "k400-mod1", "template": "scandinova-mod-k400"}, "Modulator"),
])
def test_an_llrf_or_modulator_ioc_is_the_unit(ioc, expected):
    assert infer_ioc(ioc).asset_type == expected


@pytest.mark.parametrize("ioc", [
    {"name": "orbit", "devtype": "softioc", "devgroup": "diag"},
    {"name": "rf-conditioning-gun", "devtype": "softioc", "devgroup": "rf"},   # software, not a unit
    {"name": "cams", "template": "adcamera", "devgroup": "cam"},
])
def test_an_ioc_that_is_software_or_a_group_of_devices_is_not_a_unit(ioc):
    assert infer_ioc(ioc) is None


# --- what is deliberately left alone --------------------------------------------------------------------

@pytest.mark.parametrize("ioc,name", [
    ({"template": "icpdas", "devgroup": "io", "devtype": "rtd"}, "SLD01"),
    ({"template": "tektronix", "devgroup": "diag", "devtype": "channel"}, "AC1BCM01"),   # a scope channel, not a BCM
    ({"template": "mrf-pci-230", "devgroup": "timing"}, "EVR-RFD"),
])
def test_channels_no_rule_covers_are_none_not_a_guess(ioc, name):
    assert infer_device(ioc, {"name": name}) is None


def test_every_type_the_rules_write_is_in_the_catalogue_and_is_shared_or_the_machines_own():
    for name in (*ASSET_TYPES, *ELEMENT_TYPES):
        assert name in at.BY_NAME, name
    assert all(at.scope_of(n) == "global" for n in ASSET_TYPES)          # a shared inventory
    assert all(at.scope_of(n) == "beamline" for n in ELEMENT_TYPES)      # a machine's own lattice


# --- motors ------------------------------------------------------------------------------------------------

MOTOR = {"name": "tml-ch1", "template": "motor", "devtype": "technosoft-asyn"}


def test_a_motor_channel_is_an_axis_whatever_its_name():
    found = infer_device(MOTOR, {"name": "GUNSOLH1", "axid": 2})
    assert (found.asset_type, found.asset_attrs["axis_id"], found.element_type) == ("Motor Axis", "2", None)
    assert infer_device(MOTOR, {"name": "m0", "axid": 0}).asset_attrs["axis_id"] == "0"   # zero is an axis


def test_the_template_decides_that_it_is_a_motor_not_the_group():
    assert infer_device({**MOTOR, "devgroup": "rf"}, {"name": "m0"}).asset_type == "Motor Axis"


@pytest.mark.parametrize("name", ["GUNFLG01", "AC1FLG01", "FELFLG03A", "TESTFLG"])
def test_a_flag_is_a_screen_driven_by_an_actuator(name):
    found = infer_device(MOTOR, {"name": name, "poi": [{"name": "YAG", "value": 1}, {"name": "OUT", "value": 0}]})
    assert (found.asset_type, found.element_type, found.element_name) == ("Actuator", "Screen Station", name)
    assert found.element_link == "composed of"
    assert found.element_attrs["insertion_positions"] == ["YAG", "OUT"]


@pytest.mark.parametrize("name,element,plane,attrs", [
    ("FI4-HMN-01", "FI4-MMIR-001", "horizontal", {"beam": "main"}),
    ("FI4-VMN-01", "FI4-MMIR-001", "vertical", {"beam": "main"}),
    ("FI8-HMN-02", "FI8-MMIR-002", "horizontal", {"beam": "main"}),          # the second mirror of the area
    ("FI1-HPB-01", "FI1-PMIR-001", "horizontal", {"beam": "probe"}),
    ("FP1-VMN-01", "FP1-MMIR-001", "vertical", {"beam": "main"}),
    ("FI3-MMR-001", "FI3-MMIR-001", "rotation", {"beam": "main"}),           # the main mirror's third axis
    ("FI8-PRH-01", "FI8-PAR-001", "horizontal", {"mirror_kind": "Parabolic"}),
    ("FI8-PRV-01", "FI8-PAR-001", "vertical", {"mirror_kind": "Parabolic"}),
])
def test_an_axis_of_a_mirror_belongs_to_the_mirror_the_utility_matrix_names(name, element, plane, attrs):
    found = infer_device(MOTOR, {"name": name, "axid": 1})
    assert (found.asset_type, found.element_type, found.element_name) == ("Motor Axis", "Mirror", element)
    assert found.element_link == "composed of" and found.element_attrs == attrs
    assert f"{plane} axis" in found.why and "Utility Matrix" in found.why


@pytest.mark.parametrize("name", [
    "FI2-MPB-001", "FI2-MPB-002",             # the probe delay line and in/out stage in the matrix
    "FI8-SLT-01", "FP4-SLT-001", "FI8-HEX-01", "FI8-DIP-01", "FI8-PBM-01",   # EuAPS: "slitte?"
    "CMBTHV01", "CMBEOS01", "CMBPLV01", "SBNROT01",     # SPARC: a YAG among their positions, but not flags
    "SLTTB004L", "SCN01:MOT01",
])
def test_an_axis_whose_code_does_not_say_what_it_moves_gets_no_element(name):
    found = infer_device(MOTOR, {"name": name, "poi": [{"name": "YAG", "value": 1}]})
    assert found.asset_type == "Motor Axis" and found.element_type is None


# --- the plant: chillers and timing ----------------------------------------------------------------------------

CHILLERS = {"name": "chiller-smc", "template": "smc", "devgroup": "cool"}


@pytest.mark.parametrize("name,element,element_name", [
    ("CHLGUN01", "RF Gun", "GUN"),                       # SPARC
    ("CHLAC101", "Accelerating Structure", "AC1"),       # the first section, not a hundred and first
    ("CHLAC301", "Accelerating Structure", "AC3"),
    ("CHLRFD01", "RF Deflector", "RFD"),
    ("GUN", "RF Gun", "GUN"),                            # ELI names it plain
    ("ACC02", "Accelerating Structure", "ACC02"),
])
def test_a_chiller_channel_is_a_chiller_and_the_element_it_cools(name, element, element_name):
    found = infer_device(CHILLERS, {"name": name})
    assert (found.asset_type, found.element_type, found.element_name) == ("Chiller", element, element_name)
    assert found.element_link == "cools" and found.asset_to_element is True
    assert found.asset_attrs["argus_system"] == "Cooling"


@pytest.mark.parametrize("name", ["CHLBOC01", "CHLBOC02", "CHLSLS01"])
def test_a_chiller_whose_target_the_rules_do_not_know_is_a_chiller_and_no_guessed_element(name):
    found = infer_device(CHILLERS, {"name": name})
    assert found.asset_type == "Chiller" and found.element_type is None and found.cools_type is None
    assert "names no cooled object" in found.why


def test_the_modulator_hall_chiller_cools_every_modulator():
    found = infer_device({"template": "polyscience", "devgroup": "cool"}, {"name": "MOD"})
    assert (found.asset_type, found.cools_type, found.element_type) == ("Chiller", "Modulator", None)


EVR = {"template": "mrf-pci-230", "devgroup": "timing", "devtype": "evr230"}


def test_a_timing_channel_is_a_generator_or_a_receiver_by_its_devtype():
    generator = infer_device({**EVR, "devtype": "evg230"}, {"name": "TMG"})
    assert (generator.asset_type, generator.timing_role, generator.triggers_type) == ("Timing Module", "generator", None)
    assert infer_device({**EVR, "devtype": "evr300"}, {"name": "evr1"}).timing_role == "receiver"


@pytest.mark.parametrize("name,triggers", [("EVR-LLRF", "Low-Level RF Unit"), ("TIM:EVR-CAM", "Camera"),
                                           ("EVR-RFD", None), ("EVR-BPMCAM", None), ("EVR-LAS", None)])
def test_a_receiver_triggers_only_what_its_name_says(name, triggers):
    assert infer_device(EVR, {"name": name}).triggers_type == triggers


def test_a_charge_monitor_listed_on_a_timing_ioc_is_not_a_timing_unit():
    assert infer_device(EVR, {"name": "DIA:FCT01", "devtype": "m9210"}) is None


# --- the four real configurations --------------------------------------------------------------------------

ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
FILES = {"sparc": "epik8-sparc", "btf": "epik8s-btf", "euaps": "epik8s-euaps", "eli": "epik8s-eli"}


def channels(repo):
    path = os.path.join(ROOT, repo, "deploy", "values.yaml")
    values = yaml.safe_load(open(path))
    defaults = values.get("iocDefaults") or {}
    for entry in _ioc_entries((values.get("epicsConfiguration") or {}).get("iocs")):
        merged = {**(defaults.get(entry.get("template")) or {}), **entry}
        yield merged, [d for d in (merged.get("devices") or []) if isinstance(d, dict) and d.get("name")]


@pytest.mark.parametrize("tag", FILES)
def test_the_real_configurations_read_the_way_the_rules_say(tag):
    if not os.path.exists(os.path.join(ROOT, FILES[tag], "deploy", "values.yaml")):
        pytest.skip(f"{FILES[tag]} is not next to this repository")
    tally = {"supplies": 0, "mag": 0, "cameras": 0, "cam": 0, "pumps_gauges": 0, "vac": 0, "sim": 0}
    for ioc, devices in channels(FILES[tag]):
        if infer_ioc(ioc):
            continue
        for device in devices:
            group = str(device.get("devgroup") or ioc.get("devgroup") or "").lower()
            found = infer_device(ioc, device)
            if group == "mag":
                tally["mag"] += 1
                tally["supplies"] += bool(found and found.asset_type == "Power Supply")
            elif group == "cam":
                tally["cam"] += 1
                simulated = "camerasim" in str(device.get("devtype") or ioc.get("devtype")).lower() \
                    or "SIM" in str(device["name"]).upper()
                tally["sim"] += simulated
                tally["cameras"] += bool(found and found.asset_type == "Camera")
                assert (found is None) == simulated, device["name"]
            elif group == "vac":
                tally["vac"] += 1
                tally["pumps_gauges"] += bool(found)
    assert tally["supplies"] == tally["mag"]                       # every magnet channel is a supply
    assert tally["cameras"] == tally["cam"] - tally["sim"]         # every real camera, no simulator
    # Vacuum: nearly everything is legible from metadata or the name. What is not is few.
    assert tally["pumps_gauges"] >= 0.9 * tally["vac"], tally


# --- a unit with several channels (ELI) -------------------------------------------------------------------------

SPECTRA = {"name": "bdelilibera03", "template": "libera-spe", "devgroup": "diag", "devtype": "bpm",
           "iocprefix": "LEL:DIA:BPM01", "devices": [{"name": "BPM01"}, {"name": "BPM02"}]}
SCANDICAT = {"name": "scandicat-mod", "template": "scandinova-scandicat-mod", "devgroup": "modulator",
             "devtype": "ppt", "devices": [{"name": "MOD01"}, {"name": "MOD02"}]}


def test_a_libera_spectra_is_one_box_whose_channels_are_each_a_bpm():
    unit = infer_ioc(SPECTRA)
    assert unit.asset_type == "Digitizer" and unit.channel_element == "Beam Position Monitor"
    assert unit.element_type is None                            # the IOC itself is not a BPM
    assert unit.asset_attrs["model"] == "Libera Spectra"


def test_a_bpm_ioc_with_no_channels_is_the_monitor_itself():
    single = infer_ioc({"name": "ac1bpm01", "template": "libera-sppp", "iocprefix": "AC1BPM01"})
    assert single.channel_element is None and single.element_name == "AC1BPM01"


def test_a_modulator_ioc_that_lists_channels_has_a_modulator_per_channel():
    assert infer_ioc(SCANDICAT) is None                          # not one unit...
    for name in ("MOD01", "MOD02"):
        assert infer_device(SCANDICAT, {"name": name}).asset_type == "Modulator"    # ...but one each


def test_a_modulator_ioc_that_lists_none_is_itself_the_unit():
    assert infer_ioc({"name": "ppt-mod1", "template": "ppt", "devgroup": "modulator"}).asset_type == "Modulator"



# --- the real motors ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("tag,flags,mirrors", [("sparc", 23, 0), ("btf", 1, 0), ("euaps", 0, 19), ("eli", 0, 0)])
def test_the_real_motor_channels_are_axes_and_only_what_is_named_is_more(tag, flags, mirrors):
    if not os.path.exists(os.path.join(ROOT, FILES[tag], "deploy", "values.yaml")):
        pytest.skip(f"{FILES[tag]} is not next to this repository")
    axes = screens = elements = 0
    names = set()
    for ioc, devices in channels(FILES[tag]):
        if str(ioc.get("template")).lower() != "motor":
            continue
        for device in devices:
            found = infer_device(ioc, device)
            assert found is not None and found.asset_type in ("Motor Axis", "Actuator"), device["name"]
            axes += 1
            screens += found.element_type == "Screen Station"
            if found.element_type == "Mirror":
                names.add(found.element_name)
    assert screens == flags
    assert len(names) == mirrors
