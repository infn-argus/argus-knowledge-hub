# The ARGUS beam model format (`argus.beam-model/1`)

The one representation of an accelerator or beam-line model that ARGUS imports and exports. Simulator files
(MAD-X, Elegant, …) are turned into it by converters ([§ 9](#9-converters-from-simulator-files)); the hub's
core reads nothing else. This page is the reference; the machine-readable form is the JSON Schema in
[`beam-model.schema.json`](beam-model.schema.json), served live at `GET /v1/beam-model/schema` and generated
from the same model the importer validates with, so the two cannot drift apart. What the hub does with a
model is described in [beam-model.md](beam-model.md).

Units are SI unless a field says otherwise: metres, radians, m⁻² for `k1`, m⁻³ for `k2`, GeV for beam
energies, MeV/c² for rest masses.

## 1. A document

```json
{
  "format": "argus.beam-model/1",
  "model":       { … },
  "systems":     [ … ],
  "paths":       [ … ],
  "elements":    [ … ],
  "observables": [ … ],
  "datasets":    [ … ]
}
```

| Field | Required | What |
|---|---|---|
| `format` | yes | exactly `argus.beam-model/1` |
| `model` | yes | the model's identity and provenance ([§ 2](#2-model)) |
| `systems` | yes, ≥ 1 | machines: a ring, a linac, a laser line ([§ 3](#3-systems-and-beams)) |
| `paths` | yes, ≥ 1 | ordered sequences of elements a beam follows ([§ 4](#4-paths)) |
| `elements` | yes | the positions along the paths ([§ 5](#5-elements)) |
| `observables` | no | quantities diagnostics measure, beyond the built-in ones ([§ 6](#6-observables)) |
| `datasets` | no | values that depend on optics, a version or a time ([§ 7](#7-datasets-and-values)) |

Unknown fields are ignored. Ids are strings, unique within their list (the importer enforces it for elements), and are what the hub uses to
recognise the same thing on the next import: **keep them stable** across versions of a model.

## 2. `model`

| Field | Required | What |
|---|---|---|
| `id` | yes | stable identifier; importing the same `id` again updates the model and keeps its history |
| `name` | no | for people |
| `source` | no | where it comes from: a repository, a tool, a file |
| `version` | no | the model's version, e.g. `2026.1` |
| `git_commit` | no | the commit it was produced from |
| `simulator` | no | the simulator the values come from (`madx`, `elegant`, `xsuite`, …) |
| `dataset` | no | the dataset element-level values belong to ([§ 7.2](#72-values-written-on-elements)) |

## 3. `systems` and beams

| Field | Required | What |
|---|---|---|
| `id` | yes | |
| `name` | no | |
| `kind` | no (`Other`) | `Storage ring`, `Accumulator`, `Linac`, `Synchrotron`, `Transfer line`, `Laser transport`, … |
| `beams` | no | the beams it carries |

A beam: `id`, `name`, `kind` (`particle` or `photon`), and `parameters`, a free object. The ones the hub
shows: for particles `species`, `charge`, `reference_energy` (GeV), `reference_momentum` (GeV/c),
`rest_mass` (MeV/c²); for photons `wavelength` (nm), `pulse_energy`, `repetition_rate`.

## 4. `paths`

| Field | Required | What |
|---|---|---|
| `id` | yes | |
| `name` | no | |
| `system` | yes | the `id` of one of `systems` |
| `topology` | yes | `open` (a line) or `closed` (a ring: the last element is followed by the first) |
| `elements` | yes | element ids **in beam order** |
| `reference` | no | the element at `s = 0`; the first when not given |
| `length` | no | the path's length (a ring's circumference), m |
| `direction` | no | free text, e.g. `clockwise` |
| `branches` | no | `[{"at": "<element of this path>", "to_path": "<path id>"}]`: where another path leaves this one (an extraction septum, a beam splitter) |

**Each element is on one path.** A section two lines share is a path of its own that branches to both;
this keeps `s` unambiguous.

## 5. `elements`

| Field | Required | What |
|---|---|---|
| `id` | yes | the position's name in the model, e.g. `QUAA101` |
| `name` | no | defaults to `id` |
| `type` | yes | one of the normalised kinds below |
| `capabilities` | no | what it does; defaults by kind (below). Give it to say more, e.g. a corrector's plane |
| `observes` | no | for diagnostics: the quantities it measures ([§ 6](#6-observables)) |
| `s`, `geometry`, `physics`, `optics`, `native` | no | values, filed into a dataset ([§ 7.2](#72-values-written-on-elements)) |

### 5.1 Kinds

| `type` | Is (catalogue type) | Default capabilities |
|---|---|---|
| `drift` | Drift | beam_transport |
| `dipole` | Dipole | beam_transport, bending, powered, alignment_sensitive |
| `quadrupole` | Quadrupole | beam_transport, focusing, powered, alignment_sensitive |
| `sextupole` | Sextupole | beam_transport, chromatic_correction, powered, alignment_sensitive |
| `corrector` | Corrector | beam_transport, steering, powered |
| `kicker` | Kicker | beam_transport, steering, pulsed, powered |
| `septum` | Septum | beam_transport, branching, powered |
| `rf_cavity` | RF Cavity | beam_transport, acceleration, powered |
| `solenoid` | Solenoid | beam_transport, focusing, powered |
| `collimator` | Collimator | beam_transport, interceptive |
| `undulator` | Undulator | beam_transport, radiation |
| `bpm` | Beam Position Monitor | diagnostic, beam_position_measurement |
| `screen` | Screen Station | diagnostic, beam_profile_measurement, interceptive |
| `generic_monitor` | Generic Monitor | diagnostic |
| `source` | Beam Source | beam_source |
| `dump` | Beam Dump | beam_dump, interceptive |
| `mirror` | Mirror | photon_transport, steering, alignment_sensitive |
| `lens` | Lens | photon_transport, focusing, alignment_sensitive |
| `beam_splitter` | Beam Splitter | photon_transport, branching |
| `generic` | Generic Beam Element | — |

A simulator's own class (`HKICKER`, `CSBEND`, `KQUAD`) is not a kind: it goes in `native.type`. Capabilities
the hub reads: `horizontal_steering` and `vertical_steering` (which plane a corrector acts in; a steering
element with neither is reported with its plane unknown, never guessed), `pulsed`, `interceptive`.

## 6. `observables`

`{"quantity": "beam.position.x", "unit": "mm", "domain": "particle", "plane": "x"}`. Built in, so they need
no declaration: `beam.position.x`, `beam.position.y`, `beam.size.x`, `beam.size.y`, `beam.intensity`,
`beam.energy`, `beam.loss`, `optical.power`, `optical.profile`. A quantity is lowercase words separated by
dots. An element's `observes` must name built-in or declared quantities.

## 7. Datasets and values

Everything that depends on the optics, a version or a time — positions, strengths, Twiss functions — lives in
a dataset, so a design lattice, a measured one and next year's version can sit side by side on the same
positions.

| Field | Required | What |
|---|---|---|
| `id` | yes | |
| `name` | no | |
| `kind` | no (`design`) | `design`, `measured`, `operational`, `simulation`, … |
| `path` | yes | the path it gives values for |
| `source`, `version`, `git_commit` | no | provenance |
| `simulator`, `simulator_version` | no | what computed it |
| `generated_at`, `valid_from`, `valid_until` | no | ISO 8601 dates |
| `values` | no | `{ "<element id>": <values> }` |

### 7.1 Values

| Field | What |
|---|---|
| `s` | position of the element's **entry** along the path, m, from the path's `reference` |
| `geometry` | where the entry is in the hall: `x`, `y`, `z` (m), `yaw`, `pitch`, `roll` (rad). `yaw` is the heading in the horizontal plane, 0 along +x, counter-clockwise positive |
| `physics` | `length` (m) and the normalised strengths: `angle`, `e1`, `e2` (rad) for dipoles; `k1` (m⁻²) for quadrupoles; `k2` (m⁻³) for sextupoles; `kick` (rad) for correctors; `ks` for solenoids; `voltage`, `frequency`, `phase`/`lag`, `harmonic` for cavities |
| `optics` | `beta_x`, `beta_y` (m), `alpha_x`, `alpha_y`, `dx`, `dy` (m), `dpx`, `dpy`, `mux`, `muy` (tunes, in units of 2π) |
| `native` | `{"source": "madx", "type": "QUADRUPOLE", "parameters": {…}}`: the simulator's own type and parameters, kept whole |

Viewers draw to scale from these: the path unrolled along `s` with each element `length` wide, and the hall
layout from `geometry`. When a dataset has no geometry, the layout is computed from `s`, `length` and dipole
`angle` (a survey), and a ring whose bends sum to 2π closes.

### 7.2 Values written on elements

For a model with one dataset, the values can be written on the elements instead of in `datasets`
(`{"id": "QUAA101", "type": "quadrupole", "s": 1.43, "physics": {"length": 0.3, "k1": 4.3}}`). They are filed
into `model.dataset` when named (created as a design dataset when not in `datasets`), else into the first
dataset of the element's path, else into a design dataset made for that path.

## 8. Several models: bundles

```json
{"format": "argus.beam-model-bundle/1", "models": [ {"format": "argus.beam-model/1", …}, … ]}
```

A plain JSON list of models is accepted too. A bundle is imported **all or none**: if one model is invalid,
nothing is written and every problem is reported. `GET /v1/beam-model/export` writes a bundle; an export is
rebuilt from what the hub holds now (edits included, retired elements left out) and imports into another hub
as the same model.

### 8.1 What the importer refuses

* a `format` other than `argus.beam-model/1`, or a `model.id` with characters other than letters, digits,
  `.`, `_` and `-`;
* an element `type` outside [§ 5.1](#51-kinds), or two elements with the same id;
* a path naming an unknown system or element, or an element already on another path;
* a `topology` other than `open` or `closed`; a `reference` that is not one of the path's elements;
* a branch `at` an element not on its path, or to an unknown or empty path;
* a dataset for an unknown path, or with values for an unknown element;
* `observes` naming a quantity neither built in nor declared.

`POST /v1/beam-model/validate` runs these checks without writing.

## 9. Converters from simulator files

Converters are a separate layer, `backend/app/beam_converters/`: pure functions from a file's text to a
canonical document, with no database and no ledger, so the same code runs in the Accelerator Model Toolbox,
in a CI job, or behind `POST /v1/beam-model/convert`, which returns the converted model and a report to look at
**before** anything is imported. In the web app, **+ New → Beam model → Upload files** accepts simulator files
next to canonical JSON and converts them on upload.

| Converter | Reads | Notes |
|---|---|---|
| `madx` | `.madx`, `.seq`, `.str`, `.mad` | variables (`=`, deferred `:=`, `const`/`real`), arithmetic and functions, element definitions with inheritance, `SEQUENCE … ENDSEQUENCE` with `REFER` (centre, entry, exit) and `AT … FROM`, `LINE = (…)` with `n*` repetition and `-` reversal, `BEAM`, `USE`. Macros, `IF`/`WHILE`, `CALL` and `EXEC` are not executed: they are listed in the report |
| `madx-tfs` | `.tfs` | a TFS table (TWISS output): `NAME`, `KEYWORD`, `S`, `L`, `ANGLE`, `K1L`, `K2L` and the optics columns (`BETX`, `ALFX`, `DX`, `MUX`, …) |
| `elegant` | `.lte` | element definitions, `&` continuations, numbers or quoted RPN expressions with `sto` variables, `LINE = (…)` with repetition and reversal, `USE` |

What every converter does the same way:

* **Kinds** come from the simulator's class (`SBEND`/`CSBEND` → `dipole`, `HKICKER` → `corrector` acting in x,
  `MONITOR`/`MONI` → `bpm`, …). Only where the class cannot say (a corrector class used for a fast kicker, a
  bend used for a septum, a generic class) does the element's name refine it — `KCK…`/`KICK…` kicker, `SEP…`/`SPT…`
  septum, `BPM…`/`BPS…` bpm, `SCR…`/`OTR…`/`YAG…` screen; turn this off with the option `name_hints: false`.
* **Drifts and markers** are left out (their lengths still count in `s`); options `keep_drifts`, `keep_markers`.
* **`s`** is the entry: a centred `AT` becomes `AT − L/2`, a TFS row's `S` (the exit) `S − L`.
* **Repeated names** (a line using `QF` twice) become `QF`, `QF#2`, …
* **The survey** (geometry) is computed from lengths and bends, starting at the origin heading along +x.
* **Topology**: `auto` makes it a ring when the bends sum to ±2π; options `closed` or `open` override.
* **The simulator's own type and every parameter** are kept in `native`.

Options (all optional): `model_id`, `model_name`, `version`, `system_id`, `system_kind`, `topology`,
`beamline` (which sequence or line, when a file defines several; else the `USE`d one, else the last),
`species`, `reference_energy`, `keep_markers`, `keep_drifts`, `name_hints`.

The report says which converter read the file, how many elements it kept, the total bend, whether it is a
ring, how closely the survey closes (`survey_closure_m`), and, for MAD-X, the statements not executed.

### 9.1 Adding a converter

Write a module in `backend/app/beam_converters/` that registers itself; it is found at start-up.

```python
from app.beam_converters import Converter, Options, register
from app.beam_converters.common import Placed, build

def convert_bmad(text: str, filename: str, options: Options) -> dict:
    placed = [Placed(name="qf", kind="quadrupole", s=0.0, length=0.3, native_type="QUADRUPOLE",
                     native={"L": 0.3, "K1": 1.2}, physics={"k1": 1.2})]          # … parsed from text
    return build(placed, source="bmad", filename=filename, options=options, line_name="ring",
                 total_length=None, beam={"species": "electron", "reference_energy": 3.0})

register(Converter(name="bmad", label="Bmad lattice (.bmad)", extensions=(".bmad",),
                   detect=lambda text: "parameter[" in text.lower(), convert=convert_bmad))
```

`common.py` provides what converters share: a safe arithmetic evaluator (never `eval`), `LINE` expansion,
the survey, and `build`, which turns placed elements into a canonical document with the conventions above.
A converter only has to parse its format into `Placed` elements. Tests: `backend/tests/test_beam_converters.py`
reads the same ring written as MAD-X, Elegant and TFS (`backend/tests/fixtures/beam_model/`) and checks the
three give one model.
