# The beam model

ARGUS links the real facility it knows — equipment, controls, documentation, maintenance, history — to a
**simulator-independent physics model** of its accelerators, beamlines, rings, linacs, transfer lines and
laser transport. It does not become a simulator, and a lattice file never becomes the authority on equipment.

* **The canonical format** is `argus.beam-model/2` ([beam-model-format.md](beam-model-format.md)). Its pure
  library is `backend/app/beam_model_core/`, which the Accelerator Model Toolbox runs too.
* **Matching** model components to physical assets: [beam-asset-sync.md](beam-asset-sync.md).
* **Hub code:**
  * `backend/app/services/beam_model.py` (queries, v1 rules);
  * `backend/app/services/beam_model_v2.py` (import, storage, export);
  * `backend/app/services/beam_asset_sync.py`;
  * `backend/app/routers/beam_model.py`;
  * `backend/app/models/beam_model.py`.
* **Fixtures:** `backend/tests/fixtures/beam_model/`.
* **Tests:**
  * `test_beam_model.py` (the hub, v1 documents);
  * `test_beam_model_core.py` (the library: ring, linac, branches, laser, apertures, collider);
  * `test_beam_asset_sync.py` (sync and v2 in the hub);
  * `test_beam_converters.py`.

## 1. Five layers, kept apart

```
 PHYSICS MODEL        Beam System ── Beam ── Beam Path ── Beam Element ─observes→ Observable
 (positions)                                    │ s, geometry, k1, Twiss …: in a Model Dataset
                                                │
                                   installed at │ (an Installation, valid from … until …)
                                                ▼
 PHYSICAL EQUIPMENT                        Physical asset (magnet, pickup, mirror …)
                                                │ powers / connected to / acts on
                                                ▼
 CONTROLS               Power supply · Electronics ←acts on─ Control Device ─provided by→ IOC
                                                                 ▲
                                                 Control Signal ─┘ signal of      ─measures→ Observable
                                                   (PV identity)   ─signal for→ Beam Element
 DOCUMENTATION /        manuals, calibrations, procedures, tickets, maintenance, installation history
 KNOWLEDGE              — attached to the physical asset (and its type and product model)

 TELEMETRY              outside ARGUS: EPICS, !CHAOS, Archiver Appliance, Prometheus hold the values
```

ARGUS answers *“which signal is BPM01’s horizontal position?”*. A live-data service answers *“what is it
now?”*. No value of a signal is ever stored.

## 2. What represents what

Every concept reuses an existing mechanism where one fits:

| Requested concept | In ARGUS | Why |
|---|---|---|
| BeamElement | a record of a **Beam Element** type (functional plane): Quadrupole, Dipole, Septum, BPM, Mirror… | The catalogue already separates functional positions (plane A) from physical assets (plane B). |
| BeamSystem | record of type **Beam System** (functional plane) | — |
| Beam | **Particle Beam** / **Photon Beam** (under abstract **Beam**) | Different parameters per kind, none required. |
| BeamPath | record of type **Beam Path**: `topology` open/closed, `length`, `direction` | Topology itself is relations (§4). |
| Diagnostic | a Beam Element whose kind is `bpm`, `screen`, `generic_monitor` (or capability `diagnostic`) | Diagnostics are positions like any other; the hardware is installed at them. |
| Observable | record of type **Observable** (catalogue plane, shared) keyed by `quantity` | A vocabulary every workspace can use. |
| ModelDataset | record of type **Model Dataset** (provenance attributes) + rows of `beam_model_values` | §3. |
| ModelElementBinding | an **Installation** (`installed at` the position, `installation of` the asset, valid from/until) and the derived `realized by` | §5. |
| Control signal identity | record of type **Control Signal** (`address`, `role`, `signal_system`, `unit`) | Identities only. |
| Provenance, history, review | the fact ledger: claims with rule ids, decisions, the review queue, the guard |
| Vacuum, material, optical and support components (v2) | **Vacuum Element**, **Material Element**, **Optical Element**, **Support Element** (functional plane, installable); the fine type is `element_kind` (`gate_valve`, `foil`, `iris`, `girder`…), the family `component_family` | Four generic positions instead of a catalogue type per kind; the vocabulary is the model's |
| The whole document | a row of `beam_model_documents` per revision (the newest `current`) | What the ledger does not hold — definitions, boundaries, materials, states, measurement models, alignment, fields along paths, bindings — comes back whole in an export, and the model's own queries run on it |
| Asset bindings with confidence and provenance | rows of `beam_asset_bindings` (status, authority, confidence, evidence, matcher, decision); a confirmed `implemented_by` is also an Installation | [beam-asset-sync.md](beam-asset-sync.md) | §6. |

## 3. Datasets: what depends on the optics

`s`, the placement (`x y z yaw pitch roll`), the normalised physics parameters (`length`, `k1`, `angle`…),
the optics (`beta_x beta_y alpha_x alpha_y dx dpx mux muy`…) and the simulator’s own type and parameters
change with the lattice version, the optics in use and the measurement. They are **never attributes of the
element or of the hardware**. They are rows of `beam_model_values`, one per *(dataset, element, path)*:

| column | meaning |
|---|---|
| `dataset_uid` | the Model Dataset (design, nominal, current model, measured, commissioning, configuration) |
| `subject_uid`, `path_uid` | the element, and the path its `s` is along |
| `s`, `x … roll` | coordinate along the path, and placement in the hall |
| `physics`, `optics`, `native` | JSON: normalised parameters, optics functions, the simulator’s own `{source, type, parameters}` |

They are not ledger claims: they are a model’s output, not facts about the facility. The dataset record
carries the provenance (`source`, `version`, `git_commit`, `simulator`, `simulator_version`,
`generated_at`, `valid_from`/`valid_until`). Importing a dataset again replaces its rows.

## 4. Topology and relations

`s` orders and places elements; **it is never the topology**. A path’s elements are joined by relations:

| Relation (stored as) | Layer · failure | Meaning |
|---|---|---|
| `upstream of` (element → next element) | beam · forward, degradation | *existing*. Consecutive elements of a path. With v2 these edges are the network of every path together; a path's own order is its `sequence` attribute (placement ids). |
| `merges into` (end of a path → where it joins) | beam · forward, degradation | **v2**. Injection. |
| `continues to` (end of a path → next path's start) | beam · forward, degradation | **v2**. An injector chain. |
| `placed on` (component → every path it is on) | provenance · none | **v2**. A component may be on several paths (a shared interaction region); `part of` still names its first. |
| `mounted on` (component → support component or physical support) | mechanical · reverse, degradation | **v2**. At most one; acyclic. The support moving misaligns what it carries. |
| `contained in` (component → assembly or chamber) | mechanical · reverse, degradation (weak) | **v2**. At most one; acyclic. |
| `fiducial of` (fiducial → component or support) | provenance · none | **v2**. |
| `measured by`, `associated with` (component → physical asset) | provenance · none | **v2**. Bindings other than `implemented_by`. |
| `branches to` (branch point → first element of a branch path) | beam · forward, degradation | **new**. A septum, a switchyard, a beam splitter. |
| `closes to` (last element of a closed path → its first) | beam · forward, degradation | **new**. A ring has no end; at most one per element each way. |
| `part of` (element → path, path → system) | membership · forward, degradation (weak) | *existing*. One container each: a branch is its own path. |
| `starts at` (path → reference element) | provenance · none | **new**. Where `s = 0`. |
| `beam of` (beam → beam system) | provenance · none | **new**. |
| `models` (model dataset → beam path) | provenance · none | **new**. |
| `observes` (diagnostic element → observable) | provenance · none | **new**. Knowing is not depending. |
| `signal of` (control signal → control device or IOC) | control · reverse, control | **new**. The device stops, the signal is gone. |
| `signal for` (control signal → element or asset) | provenance · none | **new**. Whose quantity it carries. |
| `measures` (control signal → observable) | provenance · none | *existing*. |
| `connected to` (pickup/sensor → electronics) | control · forward, control | **new**. The pickup fails, the reading is gone. |
| `installed at` / `installation of` / `realized by` | — | *existing*. The binding (§5). |
| `powers` (supply → element or magnet), `acts on` (device → asset), `provided by` (device → IOC), `located in` | — | *existing*. “powered by”, “controlled by” are these read backwards. |

Every new relation is classified in `services/causal_model.py` (so impact and root-cause analysis walk it
correctly) and given endpoint rules in `ledger/registry.py` (`closes to` 1:1, `starts at`/`signal of`/
`models` at most one per source).

A branch, e.g. a laser splitter:

```
main:        LSR01 → MIR01 → LNS01 → BSP01 → IP01          (upstream of)
                                        │
                                        └─ branches to ─→ CAM01   (path “diagnostic”, own s or none)
```

## 5. Positions and hardware: the binding

A physics position (`QUAA101`) stays while the magnet installed there changes. That is the existing
Installation model, unchanged: an Installation says *this asset was at this position from … until …*,
and the derive stage keeps `realized by` pointing at the current one.

| Binding state | In the ledger |
|---|---|
| **confirmed** | an Installation a person confirmed, covering now |
| **historical** | a confirmed Installation whose validity has ended |
| **proposed** | an Installation proposed by name matching (rule `beam-model.bind-by-name/1`), waiting in the review queue |
| **rejected / withdrawn** | a proposal a person rejected, or whose evidence went away |

Equal names never make the same thing. `POST /v1/model-bindings/propose` only *proposes*: a physical asset
whose name names exactly one position, the position having nothing installed or proposed. Confirming,
rejecting and swapping use the Installation endpoints (`/v1/installations/{uid}/confirm|reject`,
`/v1/installations/swap`). Every Beam Element kind where hardware is installed is an installable position
(`engine.INSTALLABLE`); a Drift is not.

## 6. Provenance and governance

The canonical import writes ledger claims, `method: stated`, rule `beam-model.canonical/1`, with the
model’s id, source, version and commit as evidence, into the stream `beam-model:<workspace>:<model>`:

* importing the same model again changes nothing; an element it no longer lists is **retired**, keeping its
  history and its installations;
* a revision that would retire too much is **held** by the ledger’s guard until someone approves it;
* who brings a model decides, once, at its first import, how it is governed: a model **pushed by a machine**
  (an API token: the Accelerator Model Toolbox) is an external source and waits (`awaiting_policy: true`)
  until governance activates an authority policy that covers it (`POST /v1/ledger/policy/activate`); a model
  a **signed-in person** uploads or writes in ARGUS is theirs, as a record they create is, and takes effect at
  once. Every revision names who brought it.

## 7. API

All under the usual workspace header and permissions (`read`, `create`, `approve`).

| Endpoint | Answers |
|---|---|
| `POST /v1/beam-model/import` | import or update one model, a bundle or a list — all or none (422 with the problems when one is invalid) |
| `POST /v1/beam-model/validate` | check models without writing: each one's problems, or what it holds |
| `POST /v1/beam-model/convert` | a simulator file (MAD-X, TFS, Elegant…) converted to a canonical model, checked, with a report — nothing written |
| `GET /v1/beam-model/formats` | what can be read: canonical JSON and each installed converter |
| `GET /v1/beam-model/schema` | the JSON Schema of `argus.beam-model/1` |
| `GET /v1/beam-model/models` | the models in the workspace, with what each holds |
| `GET /v1/beam-model/models/{id}/export` | one model as canonical JSON, from what the hub holds now |
| `GET /v1/beam-model/export?model=…` | several models (all when none is named) in one bundle |
| `GET /v1/beam-systems`, `/{uid}` | systems with their beams and paths |
| `GET /v1/beam-paths?system=`, `/{uid}` | paths, their system and datasets |
| `GET /v1/beam-paths/{uid}/graph?dataset=` | ordered nodes (`s`, length, bend angle, geometry and β/D from the dataset — design by default), edges, `branches_out`, `branches_in` |
| `GET /v1/beam-paths/{uid}/elements` | the nodes alone |
| `GET /v1/beam-elements?path=&kind=&q=`, `/{uid}` | elements (in beam order on a path) |
| `GET /v1/beam-elements/{uid}/context?dataset=` | the selection panel: physics and optics per dataset, hardware installed and its history, power, controls, documentation, tickets, observables, neighbours |
| `GET /v1/beam-elements/{uid}/upstream?n=`, `/downstream?n=` | nearest first, across branches and round rings |
| `GET /v1/beam-elements/{uid}/between/{other}` | the elements in between (the shorter way round in a ring) |
| `GET /v1/beam-elements/{uid}/equipment?at=` | installed now, or at a past instant, and the full history |
| `GET /v1/beam-elements/{uid}/controls` | units, power supplies, control devices, IOCs, signals, connected electronics |
| `GET /v1/beam-elements/{uid}/observables` | what it observes, and the signals that carry each |
| `GET /v1/beam-elements/{uid}/diagnostics?n=` | the nearest diagnostics up- and downstream |
| `GET /v1/beam-elements/{uid}/correctors?plane=x` | steering elements upstream acting in a plane |
| `GET /v1/diagnostics?path=&observable=` | diagnostic positions, filtered by observable |
| `GET /v1/observables`, `/{quantity}` | observables; who observes and which signals measure one |
| `GET /v1/model-datasets?path=`, `/{uid}` | datasets and their values in `s` order |
| `GET /v1/model-bindings?state=` | every binding with its state |
| `POST /v1/model-bindings/propose` | propose bindings by name (review queue) |
| `POST /v1/model-bindings` | a person binds a position to hardware from a date (confirmed) |
| `POST /v1/beam-model/signals` | a control signal’s identity: PV, role, device, element, observable |
| `GET /v1/beam-model/schema?version=2` | the JSON Schema of `argus.beam-model/2` (`?version=1`: the old one) |
| `GET /v1/beam-model/models/{id}/export?format=` | the model in its own format, or `1` / `2` (v2: the stored document with the hub's confirmed bindings) |
| `GET /v1/beam-models/{id}/document` | the stored v2 document, its revision and its validation (completeness levels, warnings, gaps) |
| `GET /v1/beam-models/{id}/aperture?path=&from=&to=&dataset=&state=C:S` | the limiting aperture between two components and what produces it |
| `GET /v1/beam-models/{id}/components/{c}/alignment` | what it is mounted on, what moves with it, its fiducials, design/surveyed/offset |
| `POST /v1/beam-models/{id}/asset-sync/preview`, `/apply`; `GET …/asset-sync/status`, `…/asset-bindings` | asset synchronization ([beam-asset-sync.md](beam-asset-sync.md)) |

## 8. The canonical representation

**The current format is `argus.beam-model/2`: the full reference is [beam-model-format.md](beam-model-format.md)**,
with the JSON Schema [beam-model.schema.json](beam-model.schema.json). What follows is the v1 form, still
imported (held to the v1 rules, then upgraded) and exported on request (`?format=1`; a v1 client's
edit keeps what v1 cannot say). Its schema is [beam-model-1.schema.json](beam-model-1.schema.json). The hub's core reads only this; simulator files are turned
into it by converters — the ones in `app/beam_converters/` (MAD-X, TFS, Elegant, extensible) or the
Accelerator Model Toolbox for the rest (Xsuite, Bmad, AT, laser optics tools…). Normalised kinds: `drift dipole quadrupole sextupole corrector kicker septum rf_cavity bpm screen
source dump mirror lens beam_splitter generic_monitor generic` (plus `solenoid collimator undulator`). A
simulator’s own type goes in `native.type`, its parameters in `native.parameters`: nothing is lost.

```json
{
  "format": "argus.beam-model/1",
  "model": {"id": "dafne-accumulator", "name": "DAΦNE Accumulator", "source": "accelerator-model-toolbox",
            "version": "2026.1", "git_commit": "1a2b3c4", "simulator": "madx"},
  "systems": [{"id": "dafne-accumulator", "name": "DAΦNE Accumulator", "kind": "Accumulator",
               "beams": [{"id": "e-", "kind": "particle",
                          "parameters": {"species": "electron", "charge": -1, "reference_energy": 0.51}}]}],
  "paths": [
    {"id": "accumulator-ring", "system": "dafne-accumulator", "topology": "closed", "length": 32.56,
     "reference": "SEPA101", "elements": ["SEPA101", "KCKA101", "QUAA101", "SXTA101", "BPSA101", "…"],
     "branches": [{"at": "SEPA102", "to_path": "extraction-line"}]},
    {"id": "extraction-line", "system": "dafne-accumulator", "topology": "open",
     "elements": ["QUAT101", "BPST101", "DHPT101", "DMPT101"]}],
  "elements": [
    {"id": "QUAA101", "type": "quadrupole",
     "capabilities": ["beam_transport", "focusing", "powered", "alignment_sensitive"],
     "native": {"source": "madx", "type": "QUADRUPOLE", "parameters": {"L": 0.3, "K1": 4.30926}}},
    {"id": "BPSA101", "type": "bpm", "observes": ["beam.position.x", "beam.position.y"]}],
  "observables": [{"quantity": "beam.position.x", "unit": "mm", "domain": "particle", "plane": "x"}],
  "datasets": [{"id": "design-2026", "kind": "design", "path": "accumulator-ring", "simulator": "madx",
                "values": {"QUAA101": {"s": 30.473, "geometry": {"x": 5.1, "y": 0.4},
                                       "physics": {"length": 0.3, "k1": 4.30926},
                                       "optics": {"beta_x": 3.66, "beta_y": 4.67, "dx": 0.38}}}}]
}
```

Rules the importer enforces: unique element ids; each element on **one** path (a branch has its own
elements); references to known systems, paths and elements; topology `open` or `closed`; observed
quantities declared (or one of the built-in ones). Element-level `s`/`physics`/`native` go into
`model.dataset` when named, else the first dataset of the element’s path, else a design dataset made for it.

Several models travel together in a **bundle**: `{"format": "argus.beam-model-bundle/1", "models": [...]}`
(a plain list of models is accepted too). An export is canonical JSON rebuilt from what the hub holds now, so
it carries edits made since the import, leaves out retired elements, and imports into another hub as the
same model.

## 9. In the web app

* **Beam model** (left menu): systems and paths, and the selected path drawn **to scale** — *Layout*, the path
  in the hall (the dataset's geometry, or the survey of lengths and bends; dipoles drawn as the arcs they bend),
  pan and zoom with a scale bar; and *Unrolled*, along `s` with every element its length wide, labels on leader
  lines and β functions under the line when the dataset has them. Each kind has its own glyph and colour;
  the chips (with counts) hide and show kinds, *Names* the labels. Branches, and the panel of a selected
  element. *Export all*, and per model *edit* and *export*.
* **+ New → Beam model**:
  * **Upload files** takes several files at once:
    * canonical JSON (v2 or v1, models or bundles);
    * simulator files (MAD-X, TFS, Elegant, Bmad, Xsuite, Accelerator Toolbox), converted on upload with a
      report: components, ring or line, survey closure, statements not executed.

    It checks every model with the server, showing levels and warnings, and imports them all or none.
  * **Write a model** is the `argus.beam-model/2` editor:
    * the model and its facility; beams; systems;
    * paths, each with a placement table (component, type from the vocabulary, `s`, length, strength,
      observes, passed backwards, the other paths it is on). Values go into the path's first dataset, or a
      design dataset made for it. An existing component can be placed on another path;
    * connections (branch, merge, continue);
    * components on no path (girders, supports, fiducials);
    * definitions: type, name, length, parameters, capabilities, boundaries and material, with the components
      that use each. A definition can be made from a component (its description moves into it); removing one
      leaves its instances with what it gave them;
    * datasets: kind, category, path, source, version, simulator, dates; every value as a grid (`s`, the
      reference trajectory, physics and optics columns, more columns on request); fields along a path as
      `s value` samples, and the dataset's own aperture model. Each path's placement table writes into the
      dataset chosen for it;
    * boundaries along a path: an aperture no single component produces, or one a simulator gives as its own
      element, with its `s` range, the component producing it (if any), its kind (physical or model) and the
      state it applies in;
    * a panel per component: aliases, family, definition, capabilities, observables and measurement model,
      supports, containment and fiducials, boundaries of any shape (and the state they apply in), alignment
      (reference point, the object's pose in the hall, design and surveyed poses, the offset — computed from
      the survey on request — survey date and campaign), material, states, parameters.

    *Check* shows the completeness levels and what each missing level needs. What the editor does not show is
    kept and saved as it came: bindings, provenance, a tool's own fields. Editing an existing model loads its v2 export and saves it back as an import, so its
    history stays. The page uses `GET /v1/beam-model/vocabulary` and `POST /v1/beam-model/upgrade` (a v1
    file opened in the editor).

## 10. Examples

**Quadrupole.** `QUAA101` (Quadrupole, path *Accumulator ring*). Physics from *Design optics 2026*:
`s = 3.186`, `L = 0.3`, `k1 = 4.30926`, native MAD-X `QUADRUPOLE {L, K1}`. Hardware: Magnet Assembly
s/n Q-0001 installed from 2025-01-01, swapped for Q-0007 on 2026-03-01 (`/equipment?at=2025-06-01` gives
Q-0001). Power: the supply that `powers` it. Controls: the Control Device that `acts on` the supply,
`provided by` its IOC, and its signals (`…:CURRENT:SP` setpoint, `…:CURRENT:RB` readback, `…:STATUS`).
Documentation and tickets: those of the installed magnet, its type and product model.

**BPM.** `BPM01` observes `beam.position.x` and `beam.position.y`. Installed: a stripline pickup,
`connected to` its Libera electronics, which a Control Device `acts on`, `provided by` an IOC. Signals
`LINAC:BPM01:X` and `LINAC:BPM01:Y` are each `signal for` BPM01 and `measures` one observable — one physical
diagnostic, several observables. Design optics at BPM01 (`beta_x`, `beta_y`) come from the dataset.

**Screen.** `SCR01` (kind `screen`, capabilities `diagnostic`, `beam_profile_measurement`, `interceptive`)
observes `beam.size.x`, `beam.size.y`, `beam.energy`; the screen station hardware (screen, camera, actuator)
is installed at it as for any position.

**Laser camera.** `CAM01` (kind `generic_monitor`, native Zemax `DETECTOR`) on the *Diagnostic leg*, reached
by `branches to` from the beam splitter `BSP01`, observes `optical.profile` and `optical.power`. It has no
`s`: none is needed to know it is downstream of the splitter.

## 11. Queries

| Question | How |
|---|---|
| What is immediately upstream of BPM01? | `/beam-elements/{BPM01}/upstream` |
| What elements are between QUAA101 and BPSA101? | `/beam-elements/{QUAA101}/between/{BPSA101}` |
| Which diagnostics observe the horizontal orbit in this section? | `/diagnostics?path={path}&observable=beam.position.x` |
| Which correctors act on x upstream of BPM01? | `/beam-elements/{BPM01}/correctors?plane=x` |
| What physical magnet implements QUAA101? What powers it? Which IOC? Which readback channel? | `/beam-elements/{QUAA101}/controls` (or `/context`) |
| What documentation exists for the installed magnet? | `/beam-elements/{QUAA101}/context` → `documentation` |
| What physical diagnostic implements BPM01, what electronics? | `/controls` → `units`, `connected_electronics` |
| Which signal corresponds to beam.position.x at BPM01? | `/beam-elements/{BPM01}/observables` → `measured_by` |
| Which model contains QUAA101? | `/beam-elements/{QUAA101}` → `path`; the path’s system and datasets |
| What are the design optics at BPM01? | `/context` → `physics.optics` (or `/model-datasets/{uid}`) |
| What is installed at QUAA101 now, and last year? | `/beam-elements/{QUAA101}/equipment`, `?at=2025-10-01` |

## 12. Boundaries kept

1. ARGUS does not simulate; it keeps what a model says, versioned.
2. A model is not the authority on equipment: it names positions; hardware is installed at them by
   Installations a person confirms.
3. A name is not an identity: name matches are proposals.
4. Positions and hardware stay separate records.
5. No telemetry: signals are identities.
6. Imports keep provenance (rule, model, version, commit) and history; new sources pass governance.
7. Simulator-specific information is kept whole (`native`). Converters are a separate, pure layer
   (`app/beam_converters/`): they produce canonical JSON for a person to check; the core reads nothing else.
8. One model for electron and positron rings, protons and ions, linacs, synchrotrons, transfer lines and
   laser transport: the fixtures are a ring, a linac and a laser line.

## 13. Known limits

* **One path per element — v1 only.** A v1 section shared by two lines is its own path that branches to both.
  v2 places a component on several paths (`placed on`), each with its own `s`; the hub's per-path queries use
  the path's `sequence`.
* **The ledger holds what the hub reasons on.** Records, topology, observables and bindings are claims. The
  rest of a v2 document — boundaries, materials, states, definitions, alignment, fields along paths — lives
  in the stored document. It is served whole (`/document`, `/export?format=2`) and queried there (aperture,
  alignment), but not as ledger facts with their own history: a new import replaces it, and earlier
  revisions are kept as rows.
* **Hand edits of hub records** (renaming a position in the catalogue) appear in a v1 export, which is rebuilt
  from the ledger, but not in the stored v2 document until the model is imported again.
* **Corrector planes** come from capabilities (`horizontal_steering`, `vertical_steering`) or the
  catalogue `plane`; a steering element saying neither is listed with `plane_known: false`, never guessed
  from its name.
* **Observables are per workspace** (the type is shared; records are not), as Product Models are.
* **Optics are queried per dataset**; there is no interpolation between elements.
* **The viewer draws the horizontal plane**: no vertical survey, no element tilt. A dedicated application
  builds on `/graph` and `/context`.
* **Converters read lattice files, not programs**: MAD-X macros, loops and conditionals are not executed
  (they are reported); Elegant's SDDS outputs (twiss) are left to the Toolbox.
* **The editor writes canonical values only**: simulator-specific types and parameters come with an uploaded
  file, and are kept through edits.
* **Not editable there:** state-to-signal mappings, the meaning of each state (beam passes, intercepts…) and
  value provenance. They are kept, and come from the Toolbox or a file.
* **Not modelled here, on purpose**: vacuum pumping, electrical distribution, cooling, PLC logic, networks,
  maintenance, documents and inventory. The beam model identifies a component and its relevance to the beam;
  the Knowledge Hub holds the engineering detail, linked by the binding.
