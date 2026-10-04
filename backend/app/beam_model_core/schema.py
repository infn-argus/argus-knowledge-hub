"""The canonical beam model, `argus.beam-model/2`: the object model and its JSON form (`*.beam.json`).

    Document
    ├── model            identity and provenance of the model
    ├── facility         the facility it describes (the namespace external ids live in)
    ├── systems          beam systems: a ring, a linac, a transfer line, a laser transport
    ├── beams            what travels: particle or photon beams, any species, any number
    ├── paths            ordered placements of components (open or closed); a component may be placed on
    │                    several paths (a shared interaction region); `s` is a coordinate along a path
    ├── connections      how paths join: branch, merge, continue — the topology between paths is explicit
    ├── definitions      reusable component definitions (a magnet family, a simulator's element class)
    ├── components       instances: type, capabilities, parameters, geometry, boundaries, material, states,
    │                    measurement model, observes, mechanical relations, native data, provenance
    ├── observables      quantities beyond the built-in ones
    ├── datasets         values that depend on a configuration: optics, survey, orbit, apertures, fields
    │                    along a path (pressure, temperature, loss…) — design, measured, current model…
    ├── external_bindings  links to physical assets kept elsewhere (Knowledge Hub), with status and provenance
    └── provenance       where the document as a whole came from

Units are SI unless a field says otherwise (m, rad, m⁻² for k1, GeV for beam energies, MeV/c² for masses).
Unknown fields are kept (`extra="allow"`), so a tool's own annotations survive a round trip. Validation
beyond shape — references, vocabulary, completeness levels — is in `validation.py`.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "argus.beam-model/2"
BUNDLE_VERSION = "argus.beam-model-bundle/2"
ID_PATTERN = r"^\S(.*\S)?$"          # any name without leading or trailing space


class _Open(BaseModel):
    """Keeps fields it does not know: a tool's annotations travel with the model."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# --------------------------------------------------------------------------- provenance and native data

class ValueProvenance(_Open):
    """Where one value came from: `QUAA101.k1` ← MAD-X, strengths.str, symbol `qk1`, line 12."""
    source: Optional[str] = None          # a tool or format: madx, elegant, survey, measurement, person
    file: Optional[str] = None
    symbol: Optional[str] = None          # the variable or expression it was computed from
    expression: Optional[str] = None
    line: Optional[int] = None
    note: Optional[str] = None


class Native(_Open):
    """A simulator's own description of an object, kept whole: nothing is lost in normalisation."""
    format: Optional[str] = Field(default=None, validation_alias=AliasChoices("format", "source"))  # madx…
    file: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    location: Optional[str] = None        # file:line, or a path in the simulator's structure


# --------------------------------------------------------------------------- geometry and alignment

class Pose(_Open):
    """A position and orientation in the facility frame: x, y, z (m), yaw, pitch, roll (rad). `yaw` is the
    heading in the horizontal plane, 0 along +x, counter-clockwise positive."""
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    yaw: Optional[float] = None
    pitch: Optional[float] = None
    roll: Optional[float] = None
    frame: Optional[str] = None           # defaults to the facility frame


class Offset(_Open):
    dx: Optional[float] = None
    dy: Optional[float] = None
    dz: Optional[float] = None
    dyaw: Optional[float] = None
    dpitch: Optional[float] = None
    droll: Optional[float] = None


class Alignment(_Open):
    """Where the physical object is meant to be, where a survey found it, and the difference. All optional."""
    design: Optional[Pose] = None
    surveyed: Optional[Pose] = None
    offset: Optional[Offset] = None
    surveyed_at: Optional[str] = None
    survey: Optional[str] = None          # the survey campaign or dataset


class Geometry(_Open):
    """The physical object's geometry, independent of any simulator. The beam's reference trajectory at the
    component is a dataset value (`values.geometry`); `placement` is where the object itself is."""
    length: Optional[float] = None
    reference_point: Optional[Literal["entry", "centre", "exit"]] = None
    placement: Optional[Pose] = None
    alignment: Optional[Alignment] = None
    shape: Optional[str] = None           # a viewer hint: box, cylinder, mesh reference…


# --------------------------------------------------------------------------- boundaries, material, states

class Profile(_Open):
    """The transverse shape of the space available to the beam."""
    shape: Literal["circle", "ellipse", "rectangle", "racetrack", "polygon", "custom"]
    radius: Optional[float] = None                 # circle
    semi_axis_x: Optional[float] = None            # ellipse
    semi_axis_y: Optional[float] = None
    half_width_x: Optional[float] = None           # rectangle, racetrack
    half_height_y: Optional[float] = None
    corner_radius: Optional[float] = None          # racetrack
    points: Optional[list[list[float]]] = None     # polygon / custom: [[x, y], …] in m
    offset_x: Optional[float] = None
    offset_y: Optional[float] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def _complete(self):
        need = {"circle": ("radius",), "ellipse": ("semi_axis_x", "semi_axis_y"),
                "rectangle": ("half_width_x", "half_height_y"), "racetrack": ("half_width_x", "half_height_y"),
                "polygon": ("points",)}.get(self.shape, ())
        missing = [f for f in need if getattr(self, f) in (None, [])]
        if missing:
            raise ValueError(f"a {self.shape} profile needs {', '.join(missing)}")
        for f in ("radius", "semi_axis_x", "semi_axis_y", "half_width_x", "half_height_y"):
            v = getattr(self, f)
            if v is not None and v <= 0:
                raise ValueError(f"{f} must be positive")
        if self.shape == "polygon" and len(self.points or []) < 3:
            raise ValueError("a polygon needs at least three points")
        return self


class Boundary(_Open):
    """A restriction of the beam's space. On a component, `s_start`/`s_end` are relative to the component's
    entry (default: its whole length); on its own (`path` given) they are along that path. `component` names
    what physically produces it; `when_state` limits it to a state (a scraper IN, a valve's open bore)."""
    id: Optional[str] = None
    component: Optional[str] = None
    path: Optional[str] = None
    s_start: Optional[float] = None
    s_end: Optional[float] = None
    profile: Profile
    when_state: Optional[str] = None
    kind: Literal["physical", "model"] = "physical"
    note: Optional[str] = None

    @model_validator(mode="after")
    def _ordered(self):
        if self.s_start is not None and self.s_end is not None and self.s_end < self.s_start:
            raise ValueError("s_end is before s_start")
        return self


class Material(_Open):
    """What the beam meets, for engines that simulate interactions; the model only describes it."""
    material: str
    thickness: Optional[float] = None              # m
    density: Optional[float] = None                # g/cm³
    radiation_length: Optional[float] = None       # m (or g/cm² when `radiation_length_unit` says so)
    interaction_length: Optional[float] = None     # m
    orientation: Optional[dict[str, Any]] = None   # e.g. {"angle": 0.785} or a crystal plane
    composition: Optional[dict[str, float]] = None


class StateDef(_Open):
    """What a state means for the beam (`beam_passes`, `intercepts`, `limits_aperture`, `acts`)."""
    name: str
    meaning: dict[str, Any] = Field(default_factory=dict)
    description: Optional[str] = None


class StateMapping(_Open):
    """How a value read from an external signal maps to a state; the signal's identity lives elsewhere
    (Knowledge Hub), named by `signal` (a role such as `status`, or an external id)."""
    signal: Optional[str] = None
    value: Any
    state: str


class StateModel(_Open):
    """The states a component can be in. Never the current state: that is read from the control system."""
    states: list[StateDef]
    default: Optional[str] = None                  # the state the static model assumes (normal operation)
    mappings: list[StateMapping] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self):
        names = [s.name for s in self.states]
        if len(set(names)) != len(names):
            raise ValueError("a state is defined twice")
        for n in [self.default, *(m.state for m in self.mappings)]:
            if n is not None and n not in names:
                raise ValueError(f"state {n} is not one of {names}")
        return self


class MeasurementModel(_Open):
    """How a diagnostic derives its observables: centroid, profile, image, integrated charge… No channel
    names and no values: those are external bindings and the control system."""
    type: str
    observables: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- definitions and components

class ComponentDefinition(_Open):
    """A reusable definition (a family, a simulator's element class with its parameters). Instances name it
    and may override anything."""
    id: str = Field(pattern=ID_PATTERN)
    type: str
    name: Optional[str] = None
    capabilities: Optional[list[str]] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    geometry: Optional[Geometry] = None
    boundaries: list[Boundary] = Field(default_factory=list)
    material: Optional[Material] = None
    states: Optional[StateModel] = None
    native: Optional[Native] = None
    provenance: dict[str, ValueProvenance] = Field(default_factory=dict)


class Component(_Open):
    """A beamline component instance: a lattice position, a diagnostic, a valve, a mirror, a girder. Its
    identity does not depend on the physical device implementing it (that is an external binding)."""
    id: str = Field(pattern=ID_PATTERN)
    name: Optional[str] = None
    type: Optional[str] = None                     # from the definition when not given
    definition: Optional[str] = None
    family: Optional[str] = None                   # a model family name (e.g. QF), not the vocabulary family
    aliases: list[str] = Field(default_factory=list)
    capabilities: Optional[list[str]] = None       # defaults by type (and the definition's)
    parameters: dict[str, Any] = Field(default_factory=dict)
    geometry: Optional[Geometry] = None
    boundaries: list[Boundary] = Field(default_factory=list)
    material: Optional[Material] = None
    states: Optional[StateModel] = None
    measurement_model: Optional[MeasurementModel] = None
    observes: list[str] = Field(default_factory=list)
    mounted_on: Optional[str] = None               # a support, girder or mover (another component)
    contained_in: Optional[str] = None             # an assembly or chamber (another component)
    fiducials: list[str] = Field(default_factory=list)
    native: Optional[Native] = None
    provenance: dict[str, ValueProvenance] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    description: Optional[str] = None


# --------------------------------------------------------------------------- beams, systems, paths, topology

class Facility(_Open):
    id: str = Field(pattern=ID_PATTERN)
    name: Optional[str] = None
    namespace: Optional[str] = None                # prefix of stable component names: dafne/accumulator/QUAA101
    site: Optional[str] = None
    description: Optional[str] = None


class Beam(_Open):
    id: str = Field(pattern=ID_PATTERN)
    name: Optional[str] = None
    kind: Literal["particle", "photon"] = "particle"
    species: Optional[str] = None                  # electron, positron, proton, ion name, photon
    charge: Optional[float] = None                 # e (0 for photons and neutrals)
    rest_mass: Optional[float] = None              # MeV/c²
    reference_energy: Optional[float] = None       # GeV
    reference_momentum: Optional[float] = None     # GeV/c
    wavelength: Optional[float] = None             # nm
    systems: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class System(_Open):
    id: str = Field(pattern=ID_PATTERN)
    name: Optional[str] = None
    kind: Optional[str] = None                     # free: Storage ring, Linac, Transfer line, Laser transport…
    beams: list[str] = Field(default_factory=list)
    description: Optional[str] = None


class Placement(_Open):
    """One component's place on one path. `id` is needed only when the component appears on the path more
    than once; `s` and `length` here are a convenience for a model with one dataset."""
    component: str
    id: Optional[str] = None
    s: Optional[float] = None
    length: Optional[float] = None
    reversed: bool = False                         # passed backwards (a counter-rotating beam)


class Path(_Open):
    """An ordered route through components. `placements` is the order — the topology inside the path;
    `s` is a coordinate along it, never its identity."""
    id: str = Field(pattern=ID_PATTERN)
    name: Optional[str] = None
    system: Optional[str] = None
    beams: list[str] = Field(default_factory=list)
    topology: Literal["open", "closed"] = "open"
    placements: list[Union[str, Placement]] = Field(default_factory=list)
    reference: Optional[str] = None                # the component (or placement id) at s = 0
    length: Optional[float] = None
    direction: Optional[str] = None
    medium: Optional[Literal["particle", "photon", "mixed"]] = None

    @field_validator("placements", mode="before")
    @classmethod
    def _items(cls, v):
        return [Placement(component=x) if isinstance(x, str) else x for x in (v or [])]

    def placement_list(self) -> list[Placement]:
        return [p if isinstance(p, Placement) else Placement(component=p) for p in self.placements]


class Endpoint(_Open):
    path: str
    component: Optional[str] = None                # the component (or placement id); default: the path's end


class Connection(_Open):
    """How paths join. `branch`: from a component on one path to the start of another (a septum, a switch, a
    beam splitter). `merge`: from the end of a path into a component on another (injection). `continue`: one
    path's end leads to another's start (an injector chain)."""
    kind: Literal["branch", "merge", "continue"]
    from_: Endpoint = Field(alias="from")
    to: Endpoint
    note: Optional[str] = None


# --------------------------------------------------------------------------- observables and datasets

class Observable(_Open):
    quantity: str = Field(pattern=r"^[a-z]+(\.[a-z_]+)+$")
    unit: Optional[str] = None
    domain: Optional[Literal["particle", "optical", "any"]] = None
    plane: Optional[Literal["x", "y", "z", "none"]] = None
    description: Optional[str] = None


class Values(_Open):
    """The values of one component (or placement) in one dataset."""
    s: Optional[float] = None
    geometry: Optional[Pose] = None                # the reference trajectory at the entry
    physics: dict[str, Any] = Field(default_factory=dict)
    optics: dict[str, Any] = Field(default_factory=dict)
    native: Optional[Native] = None
    provenance: dict[str, ValueProvenance] = Field(default_factory=dict)


class FieldAlongPath(_Open):
    """A quantity as a function of `s` along a path: pressure, temperature, radiation, loss, field. Model or
    snapshot data — never a telemetry stream."""
    quantity: str
    path: str
    unit: Optional[str] = None
    samples: list[list[float]]                     # [[s, value], …], s increasing
    interpolation: Literal["linear", "step", "none"] = "linear"
    description: Optional[str] = None

    @field_validator("samples")
    @classmethod
    def _sorted(cls, v):
        if any(len(p) != 2 for p in v):
            raise ValueError("each sample is [s, value]")
        if any(b[0] < a[0] for a, b in zip(v, v[1:])):
            raise ValueError("samples must be in increasing s")
        return v


class Dataset(_Open):
    id: str = Field(pattern=ID_PATTERN)
    name: Optional[str] = None
    kind: str = "design"                           # design, nominal, commissioning, measured, current_model…
    category: Optional[str] = None                 # optics, survey, orbit, aperture, field_map, envelope, vacuum…
    path: Optional[str] = None
    source: Optional[str] = None
    version: Optional[str] = None
    git_commit: Optional[str] = None
    simulator: Optional[str] = None
    simulator_version: Optional[str] = None
    generated_at: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Values] = Field(default_factory=dict)        # component id or placement id → values
    fields: list[FieldAlongPath] = Field(default_factory=list)
    boundaries: list[Boundary] = Field(default_factory=list)      # an aperture model for this configuration


# --------------------------------------------------------------------------- bindings to external assets

BINDING_STATUSES = ("unmatched", "proposed", "confirmed", "ambiguous", "rejected")
AUTHORITY = ("authoritative", "human_confirmed", "auto_accepted", "suggestion")


class AssetRef(_Open):
    namespace: str = "kh"                          # kh = ARGUS Knowledge Hub
    id: str                                        # the asset's stable id (a uid in the hub)
    name: Optional[str] = None


class BindingSource(_Open):
    method: str = "asset_sync"                     # asset_sync, manual, imported, authoritative_source
    matcher: Optional[str] = None
    matcher_version: Optional[str] = None


class ExternalBinding(_Open):
    component: str
    relation: str = "implemented_by"
    target: AssetRef
    status: Literal["proposed", "confirmed", "ambiguous", "rejected"] = "confirmed"
    authority: Optional[Literal["authoritative", "human_confirmed", "auto_accepted", "suggestion"]] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    evidence: list[Any] = Field(default_factory=list)
    source: Optional[BindingSource] = None
    confirmed_by: Optional[dict[str, Any]] = None
    timestamp: Optional[str] = None


# --------------------------------------------------------------------------- the document

class ModelInfo(_Open):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
    name: Optional[str] = None
    source: Optional[str] = None
    version: Optional[str] = None
    git_commit: Optional[str] = None
    simulator: Optional[str] = None
    dataset: Optional[str] = None                  # where component-level values are filed
    description: Optional[str] = None


class Document(_Open):
    schema_version: Literal["argus.beam-model/2"] = Field(validation_alias=AliasChoices("schema_version", "format"))
    model: ModelInfo
    facility: Optional[Facility] = None
    systems: list[System] = Field(default_factory=list)
    beams: list[Beam] = Field(default_factory=list)
    paths: list[Path] = Field(default_factory=list)
    connections: list[Connection] = Field(default_factory=list)
    definitions: list[ComponentDefinition] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    boundaries: list[Boundary] = Field(default_factory=list)
    observables: list[Observable] = Field(default_factory=list)
    datasets: list[Dataset] = Field(default_factory=list)
    external_bindings: list[ExternalBinding] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> dict:
        """The document as JSON, as it would be written to a `.beam.json` file."""
        out = self.model_dump(mode="json", by_alias=True, exclude_none=True, exclude_defaults=False)
        out["schema_version"] = SCHEMA_VERSION
        return _prune(out)


def _prune(x):
    """Drop empty collections and default-only noise so a written document stays readable."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            v = _prune(v)
            if v in ({}, []) and k not in ("placements", "states", "samples", "points", "values"):
                continue
            if k == "reversed" and v is False:
                continue
            out[k] = v
        return out
    if isinstance(x, list):
        return [_prune(v) for v in x]
    return x


def json_schema() -> dict:
    out = Document.model_json_schema(by_alias=True)
    out["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    out["$id"] = "https://argus.infn.it/schemas/argus.beam-model-2.json"
    out["title"] = "ARGUS canonical beam model (argus.beam-model/2)"
    return out
