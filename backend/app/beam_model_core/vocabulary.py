"""The controlled vocabularies of the canonical beam model (argus.beam-model/2).

Everything here is data: component types grouped by family, the capabilities a component may declare, the
built-in observables, measurement-model kinds, default state sets for movable devices, and the relations a
model component may have with an external physical asset. Nothing assumes a ring, a charged particle, one
beam or one simulator: a type says what a component *is*; what it *does* is its capabilities, which a model
may extend; its numbers are parameters and datasets.

A type outside this list is not an error: it is kept as written, its family is `generic`, and the component
is described by its capabilities and native data (`validation` reports it as a warning).
"""
from __future__ import annotations

# --------------------------------------------------------------------------- capabilities

CAPABILITIES: dict[str, str] = {
    # transport
    "particle_transport": "a charged or neutral particle beam passes through it",
    "photon_transport": "a photon (laser, synchrotron light) beam passes through it",
    "focusing": "focuses the beam in at least one plane",
    "defocusing": "defocuses the beam in at least one plane",
    "bending": "changes the direction of the reference trajectory",
    "steering": "deflects the beam by a small, adjustable angle",
    "horizontal_steering": "steers in the horizontal plane",
    "vertical_steering": "steers in the vertical plane",
    "acceleration": "changes the beam's energy",
    "deceleration": "takes energy from the beam",
    "deflection": "deflects the beam (transversely, in time or between paths)",
    "bunching": "changes the longitudinal bunch structure",
    "chromatic_correction": "corrects chromatic effects",
    "nonlinear_correction": "corrects or drives non-linear dynamics",
    "radiation_emission": "makes the beam radiate (undulator, wiggler, bend)",
    "branching": "sends the beam, or part of it, onto another path",
    "merging": "brings another path's beam onto this one",
    "pulsed": "acts only during a pulse (kicker, pulsed septum)",
    # sources and ends
    "beam_source": "where a beam is produced",
    "beam_destination": "where a beam ends: a dump, a target, an experiment",
    "interaction_point": "where beams collide or interact with a target",
    # diagnostics
    "diagnostic": "measures something about the beam",
    "interceptive": "puts material in the beam when in use",
    "non_interceptive": "measures without intercepting the beam",
    "beam_position_measurement": "measures the beam's centroid position",
    "beam_angle_measurement": "measures the beam's angle",
    "beam_profile_measurement": "measures the transverse distribution",
    "beam_size_measurement": "measures the beam size",
    "beam_intensity_measurement": "measures current, charge or particle number",
    "beam_energy_measurement": "measures energy or energy spread",
    "beam_loss_measurement": "detects beam losses",
    "beam_timing_measurement": "measures arrival time or bunch length",
    "optical_measurement": "measures a property of a photon beam (power, spectrum, wavefront…)",
    # boundaries and material
    "aperture_limiting": "restricts the space available to the beam",
    "material_interaction": "the beam passes through or hits material",
    "vacuum_boundary": "is part of the vacuum envelope around the beam",
    "vacuum_isolation": "can separate two vacuum sections",
    "beam_protection": "protects equipment or people from the beam",
    "beam_interception": "stops or absorbs the beam on purpose",
    # operation and mechanics
    "powered": "needs a power supply to act on the beam",
    "movable": "can change position",
    "retractable": "can be moved in and out of the beam",
    "interlocked": "takes part in an interlock",
    "alignment_sensitive": "its alignment affects the beam",
    "survey_reference": "is a survey or alignment reference",
    "mechanical_support": "carries other components",
    "virtual": "a model concept with no physical object (marker, reference point, observation point)",
}

# --------------------------------------------------------------------------- component types

# family → {type: default capabilities}. Families group types for filters (magnets, diagnostics, vacuum…) and
# for matching against asset types; they are not a class hierarchy.
_P, _PH = "particle_transport", "photon_transport"
_MAG = [_P, "powered", "alignment_sensitive"]

FAMILIES: dict[str, dict[str, list[str]]] = {
    "magnet": {
        "dipole": [*_MAG, "bending"],
        "quadrupole": [*_MAG, "focusing"],
        "sextupole": [*_MAG, "chromatic_correction"],
        "octupole": [*_MAG, "nonlinear_correction"],
        "multipole": [*_MAG],
        "solenoid": [*_MAG, "focusing"],
        "corrector": [_P, "powered", "steering"],
        "kicker": [_P, "powered", "steering", "pulsed"],
        "septum": [_P, "powered", "branching", "aperture_limiting"],
        "undulator": [_P, "radiation_emission", "alignment_sensitive"],
        "wiggler": [_P, "radiation_emission", "alignment_sensitive"],
        "generic_magnet": [*_MAG],
    },
    "rf": {
        "rf_cavity": [_P, "powered", "acceleration"],
        "accelerating_structure": [_P, "powered", "acceleration"],
        "buncher": [_P, "powered", "bunching"],
        "decelerating_structure": [_P, "powered", "deceleration"],
        "rf_deflector": [_P, "powered", "deflection"],
        "crab_cavity": [_P, "powered", "deflection"],
        "rf_gun": [_P, "powered", "beam_source", "acceleration"],
        "generic_rf": [_P, "powered"],
    },
    "diagnostic": {
        "bpm": ["diagnostic", "non_interceptive", "beam_position_measurement"],
        "screen": ["diagnostic", "interceptive", "beam_profile_measurement", "material_interaction", "retractable"],
        "profile_monitor": ["diagnostic", "beam_profile_measurement"],
        "wire_scanner": ["diagnostic", "interceptive", "beam_profile_measurement", "material_interaction", "movable"],
        "current_transformer": ["diagnostic", "non_interceptive", "beam_intensity_measurement"],
        "dc_current_transformer": ["diagnostic", "non_interceptive", "beam_intensity_measurement"],
        "wall_current_monitor": ["diagnostic", "non_interceptive", "beam_intensity_measurement",
                                 "beam_timing_measurement"],
        "faraday_cup": ["diagnostic", "interceptive", "beam_intensity_measurement", "beam_interception"],
        "beam_loss_monitor": ["diagnostic", "non_interceptive", "beam_loss_measurement"],
        "spectrometer": ["diagnostic", "beam_energy_measurement"],
        "bunch_length_monitor": ["diagnostic", "beam_timing_measurement"],
        "beam_arrival_monitor": ["diagnostic", "non_interceptive", "beam_timing_measurement"],
        "synchrotron_light_monitor": ["diagnostic", "non_interceptive", "beam_size_measurement",
                                      "beam_profile_measurement"],
        "camera": ["diagnostic", "optical_measurement", "beam_profile_measurement"],
        "photodiode": ["diagnostic", "optical_measurement"],
        "power_meter": ["diagnostic", "optical_measurement", "interceptive"],
        "wavefront_sensor": ["diagnostic", "optical_measurement"],
        "optical_spectrometer": ["diagnostic", "optical_measurement"],
        "emittance_meter": ["diagnostic", "beam_size_measurement"],
        "generic_monitor": ["diagnostic"],
    },
    "injection_extraction": {
        "stripping_foil": [_P, "material_interaction", "interceptive"],
        "injection_foil": [_P, "material_interaction", "interceptive"],
        "injection_element": [_P, "merging"],
        "extraction_element": [_P, "branching"],
    },
    "interception": {
        "collimator": [_P, "aperture_limiting", "beam_protection", "material_interaction"],
        "scraper": [_P, "aperture_limiting", "movable", "material_interaction"],
        "mask": [_P, "aperture_limiting", "beam_protection"],
        "absorber": [_P, "beam_interception", "material_interaction", "beam_protection"],
        "beam_stopper": [_P, "beam_interception", "beam_protection", "retractable", "interlocked"],
        "beam_dump": ["beam_destination", "beam_interception", "material_interaction"],
        "target": ["beam_destination", "material_interaction", "interceptive"],
        "protection_block": ["beam_protection", "aperture_limiting"],
    },
    "vacuum": {
        "beam_pipe": [_P, "vacuum_boundary", "aperture_limiting"],
        "vacuum_chamber": [_P, "vacuum_boundary", "aperture_limiting"],
        "bellows": [_P, "vacuum_boundary", "aperture_limiting"],
        "flange": [_P, "vacuum_boundary"],
        "transition": [_P, "vacuum_boundary", "aperture_limiting"],
        "gate_valve": [_P, "vacuum_boundary", "vacuum_isolation", "aperture_limiting", "movable", "interlocked"],
        "fast_valve": [_P, "vacuum_boundary", "vacuum_isolation", "aperture_limiting", "movable", "interlocked"],
        "vacuum_window": [_P, "vacuum_boundary", "vacuum_isolation", "material_interaction"],
        "differential_pumping_section": [_P, "vacuum_boundary", "aperture_limiting"],
        "pump_port": [_P, "vacuum_boundary"],
        "gauge_port": [_P, "vacuum_boundary"],
        "generic_vacuum": [_P, "vacuum_boundary"],
    },
    "material": {
        "foil": ["material_interaction", "interceptive"],
        "window": ["material_interaction"],
        "wire": ["material_interaction", "interceptive"],
        "converter": ["material_interaction", "beam_source"],
        "gas_target": ["material_interaction", "interaction_point"],
        "gas_jet": ["material_interaction", "interaction_point"],
        "crystal": ["material_interaction", "deflection"],
        "generic_material": ["material_interaction"],
    },
    "optical": {
        "mirror": [_PH, "steering", "alignment_sensitive"],
        "lens": [_PH, "focusing", "alignment_sensitive"],
        "beam_splitter": [_PH, "branching", "alignment_sensitive"],
        "polarizer": [_PH],
        "waveplate": [_PH],
        "optical_crystal": [_PH, "material_interaction"],
        "grating": [_PH, "deflection"],
        "prism": [_PH, "deflection"],
        "aperture": [_PH, "aperture_limiting"],
        "iris": [_PH, "aperture_limiting", "movable"],
        "optical_filter": [_PH, "material_interaction"],
        "optical_amplifier": [_PH, "powered"],
        "generic_optical": [_PH],
    },
    "source_destination": {
        "electron_source": ["beam_source", "powered"],
        "positron_source": ["beam_source", "material_interaction"],
        "ion_source": ["beam_source", "powered"],
        "proton_source": ["beam_source", "powered"],
        "laser_source": ["beam_source", _PH, "powered"],
        "photon_source": ["beam_source", _PH],
        "generic_source": ["beam_source"],
        "experimental_target": ["beam_destination", "material_interaction"],
        "interaction_point": ["interaction_point", "virtual"],
        "beam_destination": ["beam_destination"],
    },
    "mechanical": {
        "girder": ["mechanical_support"],
        "support": ["mechanical_support"],
        "mover": ["mechanical_support", "movable", "powered"],
        "translation_stage": ["mechanical_support", "movable", "powered"],
        "rotation_stage": ["mechanical_support", "movable", "powered"],
        "fiducial": ["survey_reference"],
        "alignment_reference": ["survey_reference"],
    },
    "model": {
        # Model concepts. A drift may stand for a beam pipe, but says nothing physical by itself.
        "drift": [_P],
        "marker": ["virtual"],
        "reference_point": ["virtual"],
        "observation_point": ["virtual"],
        "thin_lens": [_P, "virtual"],
        "generic": [],
    },
}

TYPES: dict[str, list[str]] = {t: caps for fam in FAMILIES.values() for t, caps in fam.items()}
FAMILY_OF: dict[str, str] = {t: fam for fam, types in FAMILIES.items() for t in types}

# Spellings a model may use for a type (the v1 format's and common simulator words); normalised on read.
TYPE_ALIASES = {
    "dump": "beam_dump", "source": "generic_source", "rfcavity": "rf_cavity", "cavity": "rf_cavity",
    "monitor": "generic_monitor", "instrument": "generic_monitor", "hkicker": "corrector", "vkicker": "corrector",
    "sbend": "dipole", "rbend": "dipole", "bend": "dipole", "valve": "gate_valve", "ip": "interaction_point",
    "ict": "current_transformer", "dcct": "dc_current_transformer", "wcm": "wall_current_monitor",
    "blm": "beam_loss_monitor", "slm": "synchrotron_light_monitor", "otr": "screen", "yag": "screen",
}

# Families whose components normally correspond to a physical asset; the rest (model, virtual) do not.
PHYSICAL_FAMILIES = {"magnet", "rf", "diagnostic", "injection_extraction", "interception", "vacuum", "material",
                     "optical", "source_destination", "mechanical"}

# The filter groups of the synchronization view (docs/beam-asset-sync.md).
FILTER_GROUPS = {
    "magnets": {"magnet"}, "diagnostics": {"diagnostic"}, "vacuum": {"vacuum"}, "rf": {"rf"},
    "optics": {"optical"}, "mechanical": {"mechanical"},
    "interception": {"interception", "injection_extraction", "material"}, "sources": {"source_destination"},
}


def normalise_type(t: str) -> str:
    t = (t or "").strip().lower().replace("-", "_").replace(" ", "_")
    return TYPE_ALIASES.get(t, t)


def family(t: str) -> str:
    return FAMILY_OF.get(normalise_type(t), "generic")


def default_capabilities(t: str) -> list[str]:
    return list(TYPES.get(normalise_type(t), []))


def is_virtual(t: str, capabilities=()) -> bool:
    """A model concept with no physical object: never expected to bind to an asset."""
    return "virtual" in set(capabilities or default_capabilities(t)) or family(t) == "model"


# --------------------------------------------------------------------------- observables

# quantity → (unit, domain, plane). Domains: particle, optical, any. Quantities are lowercase dotted words.
OBSERVABLES: dict[str, tuple[str, str, str]] = {
    "beam.position.x": ("mm", "particle", "x"), "beam.position.y": ("mm", "particle", "y"),
    "beam.angle.x": ("mrad", "particle", "x"), "beam.angle.y": ("mrad", "particle", "y"),
    "beam.size.x": ("mm", "particle", "x"), "beam.size.y": ("mm", "particle", "y"),
    "beam.profile.x": ("", "particle", "x"), "beam.profile.y": ("", "particle", "y"),
    "beam.intensity": ("mA", "particle", "none"), "beam.charge": ("nC", "particle", "none"),
    "beam.energy": ("MeV", "particle", "none"), "beam.energy_spread": ("", "particle", "none"),
    "beam.loss": ("", "particle", "none"), "beam.bunch_length": ("ps", "particle", "z"),
    "beam.arrival_time": ("ps", "particle", "z"),
    "optical.power": ("W", "optical", "none"), "optical.energy": ("J", "optical", "none"),
    "optical.profile": ("", "optical", "none"), "optical.spectrum": ("", "optical", "none"),
    "optical.wavefront": ("", "optical", "none"), "optical.polarization": ("", "optical", "none"),
    "optical.pulse_duration": ("fs", "optical", "z"), "optical.position.x": ("mm", "optical", "x"),
    "optical.position.y": ("mm", "optical", "y"),
}

# How a diagnostic derives what it observes (§10). Free to extend; these are the ones viewers know.
MEASUREMENT_MODELS = {"centroid", "profile", "histogram", "integrated_charge", "current", "loss_rate", "spectrum",
                      "image", "time_of_arrival", "power", "energy", "wavefront", "polarization", "custom"}

# --------------------------------------------------------------------------- states (semantics, never live)

# Default state sets by type: name → meaning for the beam, the *first* being the state the static model
# assumes (normal operation: a valve open, a screen out, a stopper retracted). A component may declare its own.
DEFAULT_STATES: dict[str, dict[str, dict]] = {
    "gate_valve": {"OPEN": {"beam_passes": True}, "CLOSED": {"beam_passes": False},
                   "MOVING": {"beam_passes": False}, "FAULT": {"beam_passes": None}},
    "fast_valve": {"OPEN": {"beam_passes": True}, "CLOSED": {"beam_passes": False},
                   "MOVING": {"beam_passes": False}, "FAULT": {"beam_passes": None}},
    "screen": {"OUT": {"beam_passes": True}, "IN": {"beam_passes": False, "intercepts": True},
               "MOVING": {"beam_passes": None}},
    "beam_stopper": {"RETRACTED": {"beam_passes": True}, "INSERTED": {"beam_passes": False},
                     "MOVING": {"beam_passes": False}},
    "kicker": {"OFF": {"acts": False}, "READY": {"acts": False}, "ARMED": {"acts": True}, "FAULT": {"acts": None}},
    "scraper": {"OUT": {"limits_aperture": False}, "IN": {"limits_aperture": True}, "MOVING": {}},
    "wire_scanner": {"PARKED": {"intercepts": False}, "SCANNING": {"intercepts": True}},
}

# --------------------------------------------------------------------------- relations

# Relations between a model component and an external (Knowledge Hub) asset.
BINDING_RELATIONS = {
    "implemented_by": "the physical device that realises this model component (the normal binding)",
    "mounted_on": "the physical support, girder or stand this component sits on",
    "contained_in": "the physical assembly or chamber this component is part of",
    "measured_by": "the physical instrument that measures at this model location",
    "associated_with": "related, without a stronger claim",
}
# Relations between components inside a model (§13): mechanical and containment.
MODEL_RELATIONS = {"mounted_on", "contained_in", "references"}

# Aperture shapes (§7).
SHAPES = {"circle", "ellipse", "rectangle", "racetrack", "polygon", "custom"}
