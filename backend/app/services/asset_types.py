"""The object types an accelerator facility keeps.

Tickets and documents ship with seeded types; objects did not, so every
object type in an installation was made by an importer with no attributes at
all and nothing could be validated, autocompleted or shown as a column. This
is the catalogue that fills the gap. docs/asset-schema-design.md is the
reasoning; this module is the transcription.

The shape is one abstract root and six branches, because one object cannot be
the quadrupole, the magnet, the product and the EPICS channel at once — not
once the magnet is swapped and the quadrupole stays:

  Functional      what the machine is           survives every hardware swap
  Physical        which serialised box is in it carries serial, warranty
  Catalogue       what it is an instance of     the vendor's product
  Control         how it is driven              the EPIK8s configuration
  Engineering     what the design says it needs utilities, cost, work package
  Place           where it is

Attribute keys are spelled exactly as tickets and documents spell them
(`argus_system`, `argus_subsystem`, ...) or "everything about the vacuum
system" cannot be answered across sections. The control plane keeps the bare
keys the EPIK8s importer already writes; renaming them would orphan every
row already imported.

Seeding is additive. A type that exists keeps every attribute it has and
gains the ones it lacks, so a release that adds a field reaches existing
workspaces without overwriting anything a workspace changed.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import Schema

BASE_UID_SUFFIX = "argus-object"
ROOT_NAME = "Item"

# The two EPIK8s importers name their types `epik8s-...`. A type made by one
# of them is the importer's, empty, and exactly what this catalogue absorbs.
IMPORTER_UID_PREFIX = "epik8s-"


# --- attribute vocabulary --------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _option_id(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _options(values) -> list[dict]:
    """Labels, or (id, label) pairs where the id must be kept stable."""
    out = []
    for item in values:
        option_id, label = item if isinstance(item, tuple) else (_option_id(item), item)
        out.append({"id": option_id, "value": label})
    return out


def _attr(key: str, name: str, type_: str = "string", *, indexed: bool = False,
          multi: bool = False, unique: bool = False, readonly: bool = False,
          options=None, ref: Optional[str] = None, children: bool = False,
          regex: Optional[str] = None) -> dict:
    """One attribute definition, in the shape document_types.py emits.

    A reference names its target type here and is bound to that type's uid
    when the catalogue is seeded, because the uid carries the workspace.
    """
    out = {
        "id": key, "key": key, "name": name, "type": type_,
        "required": False, "multiValue": multi, "unique": unique,
        "readOnly": readonly, "indexed": indexed,
    }
    if options is not None:
        out["options"] = _options(options)
    if ref:
        out["referenceType"] = ref
        out["includeChildren"] = children
    if regex:
        out["regex"] = regex
    return out


def S(key, name, **f):  return _attr(key, name, "string", **f)          # noqa: E704
def X(key, name, **f):  return _attr(key, name, "text", **f)            # noqa: E704
def I(key, name, **f):  return _attr(key, name, "integer", **f)         # noqa: E704,E741
def F(key, name, **f):  return _attr(key, name, "float", **f)           # noqa: E704
def B(key, name, **f):  return _attr(key, name, "boolean", **f)         # noqa: E704
def D(key, name, **f):  return _attr(key, name, "date", **f)            # noqa: E704
def DT(key, name, **f): return _attr(key, name, "datetime", **f)        # noqa: E704
def E(key, name, options, **f): return _attr(key, name, "enumeration", options=options, **f)  # noqa: E704
def U(key, name, **f):  return _attr(key, name, "user", **f)            # noqa: E704
def R(key, name, target, **f): return _attr(key, name, "reference", ref=target, **f)  # noqa: E704


@dataclass
class TypeSpec:
    name: str
    parent: Optional[str]
    description: str
    attributes: list = field(default_factory=list)
    abstract: bool = False


def type_uid(workspace_id: str, name: str) -> str:
    return f"{workspace_id}:{BASE_UID_SUFFIX}:{_slug(name)}"


# --- the catalogue, parents before children ---------------------------------

_LIFECYCLE = [("planned", "Planned"), ("in_service", "In service"), ("standby", "Standby"),
              ("maintenance", "Under maintenance"), ("faulty", "Faulty"),
              ("decommissioned", "Decommissioned"), ("scrapped", "Scrapped")]
_CRITICALITY = [("safety", "Safety-critical"), ("beam_critical", "Beam-critical"),
                ("degrades", "Degrades beam"), ("non_critical", "Non-critical")]
_SOURCE = [("manual", "Created here"), ("epik8s", "EPIK8s"),
           ("epik8s-devices", "epik8s-devices"), ("jira", "Jira"), ("git", "Git"),
           ("pbs", "PBS workbook")]
_BAND = ["S-band", "C-band", "X-band"]

CATALOGUE: list[TypeSpec] = []


def _t(name, parent, description, attributes=(), abstract=False):
    CATALOGUE.append(TypeSpec(name, parent, description, list(attributes), abstract))


# Root ---------------------------------------------------------------------
_t("Item", None, "Anything the inventory holds. Carries the keys shared with tickets "
   "and documents.", abstract=True, attributes=[
    X("description", "Description"),                       # written by photo identification
    S("argus_facility", "Facility", indexed=True),
    S("argus_system", "System", indexed=True),
    S("argus_subsystem", "Subsystem", indexed=True),
    S("argus_keywords", "Keywords", indexed=True, multi=True),
    E("argus_lifecycle", "Lifecycle", _LIFECYCLE),
    E("argus_criticality", "Criticality", _CRITICALITY),
    U("argus_responsible", "Responsible"),
    E("argus_source", "Source", _SOURCE, readonly=True),
    S("argus_source_ref", "Source revision", readonly=True),
])

_t("Engineered Item", "Item", "Anything in the product breakdown: PBS code, work "
   "package, design status.", abstract=True, attributes=[
    S("pbs_code", "PBS code", unique=True, indexed=True,
      regex=r"^[A-Z0-9]+(-[A-Z0-9.]+){3,4}$"),
    S("pbs_area", "Area / zone", indexed=True),
    S("pbs_system", "PBS system", indexed=True),
    S("pbs_family", "PBS family", indexed=True),
    S("pbs_type", "PBS type", indexed=True),
    S("pbs_sequential", "Sequential number"),               # "001", not 1
    S("component_id", "Component id", indexed=True),
    S("wbs_code", "Work package", indexed=True),
    S("module_code", "Module", indexed=True),
    S("station_name", "Station", indexed=True),
    E("design_status", "Design status", [("study", "Study"), ("defined", "Defined"),
                                          ("approved", "Approved")]),
    I("unit_count", "Number of units"),
    # The workbook's own running number. It rises down the sheet and may be
    # order along the machine; nothing says so, so it is kept, not read as one.
    I("sequence_index", "Sequence in the PBS"),
])

# Plane A: functional --------------------------------------------------------
_t("Functional Element", "Engineered Item", "What the machine is made of, and where "
   "along the beam.", abstract=True, attributes=[
    S("argus_beamline", "Beamline", indexed=True),
    S("zone", "Zones", indexed=True, multi=True),
])
_t("Facility", "Functional Element", "A beamline or accelerator facility.", [
    # What the EPIK8s importer writes on it, spelled as it writes it. `beamline`
    # sits beside the inherited `argus_beamline` until the alias pass runs.
    S("beamline", "Beamline (as configured)", indexed=True),
    S("namespace", "Kubernetes namespace", indexed=True), S("cluster", "Cluster", indexed=True),
    S("git_url", "Repository", indexed=True), S("git_revision", "Revision")])
_t("Section", "Functional Element", "Injector, linac, bunch compressor, undulator hall.")
_t("Machine System", "Functional Element", "A named system: Vacuum, RF, Magnets, "
   "Diagnostics.", [S("system_code", "System code", indexed=True),
                    S("responsible_group", "Responsible group")])
_t("Machine Module", "Functional Element", "An assembled module, as the PBS names them.", [
    S("module_code", "Module", unique=True, indexed=True),
    E("module_kind", "Module kind", ["Accelerating", "Magnetic", "Diagnostic", "Plasma", "Other"]),
    E("assembly_state", "Assembly state", ["Designed", "In assembly", "Assembled", "Installed"]),
])
_t("RF Station", "Functional Element", "Modulator, amplifier, compressor, waveguide and "
   "structures that make one RF source.", [
    E("band", "Band", _BAND), I("station_number", "Station number"),
    F("frequency", "Frequency (MHz)"), F("peak_power", "Peak power (MW)"),
    F("pulse_length", "Pulse length (µs)"), F("repetition_rate", "Repetition rate (Hz)"),
])
_t("Beam Element", "Functional Element", "Something the beam passes through or is acted "
   "on by.", abstract=True, attributes=[
    S("lattice_name", "Lattice name", unique=True, indexed=True, regex=r"^[A-Z][A-Z0-9_]{2,15}$"),
    F("s_position", "s position (m)"), F("length", "Magnetic/effective length (m)"),
    S("family", "Family", indexed=True), F("design_value", "Design strength"),
    S("design_unit", "Design strength unit", indexed=True),
    E("polarity", "Polarity", ["Positive", "Negative", "Bipolar"]),
])
_t("Dipole", "Beam Element", "A bending magnet.", [
    F("bend_angle", "Bend angle (rad)"), F("bend_radius", "Bend radius (m)"), F("field", "Field (T)")])
_t("Quadrupole", "Beam Element", "A focusing magnet.", [
    F("gradient", "Gradient (T/m)"), F("k1", "k1 (1/m²)"), F("aperture_radius", "Aperture radius (mm)")])
_t("Sextupole", "Beam Element", "A chromaticity-correcting magnet.", [F("k2", "k2 (1/m³)")])
_t("Corrector", "Beam Element", "A steering magnet.", [
    E("plane", "Plane", ["H", "V", "Combined"]), F("max_kick", "Maximum kick (mrad)")])
_t("Solenoid", "Beam Element", "A solenoid magnet.", [F("field_on_axis", "Field on axis (T)")])
_t("Accelerating Structure", "Beam Element", "A travelling- or standing-wave structure.", [
    F("frequency", "Frequency (MHz)"), I("n_cells", "Number of cells"),
    F("gradient", "Gradient (MV/m)"), F("r_over_q", "R/Q (Ω)"), F("q0", "Unloaded Q")])
_t("RF Gun", "Beam Element", "The electron source.", [
    F("frequency", "Frequency (MHz)"), S("cathode_material", "Cathode material", indexed=True),
    F("peak_field", "Peak field (MV/m)")])
_t("RF Deflector", "Beam Element", "A transverse deflecting cavity.")
_t("Undulator", "Beam Element", "A periodic magnet array producing radiation.", [
    F("period", "Period (mm)"), I("n_periods", "Number of periods"), F("k_value", "K value"),
    F("gap_min", "Minimum gap (mm)"), F("gap_max", "Maximum gap (mm)")])
_t("Plasma Module", "Beam Element", "A plasma-accelerator stage.", [
    F("capillary_length", "Capillary length (mm)"), F("capillary_diameter", "Capillary diameter (mm)"),
    S("gas", "Gas", indexed=True), F("discharge_voltage", "Discharge voltage (kV)"),
    F("plasma_density", "Plasma density (cm⁻³)")])
_t("Collimator", "Beam Element", "An aperture limiting the beam.", [
    F("aperture_min", "Aperture minimum (mm)"), F("aperture_max", "Aperture maximum (mm)"),
    S("material", "Material", indexed=True)])
_t("Beam Stopper", "Beam Element", "Blocks the beam.", [
    F("aperture_min", "Aperture minimum (mm)"), F("aperture_max", "Aperture maximum (mm)"),
    S("material", "Material", indexed=True)])
_t("Vacuum Sector", "Beam Element", "What a valve isolates.", [
    F("nominal_pressure", "Nominal pressure (mbar)"), F("length", "Length (m)"),
    R("isolated_by", "Isolated by", "Vacuum Valve", multi=True)])
_t("Diagnostic Element", "Beam Element", "Measures the beam.", abstract=True, attributes=[
    E("measures", "Measures", ["Position", "Charge", "Profile", "Emittance", "Energy",
                               "Arrival time", "Bunch length", "Loss"]),
    B("is_invasive", "Stops the beam"), F("resolution", "Resolution"),
    S("resolution_unit", "Resolution unit", indexed=True),
    F("acquisition_rate", "Acquisition rate (Hz)"), D("calibration_due", "Calibration due"),
])
_t("Screen Station", "Diagnostic Element", "A screen, camera, actuator and optics "
   "composed into one profile monitor.", [
    E("screen_type", "Screen type", ["YAG:Ce", "LYSO", "OTR", "Chromox", "Scintillating fibre"]),
    F("calibration_um_per_px", "Calibration (µm/px)"),
    S("insertion_positions", "Insertion positions", indexed=True, multi=True),
    F("viewing_angle_deg", "Viewing angle (°)"), F("field_of_view_mm", "Field of view (mm)")])
_t("Beam Position Monitor", "Diagnostic Element", "Measures the beam's transverse position.", [
    E("pickup_kind", "Pickup", ["Button", "Stripline", "Cavity", "Inductive"]),
    I("n_electrodes", "Number of electrodes"), F("bandwidth", "Bandwidth (MHz)")])
_t("Beam Charge Monitor", "Diagnostic Element", "Measures the bunch charge.", [
    E("monitor_kind", "Monitor kind", ["Integrating current transformer", "Wall current",
                                       "Faraday cup"]),
    F("charge_range_pc", "Charge range (pC)")])
_t("Faraday Cup", "Diagnostic Element", "Stops the beam and reads its charge.", [
    S("material", "Material", indexed=True), B("is_retractable", "Retractable")])
_t("Wire Scanner", "Diagnostic Element", "Profiles the beam with a moving wire.", [
    S("wire_material", "Wire material", indexed=True), F("wire_diameter", "Wire diameter (µm)"),
    I("n_planes", "Number of planes")])
_t("Emittance Meter", "Diagnostic Element", "Measures emittance; composed of screens and "
   "actuators.", [
    E("method", "Method", ["Pepper-pot", "Quadrupole scan", "Multi-screen", "Slit-scan"]),
    F("mask_pitch", "Mask pitch (µm)")])
_t("Spectrometer Station", "Diagnostic Element", "Measures the beam's energy spectrum.", [
    F("dispersion", "Dispersion (m)"), F("energy_range_min", "Energy range minimum (MeV)"),
    F("energy_range_max", "Energy range maximum (MeV)")])
_t("Beam Loss Monitor", "Diagnostic Element", "Detects lost particles.", [
    E("detector_kind", "Detector", ["Ion chamber", "Scintillator", "Cherenkov", "PIN diode"]),
    F("alarm_threshold", "Alarm threshold")])
_t("Beam Arrival Monitor", "Diagnostic Element", "Measures arrival time.", [
    F("time_resolution_fs", "Time resolution (fs)"),
    E("pickup_kind", "Pickup", ["Button", "Stripline", "Cavity", "Inductive"])])
_t("Bunch Length Monitor", "Diagnostic Element", "Measures the bunch length.", [
    E("method", "Method", ["Electro-optic sampling", "Streak camera", "CTR", "CDR", "RF deflector"]),
    F("time_range_ps", "Time range (ps)")])

# Plane B: physical -------------------------------------------------------------
_t("Equipment Item", "Engineered Item", "The serialised box, with a purchase order.",
   abstract=True, attributes=[
    S("manufacturer", "Manufacturer", indexed=True),        # reserved: photo identification
    S("model", "Model", indexed=True),                      # reserved
    S("serial", "Serial number", indexed=True),             # reserved
    R("product_model", "Instance of", "Product Model"),
    R("argus_location", "Located in", "Place", children=True),
    S("inventory_number", "Inventory number", unique=True, indexed=True),
    D("installed_on", "Installed on"), D("removed_on", "Removed on"),
    D("warranty_until", "Warranty until"),
    E("condition", "Condition", ["New", "Good", "Degraded", "Faulty", "Beyond repair"]),
    B("is_spare", "Held as spare"), S("inventory_url", "Inventory link"),
])
_t("Power Supply", "Equipment Item", "Powers a magnet or another load.", [
    I("n_channels", "Number of channels"), F("current_max", "Maximum current (A)"),
    F("voltage_max", "Maximum voltage (V)"), B("bipolar", "Bipolar"),
    E("interface", "Interface", ["Modbus TCP", "Serial", "Ethernet", "GPIB", "CAN"]),
    F("ramp_rate", "Ramp rate (A/s)")])
_t("Magnet Assembly", "Equipment Item", "The magnet itself, as a physical unit.", [
    F("coil_resistance", "Coil resistance (Ω)"),
    E("cooling", "Cooling", ["Air", "Water", "Cryogenic"]), F("weight", "Weight (kg)")])
_t("RF Amplifier", "Equipment Item", "Klystron or solid-state amplifier.")
_t("Modulator", "Equipment Item", "Pulsed power for a klystron.")
_t("Low-Level RF Unit", "Equipment Item", "Regulates RF phase and amplitude.")
_t("Waveguide Component", "Equipment Item", "A part of the RF waveguide network.",
   abstract=True, attributes=[
    E("band", "Band", _BAND), S("waveguide_size", "Waveguide size", indexed=True),
    S("flange_type", "Flange type"), F("peak_power_rating", "Peak power rating (MW)"),
    F("average_power_rating", "Average power rating (kW)"), B("is_pressurised", "Pressurised"),
    S("gas", "Gas", indexed=True)])
_t("Waveguide Section", "Waveguide Component", "A straight or bent length of waveguide.", [
    F("length_mm", "Length (mm)"), F("bend_angle_deg", "Bend angle (°)"),
    B("is_flexible", "Flexible")])
_t("RF Load", "Waveguide Component", "Absorbs RF power.", [
    E("load_kind", "Load kind", ["Water", "Dry", "Ceramic"]), F("vswr_max", "Maximum VSWR")])
_t("RF Window", "Waveguide Component", "A vacuum-tight RF window.", [
    E("window_material", "Window material", ["Ceramic", "Sapphire"]),
    B("is_vacuum_barrier", "Vacuum barrier")])
_t("Directional Coupler", "Waveguide Component", "Samples forward and reflected power.", [
    F("coupling_db", "Coupling (dB)"), F("directivity_db", "Directivity (dB)"),
    B("is_bidirectional", "Bidirectional")])
_t("RF Isolator", "Waveguide Component", "Protects the source from reflections.", [
    F("isolation_db", "Isolation (dB)"), F("insertion_loss_db", "Insertion loss (dB)")])
_t("RF Hybrid", "Waveguide Component", "Splits or combines RF power.", [
    E("hybrid_kind", "Hybrid kind", ["3 dB", "Magic-T"]),
    F("phase_balance_deg", "Phase balance (°)")])
_t("RF Pulse Compressor", "Waveguide Component", "Trades pulse length for peak power.", [
    E("compressor_kind", "Compressor kind", ["SLED", "BOC", "Barrel"]),
    F("gain_factor", "Gain factor"), F("q0", "Unloaded Q")])
_t("RF Attenuator", "Waveguide Component", "Reduces RF power.", [
    F("attenuation_db", "Attenuation (dB)"), B("is_variable", "Variable")])
_t("RF Phase Shifter", "Waveguide Component", "Adjusts RF phase.", [
    F("phase_range_deg", "Phase range (°)"), B("is_motorised", "Motorised")])
_t("RF Mode Converter", "Waveguide Component", "Converts between waveguide modes.", [
    S("mode_in", "Mode in"), S("mode_out", "Mode out")])
_t("Vacuum Pump", "Equipment Item", "Any vacuum pump.", abstract=True)
_t("Ion Pump", "Vacuum Pump", "A sputter-ion pump: the thing that trips when the "
   "pressure rises.", [F("pumping_speed", "Pumping speed (l/s)"),
                       I("nominal_voltage", "Nominal voltage (V)"),
                       I("element_count", "Number of elements")])
_t("Turbo Pump", "Vacuum Pump", "A turbomolecular pump.", [
    F("pumping_speed", "Pumping speed (l/s)"), F("rotation_speed", "Rotation speed (Hz)"),
    R("backing_pump", "Backed by", "Primary Pump")])
_t("Primary Pump", "Vacuum Pump", "A roughing or backing pump.")
_t("NEG Cartridge", "Vacuum Pump", "A non-evaporable getter pump.")
_t("Vacuum Gauge", "Equipment Item", "Measures pressure.", [
    E("gauge_kind", "Gauge kind", ["Pirani", "Penning", "Cold cathode", "Capacitive"]),
    F("range_min", "Range minimum (mbar)"), F("range_max", "Range maximum (mbar)")])
_t("Vacuum Valve", "Equipment Item", "Isolates a vacuum sector.", [
    E("valve_kind", "Valve kind", ["Gate", "Angle", "All-metal"]),
    E("actuation", "Actuation", ["Manual", "Pneumatic", "Electric"]),
    B("interlocked", "Interlocked")])
_t("Vacuum Chamber", "Equipment Item", "What you unbolt.")
_t("Motion Controller", "Equipment Item", "Drives one or more motor axes.", [
    I("n_axes", "Number of axes"), S("protocol", "Protocol"),
    S("firmware_version", "Firmware version")])
_t("Motor Axis", "Equipment Item", "One motorised axis.", [
    S("axis_id", "Axis id"), F("travel_min", "Travel minimum (mm)"),
    F("travel_max", "Travel maximum (mm)"), F("resolution", "Resolution (mm/step)"),
    F("velocity_max", "Maximum velocity (mm/s)"), B("has_home_switch", "Home switch")])
_t("Actuator", "Equipment Item", "Puts something in and out of the beam.", [
    E("actuator_kind", "Actuator kind", ["Pneumatic", "Solenoid", "Stepper", "Piezo", "Manual"]),
    I("n_positions", "Number of positions"),
    S("position_labels", "Position labels", indexed=True, multi=True),
    F("stroke_mm", "Stroke (mm)"), B("has_position_switch", "Position switch"),
    S("fail_safe_position", "Fail-safe position", indexed=True)])
_t("Camera", "Equipment Item", "A camera.", [
    S("sensor", "Sensor"), I("resolution_x", "Resolution X (px)"),
    I("resolution_y", "Resolution Y (px)"), F("pixel_size", "Pixel size (µm)"),
    E("interface", "Interface", ["GigE", "USB3", "CameraLink", "CoaXPress"]),
    S("lens", "Lens"), F("px_calibration", "Calibration (µm/px)")])
_t("Optical Assembly", "Equipment Item", "The optics between a screen and its camera.", [
    F("focal_length_mm", "Focal length (mm)"), F("magnification", "Magnification"),
    F("aperture_f", "Aperture (f-number)"), S("filters", "Filters", indexed=True, multi=True),
    I("mirror_count", "Number of mirrors"), F("working_distance_mm", "Working distance (mm)")])
_t("Scintillator Screen", "Equipment Item", "The screen the beam strikes.", [
    E("screen_material", "Screen material", ["YAG:Ce", "LYSO", "OTR foil", "Chromox", "Alumina"]),
    F("thickness_um", "Thickness (µm)"), F("diameter_mm", "Diameter (mm)"),
    F("mount_angle_deg", "Mount angle (°)"), B("has_calibration_target", "Calibration target"),
    F("radiation_dose_budget", "Radiation dose budget")])
_t("Digitizer", "Equipment Item", "Samples an analogue signal.")
_t("Instrument", "Equipment Item", "A bench or rack instrument.")
_t("I/O Module", "Equipment Item", "Analogue or digital input and output.")
_t("PLC", "Equipment Item", "A programmable logic controller.")
_t("Timing Module", "Equipment Item", "Event generator, receiver or delay generator.")
_t("Electronics Crate", "Equipment Item", "A crate holding electronics boards.")
_t("Electronics Board", "Equipment Item", "A board in a crate.")
_t("Network Device", "Equipment Item", "A switch, terminal server or converter.", [
    E("device_kind", "Device kind", ["Switch", "Terminal server", "Media converter", "Router"]),
    I("n_ports", "Number of ports"), S("hostname", "Hostname", indexed=True),
    S("ip", "IP address", indexed=True), S("fqdn", "FQDN"),
    S("firmware_version", "Firmware version")])
_t("Computing Node", "Equipment Item", "A server or workstation.", [
    S("hostname", "Hostname", indexed=True), S("ip", "IP address", indexed=True),
    S("cpu", "CPU"), F("ram_gb", "RAM (GB)"), S("os", "Operating system"), S("role", "Role")])
_t("Chiller", "Equipment Item", "A water chiller.")
_t("Cooling Circuit Component", "Equipment Item", "A pump, exchanger or valve in a "
   "cooling circuit.")
_t("Cryogenic Device", "Equipment Item", "A cryostat, cold head or transfer line.")
_t("Interlock Unit", "Equipment Item", "A safety or machine-protection interlock.", [
    E("interlock_kind", "Interlock kind", ["PSS", "MPS", "Vacuum", "Thermal"]),
    S("sil_level", "SIL level"), I("test_interval_months", "Test interval (months)")])
_t("Radiation Monitor", "Equipment Item", "Measures radiation.", [
    S("detector_kind", "Detector kind"), F("alarm_threshold", "Alarm threshold"),
    D("calibration_due", "Calibration due")])
_t("Laser System", "Equipment Item", "A laser and its delivery.")
_t("Cable Run", "Equipment Item", "A cable between two connectors.", [
    S("cable_type", "Cable type"), F("length_m", "Length (m)"),
    S("from_connector", "From connector"), S("to_connector", "To connector"),
    S("signal", "Signal")])
_t("Mechanical Support", "Equipment Item", "A stand, girder or support.")
_t("Spare Part", "Equipment Item", "Held on a shelf for a product model.", [
    R("spare_for", "Spare for", "Product Model"), I("quantity", "Quantity"),
    I("minimum_stock", "Minimum stock"),
    R("storage_location", "Stored in", "Storage Location")])

# Plane C: catalogue --------------------------------------------------------------
_t("Catalog Item", "Item", "What a thing is an instance of.", abstract=True)
_t("Product Model", "Catalog Item", "A vendor's product. A procedure written once for it "
   "covers every unit.", [
    S("vendor", "Vendor", indexed=True), R("vendor_ref", "Supplied by", "Vendor"),
    S("model_code", "Model code", indexed=True), S("device_class", "Device class", indexed=True),
    S("datasheet_url", "Datasheet"), S("firmware_version", "Current firmware"),
    D("eol_date", "End of life"), I("mtbf_hours", "MTBF (h)"),
    S("typical_spares", "Typical spares", indexed=True, multi=True),
    S("inventory_url", "Inventory link")])
_t("Vendor", "Catalog Item", "The company, its support contract and RMA route.", [
    S("contact", "Contact"), S("support_contract", "Support contract"),
    D("support_expires", "Support expires"), X("rma_procedure", "RMA procedure"),
    S("website", "Website")])

# Plane D: control --------------------------------------------------------------
_t("Control Item", "Item", "The control configuration, as objects.", abstract=True, attributes=[
    S("beamline", "Beamline", indexed=True), S("inventory_url", "Inventory link")])
_t("Control Configuration", "Control Item", "One values.yaml at one git revision.", [
    S("git_url", "Repository", indexed=True), S("git_revision", "Revision"),
    S("config_path", "Path in repository"), S("namespace", "Kubernetes namespace", indexed=True),
    S("cluster", "Cluster", indexed=True), S("argocd_project", "ArgoCD project"),
    S("epics_address_list", "EPICS address list"), I("max_array_bytes", "Max array bytes"),
    S("base_ip", "Address range"), S("ingress_class", "Ingress class"),
    DT("imported_at", "Read at", readonly=True)])
_t("IOC Template", "Control Item", "An iocDefaults entry: the recipe an IOC is deployed "
   "from.", [
    S("template_name", "Template", unique=True, indexed=True), S("chart_url", "Chart"),
    S("image", "Image"), S("devgroup", "Device group", indexed=True),
    S("devtype", "Device type", indexed=True), S("devfunc", "Device function", indexed=True),
    S("opi", "OPI"), B("autosync", "Auto-sync"), B("pva", "PVAccess"),
    R("product_model", "Instance of", "Product Model")])
_t("IOC", "Control Item", "An EPICS IOC: the deployable unit of control software.", [
    S("iocprefix", "IOC prefix", indexed=True), S("iocroot", "IOC root"),
    S("pv_prefix", "PV prefix", indexed=True), S("template", "Template", indexed=True),
    S("devtype", "Device type", indexed=True), S("system", "System (devgroup)", indexed=True),
    S("zones", "Zones", indexed=True, multi=True), S("address", "Address", indexed=True),
    S("port", "Port"), S("chart_url", "Chart"), S("image", "Image"),
    S("host", "Host", indexed=True), S("opi", "OPI"), B("autosync", "Auto-sync"),
    B("pva", "PVAccess"), S("networks", "Networks", indexed=True, multi=True),
    X("ioc_init", "IOC init"), S("ssh_nodeport", "SSH node port")])
_t("Control Device", "Control Item", "A channel, axis, gauge or supply an IOC drives — "
   "what fails.", [
    S("pv", "PV", unique=True, indexed=True), S("pv_prefix", "PV prefix", indexed=True),
    S("ioc", "IOC", indexed=True), S("system", "System (devgroup)", indexed=True),
    S("function", "Function (devfunc)", indexed=True), S("devtype", "Device type", indexed=True),
    S("device_class", "Device class", indexed=True), S("element", "Element it serves", indexed=True),
    S("zones", "Zones", indexed=True, multi=True), I("channel", "Channel"), I("axis", "Axis"),
    S("address", "Address", indexed=True), S("port", "Port"), B("interlock", "Interlocked"),
    I("geo", "Geographic index"), S("enable_pv", "Enable PV"),
    X("settings", "Settings and limits")])
_t("Access Point", "Control Item", "What control software reaches hardware through: a "
   "terminal server, a converter, or the hardware's own network socket.", [
    S("address", "Address", indexed=True), S("ip", "IP address", indexed=True),
    S("hostname", "Hostname", indexed=True), S("fqdn", "FQDN"),
    X("argus_provenance", "Provenance", readonly=True), I("port_count", "Number of ports"),
    S("network", "Network", indexed=True)])
_t("Control Service", "Control Item", "A shared control service: archiver, gateway, "
   "alarm server, logbook.", [
    S("service", "Service", indexed=True), S("chart_url", "Chart"),
    S("chart_revision", "Chart revision"), S("image", "Image"),
    S("loadbalancer_ip", "Load balancer IP"), B("ingress", "Ingress"), S("url", "URL"),
    I("replicas", "Replicas")])
_t("Control Network", "Control Item", "A named network and its address range.", [
    S("network_name", "Network", indexed=True), S("cidr", "CIDR"),
    S("annotation", "Annotation"), I("vlan", "VLAN"), S("address_list", "Address list")])
_t("Storage Mount", "Control Item", "An NFS mount or backup target.", [
    E("mount_kind", "Mount kind", ["NFS", "Local", "S3"]), S("server", "Server", indexed=True),
    S("export_path", "Export path"), S("mount_path", "Mount path"), F("size_gb", "Size (GB)"),
    B("is_backup", "Backup")])

# Engineering record -----------------------------------------------------------
_t("Engineering Record", "Item", "What the design says a component needs and costs.",
   abstract=True)
_t("Utility Requirement", "Engineering Record", "What the building has to supply.", [
    E("electrical_phases", "Electrical phases", ["3P+N", "1P+N"]), B("under_ups", "Under UPS"),
    F("nominal_current_a", "Nominal current (A)"), F("max_inrush_current_a", "Maximum inrush current (A)"),
    F("nominal_power_kva", "Nominal power (kVA)"), F("active_power_kw", "Active power in operation (kW)"),
    F("cos_phi", "cos φ"), I("rack_units", "Rack units"),
    S("connectivity", "Connectivity", indexed=True, multi=True),
    F("heat_in_air_kw", "Heat dissipation in air (kW)"),
    F("heat_in_water_nominal_kw", "Nominal heat dissipation in water (kW)"),
    F("heat_in_water_min_kw", "Minimum heat dissipation in water (kW)"),
    F("water_temp_in_c", "Water temperature in, nominal (°C)"),
    F("water_temp_setpoint_c", "Water temperature setpoint (°C)"),
    F("water_temp_setpoint_min_c", "Water temperature setpoint minimum (°C)"),
    F("water_temp_setpoint_max_c", "Water temperature setpoint maximum (°C)"),
    F("water_temp_stability_c", "Water temperature stability (°C)"),
    F("water_flow_l_min", "Water flow rate (l/min)"),
    F("water_pressure_in_bar", "Water nominal pressure in (bar)"),
    F("water_pressure_drop_bar", "Water pressure drop (bar)"),
    F("water_pressure_max_bar", "Water maximum pressure in (bar)"),
    F("water_delta_t_c", "Water ΔT (°C)"),
    F("water_max_acceptable_temp_c", "Maximum acceptable temperature in (°C)"),
    F("air_temp_nominal_c", "Air temperature, nominal (°C)"),
    F("air_temp_stability_c", "Air temperature stability (°C)"),
    F("relative_humidity_pct", "Relative humidity (%)"), F("rh_stability_pct", "RH stability (%)"),
    F("compressed_air_nominal_bar", "Compressed air pressure, nominal (bar)"),
    F("compressed_air_min_bar", "Compressed air pressure, minimum (bar)"),
    F("compressed_air_max_bar", "Compressed air pressure, maximum (bar)"),
    F("compressed_air_flow_l_min", "Compressed air flow rate (l/min)"),
    S("gas_type", "Other gases, type", indexed=True), F("gas_quantity_m3_h", "Other gases, quantity (m³/h)")])
_t("Procurement Record", "Engineering Record", "Cost, supplier, delivery and funding.", [
    F("unit_cost_eur", "Unit cost (€)"), F("total_cost_eur", "Total cost (€)"),
    S("currency", "Currency"), I("target_year", "Target year"),
    E("target_semester", "Target semester", ["H1", "H2"]),
    S("procurement_route", "Procurement route", indexed=True),
    F("production_time_months", "Production time (months)"),
    F("delivery_time_months", "Delivery time (months)"),
    S("supplier", "Supplier", indexed=True), R("supplier_ref", "Supplied by", "Vendor"),
    U("rup", "RUP"), S("funding_line", "Funding line", indexed=True),
    S("cig", "CIG", indexed=True), S("order_reference", "Order reference"),
    D("ordered_on", "Ordered on"), D("delivered_on", "Delivered on")])
_t("Work Package", "Engineering Record", "WP-01 … WP-13.", [
    S("wbs_code", "WBS code", unique=True, indexed=True), U("leader", "Leader"),
    S("institute", "Institute", indexed=True), F("budget_eur", "Budget (€)"),
    D("start_date", "Start date"), D("end_date", "End date")])

# Place -------------------------------------------------------------------------
_t("Place", "Item", "Where something is, and the rules for reaching it.", abstract=True, attributes=[
    S("site", "Site", indexed=True), S("floor", "Floor"),
    E("access_rule", "Access rule", ["Free", "Badge", "Interlocked", "Radiation-controlled"])])
_t("Building", "Place", "A building.")
_t("Area", "Place", "A room, hall or tunnel.", [
    S("zone", "Zone", indexed=True),
    E("radiation_classification", "Radiation classification",
      ["Supervised", "Controlled", "Prohibited"]),
    S("interlock_group", "Interlock group")])
_t("Rack", "Place", "An equipment rack.", [
    I("rack_units", "Rack units"), S("position", "Position"), S("power_feed", "Power feed"),
    S("cooling", "Cooling")])
_t("Storage Location", "Place", "A shelf or bin where spares are kept.", [
    S("shelf", "Shelf"), S("bin", "Bin"), B("climate_controlled", "Climate controlled")])

BY_NAME: dict[str, TypeSpec] = {spec.name: spec for spec in CATALOGUE}


def depth(name: str) -> int:
    d, cur = 1, BY_NAME[name].parent
    while cur:
        d, cur = d + 1, BY_NAME[cur].parent
    return d


# --- seeding ------------------------------------------------------------------

@dataclass
class SeedResult:
    uids: dict = field(default_factory=dict)         # name -> schema uid
    created: list = field(default_factory=list)
    adopted: list = field(default_factory=list)      # importer-made, now under the catalogue
    extended: list = field(default_factory=list)     # existing, gained attributes
    duplicates: list = field(default_factory=list)   # a same-named type that is not ours


def _bound(attributes: list, uids: dict) -> list:
    """Attributes with each reference pointing at its target's uid."""
    out = []
    for attr in attributes:
        attr = dict(attr)
        target = attr.get("referenceType")
        if attr.get("type") == "reference" and target:
            attr["referenceSchemaUid"] = uids[target]
        out.append(attr)
    return out


def _merge(existing: list, wanted: list) -> tuple[list, bool]:
    """Add what is missing; never overwrite or drop what is there."""
    have = {a.get("key") or a.get("name") for a in existing}
    added = [a for a in wanted if a["key"] not in have]
    return (list(existing) + added, bool(added))


def ensure_asset_types(db: Session, workspace_id: str) -> SeedResult:
    """Create the catalogue in a workspace, or bring it up to date.

    Idempotent and additive: types that exist keep their attributes and gain
    any they lack. A type the EPIK8s importers made (uid `epik8s-...`, no
    parent) is adopted rather than duplicated — it is the same thing, empty —
    so the order of seeding and importing does not matter. A same-named type
    that is anybody else's is left alone and reported: reparenting somebody's
    tree to make it fit is not the seeder's call.
    """
    result = SeedResult()
    others = {
        s.name: s for s in db.scalars(select(Schema).where(
            Schema.workspace_id == workspace_id, Schema.applies_to == "objects"))
    }
    # References need every uid up front, before any type is written.
    for spec in CATALOGUE:
        own = type_uid(workspace_id, spec.name)
        found = others.get(spec.name)
        adoptable = (found is not None and found.uid != own
                     and found.uid.startswith(IMPORTER_UID_PREFIX)
                     and found.parent_schema_uid is None)
        result.uids[spec.name] = found.uid if adoptable else own

    for spec in CATALOGUE:
        uid = result.uids[spec.name]
        parent_uid = result.uids[spec.parent] if spec.parent else None
        wanted = _bound(spec.attributes, result.uids)
        schema = db.get(Schema, uid)
        if schema is None:
            clash = others.get(spec.name)
            if clash is not None and clash.uid != uid:
                result.duplicates.append(spec.name)
            db.add(Schema(
                uid=uid, workspace_id=workspace_id, name=spec.name,
                description=spec.description, applies_to="objects",
                is_concrete=not spec.abstract, parent_schema_uid=parent_uid,
                attributes=wanted, metadata_json={"source": "argus"},
            ))
            result.created.append(spec.name)
            db.flush()
            continue
        if uid != type_uid(workspace_id, spec.name):
            schema.parent_schema_uid = parent_uid
            schema.is_concrete = not spec.abstract
            schema.description = schema.description or spec.description
            result.adopted.append(spec.name)
        merged, changed = _merge(schema.attributes or [], wanted)
        if changed:
            schema.attributes = merged
            if spec.name not in result.adopted:
                result.extended.append(spec.name)
        db.flush()
    return result
