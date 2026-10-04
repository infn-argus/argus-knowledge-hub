# Beamline asset synchronization

Which physical assets in the facility correspond to a beam model's components, how certain each mapping is,
and which need a person. The beam model (`argus.beam-model/2`, [beam-model-format.md](beam-model-format.md))
says what is along the beam; the Knowledge Hub knows the installed units. Synchronization proposes the links
between the two and records what people decide. It never merges them into one object.

```
BeamlineComponent ──implemented_by──▶ PhysicalAsset           (normal)
                  ──mounted_on / contained_in / measured_by / associated_with──▶ PhysicalAsset
```

* Code: the pure matcher `backend/app/beam_model_core/matching.py` (runs in the Toolbox too), and the hub
  service `backend/app/services/beam_asset_sync.py`.
* Tests: `tests/test_beam_model_core.py` (the matcher, against mock assets) and
  `tests/test_beam_asset_sync.py` (the hub, end to end).

## 1. Workflow

```
Load beam model ─▶ canonical model created ─▶ visualise ─▶ [Sync beamline assets]
   ─▶ query the hub's physical assets ─▶ candidate mappings ─▶ review ambiguous ─▶ create / update bindings
   ─▶ physics and physical information together (element panel, controls, documents, history)
```

* **Automatic run after import:** set `ARGUS_BEAM_ASSET_SYNC_AUTO`.
  * `propose` keeps proposals for review.
  * `accept_high_confidence` also confirms auto-acceptable ones, as `authority: auto_accepted`.
  * The default is `off`.
* **Explicit run:** the *assets* link next to a model on the Beam model page, or the API (§ 6).

## 2. What is matched

* **Components:** every component whose family is physical (magnets, RF, diagnostics, injection and
  extraction, interception, vacuum, material, optics, sources and destinations, mechanical).
  * Virtual components expect no asset and are never reported as unmatched: markers, reference and
    observation points, interaction points, drifts, thin lenses.
* **Candidates:** the workspace's records on the catalogue's physical plane, everything under `Asset`.
  * Electronics, supplies, controllers, crates, PLCs, cables and computers are never a component's *primary*
    asset. A BPM is implemented by its pickup; the Knowledge Hub then connects the pickup to its electronics
    and signals.
* **What the matcher reads from an asset:**
  * name;
  * `aliases`;
  * attributes `lattice_name`, `model_name`, `tag`, `label`;
  * `control_name` / `pv_prefix`;
  * `component_type` (or `element_kind`, `device_kind`, `magnet_kind`);
  * `family`;
  * `beamline`, `section` and the names of what it is `located in` / `part of`;
  * `s` (or `s_position`), `sequence`;
  * `x`, `y`, `z`.

  None is required.

## 3. The matching algorithm (`beamline_asset_matcher` 1.0)

For every expected component, every candidate asset is scored. Each piece of evidence has a weight in [0, 1].
They are combined as `1 − Π(1 − w)`, so independent evidence adds up but never exceeds 1. Penalties then
multiply.

| Evidence | When | Weight |
|---|---|---|
| `exact_name` | the asset's name (or lattice/model name, or an alias) equals the component's id or name | 0.85 |
| `exact_alias_match` | a component alias equals an asset name or alias | 0.80 |
| `naming_convention` | a configured rule maps the component's name to the asset's (§ 3.1) | 0.75 |
| `control_name_match` | the asset's control name / PV prefix contains the component's name | 0.45 |
| `normalized_name` | equal once case, separators and leading zeros are ignored (`QUAA101` = `quaa-0101`) | 0.45 |
| `type_match` | the asset's type can implement the component's type (× compatibility, § 3.2); full when the asset says `component_type` | ≤ 0.25 |
| `number_match` | same trailing number, compatible type | 0.10 |
| `family_match` | the asset's `family` equals the component's model family | 0.10 |
| `beamline_match` | the asset's beamline, section or location names this model's system, path or model | 0.15 |
| `position_match` | \|Δs\| ≤ tolerance (0.2 m), comparing entry and centre | 0.45 × (1 − Δs/tol) |
| `geometry_match` | 3-D distance ≤ tolerance (0.3 m) | 0.45 × (1 − d/tol) |
| `order_match` | same rank along the model's main path, among components and assets of its family (assets ordered by `sequence` or `s`) | 0.20 |
| `neighbour_consistent` | an upstream or downstream neighbour is bound to the asset next to this one | 0.25 |

| Penalty | When |
|---|---|
| `type_incompatible` | confidence capped at 0.2 (downstream hardware, or a type that cannot implement this component) |
| `other_beamline` | × 0.5 — the asset declares another beamline of the facility (`DAFNE Main Ring` for an accumulator component); the facility alone does not count as this beamline |
| `position_mismatch`, `geometry_mismatch` | × 0.5 — more than 5 tolerances away |
| no anchor | capped at 0.45, below the propose threshold, when there is no name, position, order or neighbour evidence: a kind and a beamline alone never propose |

So `QUAA101` against `MAG-ACC-QF01`:
* alias `QUAA101` on the asset: 0.85;
* `Magnet Assembly`: 0.25;
* beamline: 0.15;
* number: 0.10;
* Δs 0 mm: 0.45.

That gives 0.95, auto-acceptable. `QUAA103` against `ACC-QF-03` (no shared name) has type, beamline and
Δs 4 mm: 0.64, proposed for review.

### 3.1 Naming conventions

Rules that travel with the model (`provenance.asset_sync.naming_rules`) or are given in a request:

```json
{"component": "^QUAA1(?P<n>\\d{2})$", "asset": "MAG-ACC-QF{n:02d}"}
```

### 3.2 Type compatibility

By family, with overrides by type, in `matching.FAMILY_ASSET_TYPES` / `TYPE_ASSET_TYPES`, configurable:

| Family / type | Asset types (compatibility) |
|---|---|
| magnet | Magnet Assembly (1.0) |
| diagnostic | Instrument (1.0), Scintillator Screen (0.9), Camera, Optical Assembly, Radiation Monitor (0.6) |
| screen / camera / beam_loss_monitor | Scintillator Screen / Camera / Radiation Monitor (1.0) |
| vacuum | Vacuum Component, Vacuum Chamber (0.8), Vacuum Valve (0.5); `gate_valve`, `fast_valve` → Vacuum Valve (1.0); `vacuum_chamber`, `beam_pipe` → Vacuum Chamber (1.0); `bellows` → Vacuum Component (1.0) |
| optical | Optical Assembly (1.0); `laser_source` → Laser System (1.0) |
| mechanical | Mechanical Support (1.0), Motor Axis (0.6), Actuator (0.5); `mover`, stages → Motor Axis (1.0) |
| rf, interception, material, sources | the closest types, with Other Equipment (0.5–0.7) |
| any | Other Equipment (0.5), Instrument (0.4), Asset (0.3) |

### 3.3 Decisions

| Status | When |
|---|---|
| **CONFIRMED** | a confirmed binding exists. Kept, never replaced; differences are reported (§ 4) |
| **PROPOSED** | best candidate ≥ 0.5 and ahead of the next by ≥ 0.1 |
| **AMBIGUOUS** | two or more candidates within 0.1 of each other, or one asset best for two components (the clearly better keeps it) |
| **UNMATCHED** | nothing ≥ 0.5; weak suggestions are still listed as candidates |
| **REJECTED** | a person rejected the pair; it is never proposed again |

`auto_acceptable` is a proposal that is all three of:
* ≥ 0.9;
* backed by identity evidence (exact name, alias, naming convention or control name);
* of a compatible type.

**Low confidence never becomes authoritative:** nothing is confirmed unless a person accepts it, or the
configured auto policy accepts an auto-acceptable proposal (and says so).

Asymmetry is normal:
* one component, several assets: the BPM's pickup is primary, the electronics are the hub's `connected to`;
* several components, one assembly: a `contained_in` binding, or one component `implemented_by`;
* assets with no component: listed as *unmodelled assets*;
* components with no asset: virtual, or simply unmatched.

## 4. Incremental synchronization

A sync compares with what is already known: the sync's own records, and confirmed Installations made any
other way (counted as human-confirmed). Nothing authoritative changes; each entry says how it differs (`diff`):

| Diff | Meaning |
|---|---|
| `unchanged` | as before |
| `new_match` | a proposal that did not exist before |
| `changed_candidate` | the best candidate is not the one proposed last time |
| `candidate_lost` | a previous proposal no longer has a candidate |
| `missing_asset` | the bound asset is gone or retired (a replaced unit); the replacement is listed as a candidate |
| `changed` | the bound asset was renamed or moved in `s` |
| `conflict` | another asset now matches clearly better than the bound one, which matches poorly |
| `stale_binding` | the model no longer has the component (listed separately) |

Replacing a unit is an Installation swap: the old one ends, the new one starts, and the position keeps its
identity and history.

## 5. Bindings: confidence and provenance

Each binding (`beam_asset_bindings`, and `external_bindings` in an export) carries:

```yaml
model_component: dafne/accumulator/QUAA101      # component_id in model dafne-accumulator-v2
relation: implemented_by
asset: kh://asset/92ac…                         # target {namespace: kh, id, name}
status: confirmed
authority: human_confirmed                      # authoritative | human_confirmed | auto_accepted | suggestion
confidence: 0.95
evidence: [exact_name, type_match, beamline_match, number_match, position_match]
source: {method: asset_sync, matcher: beamline_asset_matcher, matcher_version: "1.0"}
confirmed_by: {type: user, id: alice@lnf.infn.it}
timestamp: 2026-10-04T09:12:00Z
snapshot: {name: MAG-ACC-QF01, type: Magnet Assembly, s: 1.5833}   # to detect renames and moves
installation_uid: …                                                 # implemented_by: the Installation made
note: accepted with the high-confidence batch
```

* **`authority`** distinguishes:
  * `authoritative`: from an authoritative source;
  * `human_confirmed`: a person accepted it, alone or in a high-confidence batch;
  * `auto_accepted`: by policy, without a person;
  * `suggestion`: a proposal.
* **Method:** `method: manual` when a person bound an asset the matcher had not proposed.
* **Superseded:** a binding replaced by a newer confirmed one becomes `superseded`, with a note.

## 6. API

All under the usual workspace header.

| Endpoint | Permission | What |
|---|---|---|
| `POST /v1/beam-models/{id}/asset-sync/preview` | read | proposals, candidates, evidence, diff, unmodelled assets, stale bindings, summary. **Writes nothing.** Body: optional `dataset`, thresholds, tolerances, `naming_rules` |
| `POST /v1/beam-models/{id}/asset-sync/apply` | approve | `accept` (`[{component, asset, relation?}]`), `reject`, `accept_high_confidence`, `keep_proposals` (store proposed/ambiguous for the next diff). Returns what was confirmed, rejected, kept, and problems |
| `GET /v1/beam-models/{id}/asset-sync/status?filter=` | read | the summary, counts per family group, and the entries filtered by `magnets`, `diagnostics`, `vacuum`, `rf`, `optics`, `mechanical`, `interception`, `sources` or a status (`confirmed`, `proposed`, `ambiguous`, `unmatched`) |
| `GET /v1/beam-models/{id}/asset-bindings?status=` | read | every recorded binding with status, authority, confidence, evidence, matcher, decision |

Accepting an `implemented_by` binding creates a confirmed Installation (a swap when another unit is
installed). The position's equipment, power, controls, documentation and tickets
(`GET /v1/beam-elements/{uid}/context`) then come from the unit. The other relations become ledger relations
from the component to the asset. A component the model already mounts on a support (`mounted_on` GIRDER_01)
is not bound `mounted_on` an asset: the girder is what binds to the physical support.

## 7. The synchronization view

**Beam model → *assets*** (`/beam-model/{model}/assets`):

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Beamline asset synchronization                       [Accept high confidence (11)]       │
│ Model components 35 · Candidates 25 · Confirmed 2 · Proposed 16 · Ambiguous 1 ·          │
│ Unmatched 16 · Rejected 0                 [Apply selected] [Reject selected] [Sync again]│
│ all · magnets 21 · diagnostics 6 · vacuum 4 · mechanical 3 | unmatched ambiguous …       │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ Model     Candidate asset      Confidence  Status     Since last sync  Evidence          │
│ QUAA101   MAG-ACC-QF01 ▾       95%         proposed   new match        exact name · …    │
│ CHHA101   COR-H-01             —           confirmed  unchanged                          │
│ KCKA101   KCK-OLD              —           confirmed  missing asset    (KCK-NEW 91%)     │
│ QUAA103   ACC-QF-03 ▾          64%         proposed   new match        type · Δs 4 mm    │
│ BPSA103   choose… ▾            ambiguous   ambiguous  new match                          │
│ SEPA101   —                    —           unmatched                                     │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ Physical assets with no model component: ION-PUMP-07 …   Stale bindings: none            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Choosing:** pick a candidate in a row to select it (an ambiguous row's candidates are in the list).
  *Apply selected* confirms the selected rows; *Reject selected* rejects them.
* **Element panel:** the Beam model page's panel shows, under *Physical asset*, the bound unit with its
  binding status and authority. Then Power, Control (devices, IOCs, signals, connected electronics),
  Documentation and Tickets come from the Knowledge Hub.

## 8. Tests

`tests/test_beam_model_core.py` (the matcher):
* exact name;
* alias;
* naming convention;
* normalised name;
* different model and asset names (type + beamline + position, never auto);
* geometry alone;
* another beamline's asset with the same name;
* multiple candidates (ambiguous);
* no candidate;
* an existing confirmed relation, kept;
* an asset replaced while the position stays;
* a physics element without asset;
* a physical asset without element;
* a diagnostic with one primary asset and downstream electronics;
* low confidence never authoritative, and auto needing identity evidence;
* rejected pairs not proposed again;
* confirmed bindings surviving a rename;
* incremental diffs (new, changed candidate, stale);
* summary and filters.

`tests/test_beam_asset_sync.py` (the hub):
* preview writes nothing;
* accepting high-confidence creates Installations, and the rest is kept for review;
* confirmed bindings survive and rejections stick;
* a replaced unit is a swap with the position's identity unchanged;
* the BPM reaches its electronics through the hub;
* `mounted_on` versus the model's own supports;
* auto-acceptance only when configured;
* the API;
* the v2 export carrying bindings with provenance and no copy of asset data.

## 9. Limits and boundaries

* **Positions:** the matcher reads asset positions from attributes. An asset with no `s`, coordinates,
  `sequence`, name or alias in common with the model can only be bound by a person.
* **Order evidence:** `order_match` ranks along the model's main path only, because asset positions are
  along one line. Other paths rely on names and positions.
* **Thresholds:** the weights and thresholds are configuration, not learned. They are versioned with the
  matcher (`matcher_version`) so a binding says which rules made it.
* **Engineering topology:** synchronization does not create or edit vacuum, power, control or cooling
  topology. Those relations stay the Knowledge Hub's; the binding is the bridge.
