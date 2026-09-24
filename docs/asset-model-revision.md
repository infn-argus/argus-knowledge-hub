# ARGUS asset model: revision

*A review of `asset-schema-design.md` and `it-model-design.md`, checked against the code that
implements them, and a revised model that keeps their architecture and makes it operable:
positions and installations, fact-level provenance, a governed relation registry, identity
reconciliation, non-destructive retirement and a staged catalogue.*

Status: **proposal, second revision**. Where this document and the two design notes disagree,
this one states the intended model. It refers to them by section (`AS §n` =
`asset-schema-design.md`, `IT §n` = `it-model-design.md`).

---

## 0. Summary

### 0.1 The model in one paragraph

A **Position** is a stable place in the machine's function: `GUNSIP01`, a quadrupole slot, the
electronics slot that serves two BPMs. **Equipment** is a physical unit with a serial number. An
**Installation** records that one unit occupied one position over a half-open time interval, and
a unit occupies at most one place at a time. Functional topology (`powers`, `served by`,
`composed of`, `acts on`) runs between positions, so it survives swaps. Every attribute value and
every asserted edge is a **projection** of an append-only **ledger**. The ledger holds three
kinds of record: immutable source **claims**, **claim events** that record when a stream starts
or stops stating a claim, and human or policy **decisions**. A **pipeline** of independently
versioned stages turns sources into current state: parse, infer, resolve, project, derive and
reconcile. **Authority policies** and **multi-value policies** decide how several sources
combine. The **relation registry** governs every edge. Legacy data is **classified** before it
is converted. Each object gets a dry-run decision report, and the migration is reversible and
resumable.

### 0.2 What changed since the first revision

| # | Change | Section |
|---|---|---|
| 1 | Installation is strictly physical: one unit is in one place at a time. The `multi_position` exception is removed; shared equipment serves several positions through functional relations | §5.4, §8 |
| 2 | The ledger now separates immutable **claims**, append-only **claim events**, **decisions** and **status events**, and keeps projections apart from all of them. An unchanged revision writes no claims | §7.1–§7.3 |
| 3 | Parsing idempotency is separate from resolution. Six stages each have their own version, inputs and rerun rule | §7.6 |
| 4 | A confirmed fact changes only through explicit supersession or retraction. Competing confirmations open a blocking conflict | §7.4 |
| 5 | Authority is selected by predicate × object type × owning workspace × facility/domain × source instance, with specificity, fallback and load-time validation | §7.7 |
| 6 | Every multi-value fact declares a mode: replace set, members, delta or ordered list | §7.8 |
| 7 | Legacy migration classifies each object into one of six outcomes, with a decision report per object | §12 |
| 8 | An Access Point is `assigned to` a position; `implemented by` is derived through the current Installation, which preserves endpoint history | §9.2 |
| 9 | Installation carries only a workflow status. Planned, Future, Current and Ended are derived from the interval | §8.2 |
| 10 | Installation keys are opaque. The display name is a projection, and source identifiers are kept as aliases | §8.1 |
| 11 | Migration safety: plans, per-item pre-images, rollback, resumption, invariant checks and a permanent traceability map | §12.3–§12.6 |
| 12 | `Other Equipment` gets a governed `equipment_class`, periodic reports and promotion thresholds | §5.5 |
| 13 | The implementation plan starts with one end-to-end vertical slice and its acceptance tests | §13, §14 |

**Renames and scope changes.** The work-package relation is renamed `in work package`, which
frees `assigned to` for the Access Point relation. Positions and Installations may now be owned
by `it-infrastructure` as well as by beamlines.

---

## 1. Architectural assessment

### 1.1 What is right and is kept

- **Planes kept apart.** Functional, physical, catalogue, control, location and engineering
  remain separate.
- **Existing strengths.** Configuration as objects (AS §9), Access Points in the control plane
  (IT §4), site-owned IT equipment (IT §5) and composite functional elements (AS §4).
- **Secret filtering** (AS §9.4) and **honest reporting** of odd source data.
- **Stated, resolved, inferred, manually confirmed.** These are now the `method` of a claim,
  combined with the decisions made about it (§7.3).
- **Causal semantics** (`causal_model.py`) move into the relation registry.

### 1.2 Structural problems (the target of this design)

1. **Identity from control addressing.** Physical identity is derived from IOC and channel
   names (`SPARC:AST:vac-gunvpc:GUNSIP01`).
2. **No time at the plane joints.** `realized by` has no interval, and three partial history
   mechanisms compete.
3. **Thin provenance.** It is one last-writer-wins attribute plus a keyword.
4. **Ungoverned relations.** The same verb takes different domains, and nothing checks
   cardinality.
5. **Two representations of one link**, for example `product_model` and `instance of`.
6. **No retirement.** The only alternative to keeping stale records is a cascading hard delete.
7. **Implicit ownership**, including a cross-workspace write path that nothing checks.
8. **Types without support.** 122 types exist, and fewer than half have a source, an owner and
   a query.

### 1.3 Contradictions in the existing notes and code

| # | Contradiction | Where |
|---|---|---|
| C1 | `Spare Part` inherits PBS/WBS keys that it must not have | AS §4 vs §5.1 |
| C2 | `composed of` is Functional → Asset in one place, but Asset → Asset and element → element elsewhere | AS §4, §6, §9.5 |
| C3 | `part of` is used for locations (`zones:` → Area, PBS AREA → Area) | AS §9.1, §10.2; `pbs_import.py:494` |
| C4 | A modulator shared by several stations is modelled as a component of one of them | AS §4 vs §11.5 |
| C5 | Swap history is held in three places, none of them complete | AS §5.3, §6, §11.1 |
| C6 | The design says the power supply `powers` a Magnet Assembly; the code has it `powers` the Quadrupole, and never creates a Magnet Assembly | AS §11.1 vs `element_inference.py:355` |
| C7 | "Imports do not create IT equipment", yet the import does | IT §3 vs §0 |
| C8 | "The Access Point is always made", yet `access_point()` reuses matched equipment instead | IT §6 vs `epik8s_import.py` |
| C9 | `upsert()` replaces the whole attribute bag of stated objects on every re-import | `epik8s_import.py` `upsert` |
| C10 | `argus_source_ref` records a branch, not a revision | AS §5.1 |
| C11 | "Nothing is deleted", yet `remove_all_before` deletes with a cascade | AS §5.3 vs `run_epik8s_import` |
| C12 | Spares are represented in four different ways | AS §5.3, §6 |
| C13 | A single `asset:` URL on a multi-device IOC cannot name one box per device | AS §9.2 |
| C14 | 156 planned PBS components are stored as serialised assets | AS §10, §14.10 |
| C15 | Published counts disagree: 141 vs 104 serial lines, 17 vs 8 abstract types, 76/46 vs 59/44 types, 45 vs 27 tests | IT §0–§1; AS §4, §8, §14–§16 |

### 1.4 Where the platform forces an intermediate object

A `Relation` row carries only `from`, `to` and `type`. A link that has information of its own
therefore becomes an object:

- **Installation**: interval and workflow status.
- **Communication Path**: protocol and transport.
- **Bus Segment**: medium and line parameters.
- **Equipment Port**: port number and mode.

System metadata (provenance, derivation, edge status) goes into platform tables and columns,
not objects (§3.3). Ordered hops and permit thresholds remain deferred (§9.1, AS §9.3).

---

## 2. Principles and terminology

### 2.1 Principles

1. **Positions vs equipment.** Functional topology connects positions. A physical unit attaches
   to a position only through an Installation.
2. **Installation is physical occupancy.** A unit is in at most one place at any instant. A unit
   that serves several functions does so through functional relations from its one position.
3. **Configuration names positions, not boxes.** An LNF device name is a functional tag.
4. **Claims are immutable; state is projected.** A source's statement is never edited. The
   current value of every attribute and asserted edge is recomputed from claims, decisions and
   policy.
5. **Confirmation is sticky.** A confirmed fact stays until a person explicitly supersedes or
   retracts it. Sources and other confirmations can only raise conflicts against it.
6. **Stages are versioned independently.** Unchanged bytes skip parsing. They never skip
   resolution or projection when those stages' inputs have changed.
7. **Authority is policy, not code.** Which source wins is declared, versioned and validated
   data.
8. **One authoritative form per link.** A link is held as an attribute, an asserted edge or an
   intermediate object. Every other form of it is derived.
9. **Owners create; others propose.** Records are retired, never deleted. Duplicates are merged
   into tombstones, never dropped.
10. **Classify before converting.** Legacy data is sorted by evidence into explicit outcomes,
    with a reviewable report, before anything moves.
11. **Types follow sources and questions.** Fallback categories are governed and promoted when
    they cross a threshold.

### 2.2 Terms

| Term | Meaning |
|---|---|
| **Position** | a Functional Element of an *installable* type (registry `installable = true`): Equipment Position, Motion Axis, Mirror, and the Beam Element subtypes. Facilities, Sections and pure composites (Machine Module, RF Station, Screen Station) are not positions |
| **Equipment** | a physical, individually tracked unit: any subtype of `Equipment`, including IT Equipment |
| **Installation** | a domain record placing one Equipment at one Position over `[valid_from, valid_until)` |
| **Source stream** | one source instance read repeatedly, for example `epik8s:epik8-sparc#deploy/values.yaml@main`, `insight:schema=44` or `person:<user>` |
| **Source ref** | the name a source gives a subject, for example `epik8s:SPARC:device:vac-gunvpc/GUNSIP01` or `insight:object:129573`. Resolution binds it to a record uid |
| **Fact** | what is being claimed: `(subject, predicate)` for a single value, `(subject, predicate, member)` for a set member |
| **Claim** | one source stream's statement of one fact value, with its method and rule. Immutable |
| **Claim event** | a record that a claim *appeared in*, *disappeared from* or *changed evidence in* a stream revision. Append-only |
| **Decision** | a judgement by a person or by a declared policy about a fact, claim, identity, conflict or revision. Append-only |
| **Status event** | a change in a fact's projected status, with its cause. Append-only |
| **Projection** | current state computed from the above: fact state, `assets.attributes`, asserted edges, record status, identity bindings, conflicts, the review queue. Mutable and rebuildable |
| **Derived edge** | a `relations` row computed by a registry rule from projections, for example `realized by`, `implemented by` or `instance of`. It is never claimed or edited |
| **Record status** | the record's own state: `Provisional`, `Active`, `Retired` or `Merged`. It is separate from `argus_lifecycle`, which describes the equipment's operational state |

---

## 3. Metamodel

### 3.1 Domain records and how they connect

```
 FUNCTIONAL (beamline or it-infrastructure)                       CATALOGUE (catalogue ws)
 Facility ◄─part of─ Section ◄─part of─ Beam Position Monitor A ─┐       Product Model ─supplied by▶ Vendor
                                        Beam Position Monitor B ─┤ served by        ▲ instance of [derived]
                                                                 ▼                  │
 Control Device ─acts on─▶ Equipment Position SPARC:POS:LIBERA-01 (class Digitizer) │
      │                          ▲ installed at                                     │
      │ on path                  │                  PHYSICAL (inventory / it-infrastructure)
      ▼                     Installation INS-01J9… ─installation of─▶ Digitizer s/n 2217
 Communication Path          [2024-05-02, open) · Confirmed          │ located in [derived]
      │ enters at                                                    ▼
      ▼                                                         Rack B12 ─within▶ Area ─within▶ Building
 Access Point ─assigned to─▶ Equipment Position IT:POS:scsparcsipmxa001 (it-infrastructure)
      │   ╲                        ▲ installed at
      │    ╲ implemented by        │
      │     ╲ [derived]       Installation ─installation of─▶ Serial Converter Moxa s/n M-5531
      │      ╲──────────────────────────────────────────────────▶      ▲ port of
      │                                                                 │
 Communication Path ─continues on─▶ Bus Segment ─attached to [derived]─▶ Equipment Port P3

 [derived] = computed by the derive stage from projections; never claimed or edited
```

### 3.2 Four classes of stored data

| Class | Mutability | What it holds | Stored in |
|---|---|---|---|
| **Domain record** | identity (`uid`) is stable; type, key and record status change only through record events | Position, Equipment, Installation, Access Point, Communication Path… | `assets` row (uid, key, type, workspace, record_status) |
| **Immutable audit data** | append-only; never updated or deleted | source revisions, claims, claim events, decisions, status events, record events, identity events, conflict events, migration events, job runs | ledger tables (§7) |
| **Current-state projection** | rewritten by the project stage; rebuildable from audit data at any time | fact state, `assets.attributes`, `assets.record_status`, asserted `relations` rows, identity bindings, open conflicts, the review queue | projection tables and the existing columns |
| **Derived graph edge** | rewritten by the derive stage from projections and the registry | `realized by`, `implemented by` (derived form), `attached to`, `reached through`, `connects to`, `drives`, `instance of`, `located in`, `within`, `supplied by`, `in work package` | `relations` rows with `derivation = derived` |

After the cut-over, nothing writes `assets.attributes` or `relations` directly: not the
importers, the UI or the API. A UI edit becomes a claim from the stream `person:<user>` plus a
`confirm` decision by the same person, which the project stage then applies.

### 3.3 Platform additions

| Addition | Class |
|---|---|
| `source_revision`, `claim`, `claim_event`, `decision`, `status_event`, `record_event`, `identity_event`, `conflict_event`, `migration_event`, `job_run` | audit data. Append-only is enforced by database grants: the application role has only `INSERT` and `SELECT` |
| `fact_state`, `identity_binding`, `conflict`, `review_item`, `v_installation` | projections |
| `authority_rule`, `multivalue_rule`, `relation_type` (each keyed by policy or registry version) | versioned configuration, seeded from reviewed files in the repository |
| `assets.record_status`, `assets.merged_into_uid` | projection columns |
| `relations.derivation` (`asserted` / `derived`), `.status` (`active` / `proposed` / `retired`), `.retired_at`, `.rule`; unique `(workspace_id, from, to, type)` | projection columns and a constraint |
| partial unique index on active strong identifiers in `asset_labels` | constraint |
| `migration_plan`, `migration_item`, `migration_map` | migration (§12) |

---

## 4. Ownership and authority

### 4.1 Workspaces

| Workspace | Owns | Authoritative sources |
|---|---|---|
| `catalogue` | shared types; Product Model, Vendor; the `equipment_class` vocabulary | catalogue editors, vendor data |
| `inventory` | non-IT Equipment, Location | Jira Insight asset schemas; inventory staff |
| `it-infrastructure` | IT Equipment and its Equipment Ports; Address Records; **IT positions** (the rack slot or role a converter or server fills) and **their Installations** | IT registry, DNS/DHCP; IT staff |
| beamline | functional elements and positions; control items (including Communication Paths, Bus Segments and Access Points); **their Installations**; engineering records | its configuration repository, PBS matrix and operators |

**An Installation belongs to the workspace that owns its position.** A beamline records the
swaps on its machine, and IT records the swaps behind its hostnames. Positions and Installations
are readable from every workspace (decision D6), so the inventory team can see where its units
are. The owner of a piece of equipment can **propose** decisions about any Installation of it
(§4.3).

### 4.2 What each source may create

| Source | Creates in its own workspace | Proposes | Never creates |
|---|---|---|---|
| EPIK8s configuration | control items, Access Points, Communication Paths, Bus Segments; the positions it infers (`Provisional` until a policy or a person accepts them) | Installations from `asset:` evidence; edges from naming rules; Access Point assignments | Equipment, Locations, Product Models |
| PBS matrix | functional elements and positions (lifecycle Planned); modules, stations, sections; engineering records | Areas | Equipment |
| Inventory (Insight) | Equipment, Locations | Product Models; Installations where Insight records a slot | positions |
| IT registry | IT Equipment, Equipment Ports, Address Records, IT positions and their Installations | — | Access Points |
| Person | anything their workspace owns | decisions on records in other workspaces | — |

Provisional IT Equipment may be created only when all four conditions from the first revision
hold:

1. the run uses a service identity with the `it-contributor` role;
2. the domain is IT-approved and its registry export is fresh;
3. resolution finds no identifier candidate;
4. the DNS class prefix names equipment.

### 4.3 Read, edit, link, propose

| Permission | Rule |
|---|---|
| Read | the owner workspace; or anyone, if the record is flagged global |
| Edit | editors in the owner workspace. Their edits are recorded as claims plus `confirm` decisions |
| Link | an asserted edge *from* a record you own *to* any record you can read, if the registry allows that relation to cross workspaces |
| Propose | a claim or a `propose` decision on any readable record. It lands in the owner's review queue, and only the owner can confirm it |

Two platform gaps must be closed: `create_asset` must check that the type is usable from the
workspace, and the unchecked `--it-workspace` script path is removed.

---

## 5. Type hierarchy for the first production release

### 5.1 The core: 54 concrete, 12 abstract

```
Item (abstract)
├── Functional Element (abstract)        breakdown keys (pbs_*, design_status, work_package), argus_location
│   ├── Facility · Section · Machine Module · RF Station · Screen Station        (not installable)
│   ├── Mirror                            composite of its axes; installable (the optic itself)
│   ├── Beam Element (abstract)           installable
│   │   ├── Dipole · Quadrupole · Sextupole · Corrector · Solenoid
│   │   ├── Accelerating Structure · RF Gun · Beam Position Monitor
│   ├── Motion Axis                       installable
│   └── Equipment Position                installable; position_class, expected_product_model
├── Physical Asset (abstract)            argus_location
│   ├── Equipment (abstract)             manufacturer, model, serial, product_model, inventory_number,
│   │   │                                condition, warranty_until, is_designated_spare
│   │   ├── Power Supply · Magnet Assembly · Ion Pump · NEG Cartridge · Turbo Pump · Primary Pump
│   │   ├── Vacuum Gauge · Camera · Actuator · Digitizer · Low-Level RF Unit · Modulator · Chiller
│   │   ├── Other Equipment               equipment_class (governed, §5.5)
│   │   └── IT Equipment (abstract) → Serial Converter · Switch · Server
│   └── Equipment Port
├── Catalog Item (abstract) → Product Model · Vendor
├── Control Item (abstract) → Control Configuration · IOC Template · IOC · Control Device · Control Service
│                             · Control Network · Storage Mount · Access Point · Communication Path · Bus Segment
├── IT Record (abstract) → Address Record
├── Record (abstract) → Installation · Engineering Record (abstract) → Work Package · Procurement Record
│                                                                      · Utility Requirement
└── Location (abstract) → Building · Area · Rack
```

This revision adds no types. `Engineered Item` stays removed, and its breakdown keys live on
Functional Element. That fixes C1 and C14: a planned PBS component is a position, and a spare
unit is Equipment with no current Installation. The extensions keep the triggers set in the
first revision: RF distribution, diagnostics, magnets and undulators, cabling, network
topology, consoles, stores, safety, plant and electronics, and engineering. Each one enters
when it has a source, an owner and a query.

### 5.2 Installation attributes

§8.1 replaces the first revision's list. Installation has no `role` field and no temporal
status field.

### 5.3 Equipment Position

`position_class` uses the same governed vocabulary as `equipment_class` (§5.5), so the
compatibility check in §8.3 compares like with like. `expected_product_model` records design
intent, taken from an IOC template's `asset:` or from the PBS. If it differs from the installed
unit's `product_model`, that is a report item, not an error.

### 5.4 Equipment that serves several positions

A unit with several channels is installed once, at one position. The positions it serves point
to that position:

```
Digitizer (Libera Spectra, s/n 2217) ─installation─▶ Equipment Position SPARC:POS:LIBERA-01
Beam Position Monitor BPM-A ─served by─▶ SPARC:POS:LIBERA-01        (read: LIBERA-01 serves BPM-A)
Beam Position Monitor BPM-B ─served by─▶ SPARC:POS:LIBERA-01

Power Supply (4 channels) ─installation─▶ Equipment Position SPARC:POS:PS-RACK3-01
SPARC:POS:PS-RACK3-01 ─powers─▶ Corrector HCOR01, Corrector VCOR01, …
```

Per-channel facts, such as the channel number or a current limit, stay on the Control Devices
that address them, where the configuration states them. The derived chain
`BPM-A → served by → LIBERA-01 → realized by → s/n 2217` answers "which unit is behind this BPM".
The unit itself has exactly one Installation.

### 5.5 Governing `Other Equipment`

- **The vocabulary.** `equipment_class` is an enumeration owned by `catalogue`. It starts with
  the classes the sources already name (I/O Module, Scope, Timing Module, PLC, Motion
  Controller, Laser System, Cryogenic Device, Cable, Rack PDU, …) plus `Unclassified`. Adding a
  value is a catalogue decision.
- **Mapping.** Importers map source classes through a versioned mapping table. An unmapped
  source class becomes `Unclassified`, is reported, and its raw class is kept as a claim.
- **Monthly report**, also available on demand. It covers:
  - active objects per class, per workspace and per source;
  - the share of `Unclassified`;
  - classes whose objects appear in tickets or root-cause walks;
  - free-text attributes that people keep adding in `description`.
- **Promotion thresholds.** Any one of these opens a promotion review for a class:
  - at least 25 active objects;
  - objects in at least 2 workspaces;
  - at least 3 class-specific attributes requested;
  - a query or dashboard that filters on the class;
  - a causal role that the root-cause walk needs.

  Separately, `Unclassified` above 5 % of Equipment, or above 50 objects, raises a catalogue
  alert.
- **Promotion** creates a child type of `Equipment`. The class's objects are retyped in place,
  keeping their uids, and each retype writes a `record_event: retyped`. The old class value is
  deprecated: kept for history, no longer assignable (I-CAT-1).

---

## 6. Relation registry

### 6.1 Fields

The fields are unchanged from the first revision: `name`, `inverse_name`, `source_types`,
`target_types`, `card_source`, `card_target`, `acyclic`, `transitive`, `cross_workspace`,
`derivation` (`asserted` / `derived`), `derived_from`, `on_source_retire`, `on_target_retire`,
`on_merge`, `temporal`, `causal` and `mode` (`warn` / `enforce`).

This revision adds two:

- **`multivalue`**: the contribution mode for asserted n-valued relations (§7.8).
- **`installable`**: a flag on target types, used by `installed at`.

### 6.2 Registry entries

Entries changed or added in this revision are marked ●. Abbreviations: `FE` = Functional
Element, `Pos` = installable position, `Eq` = Equipment (including IT Equipment), `AP` = Access
Point. Cardinality is written `source / target`. For derived edges it applies **at any
instant**.

| name | inverse | source → target | card | derivation | multivalue | notes |
|---|---|---|---|---|---|---|
| ● **installed at** | has installation | Installation → Pos | 1 / n | asserted | — | immutable once the Installation is Confirmed |
| ● **installation of** | installed as | Installation → Eq | 1 / n | asserted | — | immutable once Confirmed |
| ● **realized by** | realizes | Pos → Eq | **1 / 1** at any instant | derived from the Current, Confirmed Installation | — | no multi-position exception |
| ● **served by** | **serves** | FE → Pos, FE | n / n | asserted | replace set per stream | shared providers (electronics, modulators); causal: function, reverse |
| **powers** | powered by | Pos → FE | n / n | asserted | replace set per stream | covers multi-channel supplies |
| **measures** | measured by | Beam Position Monitor, Screen Station → Beam Element, Section | n / n | asserted | members | |
| **part of** | contains | FE → Facility, Section | 1 / n, acyclic | asserted | — | never points to a Location; components inherit their composite's |
| **composed of** | component of | composite FE → FE | n / **1**, acyclic | asserted | replace set per stream | exclusive; shared providers use `served by` |
| **acts on** | acted on by | Control Device, device-less IOC → Pos, FE; Eq only if it has no position | n / n | asserted | replace set (config), members (review tool) | |
| **drives** | driven by | IOC → Eq | n / n | derived | — | via `provided by`, `acts on` and `realized by` |
| ● **assigned to** | has address | AP → Pos | 1 / n | asserted | — | the endpoint belongs to this place in the machine or in IT |
| ● **implemented by** | implements | AP → Eq | 1 / n at any instant | **derived** when the AP is assigned; otherwise **asserted** (resolver, transitional) | — | §9.2 |
| **provided by**, **declared in**, **templated from**, **deployed on**, **configures** | as before | control plane | as before | asserted | — | |
| **on network**, **mounts** | as before | IOC, AP / IOC, Service → … | n / n | asserted | replace set per stream | |
| **runs on** | runs | IOC → Pos, Server | 1 / n | asserted | — | an IOC on an instrument runs on that instrument's position |
| **uses path**, **on path**, **enters at**, **continues on** | as before | connectivity | as before | asserted | — | |
| ● **attached to** | attachment | Bus Segment → Equipment Port | 1 / 1 at any instant | **derived**: the segment's `port_number` on the unit currently implementing its path's AP | — | needs no re-pointing after a swap |
| **port of** | ports | Equipment Port → Eq | 1 / n | asserted (IT registry) | — | retired with the unit |
| **traverses** | traversed by | Path, Segment → Equipment Port, Switch | n / n, unordered | asserted | members | |
| **reached through**, **connects to** | as before | | | derived | — | |
| **enabled by**, **cools**, **triggers**, **timed by**, **upstream of** | as before | positions and control | as before | asserted | replace set per stream | |
| **instance of**, **located in**, **within**, **supplied by** | as before | | | derived from reference attributes | — | |
| ● **in work package** | work package of | FE → Work Package | 1 / n | derived from `work_package` | — | renamed from `assigned to` |
| **requires**, **procured under**, **described by** | as before | | | asserted | members | |

§12 migrates the deprecated verbs: `replaced`, `carried by`, `on line`, the Serial Line's
`port of`, `spare for`, and the old `assigned to` → Work Package. Once the registry is in
`enforce` mode, it rejects them.

---

## 7. The fact ledger

### 7.1 Schemas

**Audit tables** (append-only):

```
source_revision                  one row per stream revision read
  id, stream_id, revision (commit SHA | file SHA-256 | export timestamp), content_hash,
  observed_at, retrieved_at,
  ordering ('head' | 'historical'), state ('published' | 'held' | 'approved'), parse_job_id

claim                            immutable; content-addressed; one row per distinct statement
  claim_id = hash(stream_id, source_ref, predicate, polarity, canonical(value), method, rule_id)
  stream_id, source_ref, predicate,
  polarity ('present' | 'absent'),
  value           canonical JSON; relation targets are source refs
  method ('stated' | 'resolved' | 'inferred' | 'manual'), rule_id,
  derived_from    claim_ids an inference or resolution read; empty for stated and manual

claim_event                      written only when presence or evidence changes
  seq (global bigserial), claim_id, stream_id, source_revision_id,
  kind ('appeared' | 'disappeared' | 'evidence_changed'),
  rule_version, evidence (JSONB), confidence, at

decision                         judgements by people and by declared policies
  seq, decision_id, kind,
  actor ('user:<id>' | 'policy:<rule>@<version>' | 'migration:<plan>'),
  workspace_id, target (see §7.4), value, effective_at,
  supersedes (decision_ids), reason, at

status_event                     every change in a fact's projected status
  seq, fact_key, claim_id | decision_id, from_status, to_status,
  cause ('claim_event:<seq>' | 'decision:<seq>' | 'policy:<version>' |
         'registry:<version>' | 'identity:<seq>'),
  projector_version, at

record_event    seq, uid, kind ('created' | 'retyped' | 'rekeyed' | 'status' | 'merged' | 'unmerged'),
                before, after, cause, at
identity_event  seq, source_ref, uid, kind ('bound' | 'unbound' | 'rebound'), cause, resolver_version, at
conflict_event  seq, conflict_id, kind ('opened' | 'updated' | 'resolved' | 'dismissed'),
                conflict_type, fact_key, detail, cause, at
job_run         id, stage, stage_version, input_digest, input_watermarks, output_watermark,
                status, counts, started, finished
```

**Projection tables** (mutable, rebuildable):

```
fact_state        one row per contributing claim or decision:
                  fact_key, subject_uid, predicate, member, claim_id | decision_id,
                  status, rank, is_effective, since_seq
identity_binding  source_ref → uid, since_seq
conflict          conflict_id, type, fact_key, severity ('blocking' | 'non-blocking'), opened_seq, state
materialized      assets.attributes, asserted relations rows, assets.record_status
```

### 7.2 Why this is auditable without duplication

- **A claim is written once.** Its id is a hash of its content, so a value that a stream keeps
  stating is the same claim row in every revision.
- **An event is written only on change.** An unchanged revision writes one `source_revision`
  row and one `job_run` row. It writes **zero** claims and **zero** claim events.
- **What a stream said is recoverable.** What stream S said at revision R is the set of claims
  whose last event in S at or before R is `appeared`.
- **Evidence changes are cheap.** If only the evidence moves (for example, a YAML index shifts),
  the stream writes one `evidence_changed` event and no new claim.
- **History is never overwritten.** Every acceptance, rejection, confirmation, retraction and
  supersession is a `decision` or a `status_event`. Automatic ones are included: their actor or
  cause names the policy version.
- **Any past state can be replayed.** Replaying events up to a sequence number reproduces the
  state of any fact at that point. The test suite checks that a replay from zero equals the
  incremental projection (A16).
- **Older revisions do not rewind the present.** A revision older than the stream's head, by
  commit ancestry or `observed_at`, is stored with `ordering = historical`. It produces no
  presence events unless a person issues a `rewind` decision.

### 7.3 Fact statuses (projection)

Each claim or decision that contributes to a fact has one of these statuses:

| Status | Meaning | Entered by |
|---|---|---|
| `proposed` | shown in the review queue; not effective | a policy that requires confirmation |
| `accepted` | eligible to be effective; not signed by a person | a policy with `auto_accept`, or an `accept` decision |
| `confirmed` | signed by a person | a `confirm` decision on the fact value |
| `rejected` | never effective, and blocks re-proposal | a `reject` decision. Its scope is either the claim or its fingerprint (stream kind, rule, source ref, predicate, value) |
| `withdrawn` | the stream no longer states it | `claim_event: disappeared` |
| `superseded` | replaced by an explicit decision, or by a newer value from the same stream | a `supersede` decision, or a same-stream disappearance plus appearance |
| `outranked` | valid, but a higher-ranked value is effective | projection |

The four-way distinction from the design notes survives. Stated, resolved and inferred are the
claim's `method`. Manually confirmed means a `confirm` decision exists, whatever the method.

### 7.4 Decisions and the confirmation rules

| Kind | Target | Effect |
|---|---|---|
| `accept` / `reject` | a claim or a fingerprint | makes it eligible, or blocks it |
| `confirm` | a fact value (`subject, predicate[, member], value`) | makes it confirmed. `basis` may list the supporting claims |
| `supersede` | one or more earlier `confirm` decisions, plus a new value | ends the old confirmations and confirms the new value, in a single decision |
| `retract` | an earlier `confirm` decision | the fact is no longer confirmed, because it was wrong or has stopped being true |
| `revoke` | any earlier decision | undoes a decision made in error. Both decisions stay on record |
| `bind`, `merge`, `unmerge`, `confirm_new`, `reject_candidate` | identities (§10) | |
| `approve_revision`, `rewind` | a held or historical source revision (§11) | |
| `resolve_conflict` | a conflict | must carry, or reference, the supersede, retract or reject decisions that remove the conflict's cause |

Several decisions can be submitted as one **atomic batch**, for example ending one Installation
and starting another. The batch's invariants are checked once, after all of its decisions apply.

Invariants:

- **I-LED-1.** A `confirm` stays effective until a later `supersede`, `retract` or `revoke`
  names it. Nothing else ends it: not a source withdrawal, not a newer source value, not a
  policy change.
- **I-LED-2.** Suppose a single-valued fact already has an effective confirmation, and a new
  `confirm` of a different value does not name it in `supersedes`. The new decision **does not
  replace** the old one. It opens a **blocking conflict** (`confirmed_vs_confirmed`), and the
  earlier confirmed value remains the projected value until the conflict is resolved.
- **I-LED-3.** A source that stops stating a confirmed fact, or contradicts it, opens a
  **non-blocking conflict** (`source_vs_confirmed`). The confirmed value stays.
- **I-LED-4.** Claims, events and decisions are never updated or deleted. A correction is a new
  decision that names the old one.
- **I-LED-5.** Every status change has a `status_event`. Its cause resolves to exactly one claim
  event, decision, policy version, registry version or identity event.

### 7.5 Projecting a single-valued fact

The project stage picks the effective value in this order:

1. **Confirmed.** Effective confirmations (§7.4) win. If there are two or more values, I-LED-2
   applies and the oldest confirmation remains in effect.
2. **Authoritative.** Otherwise, accepted claims ranked `authoritative` (§7.7) apply.
   - One distinct value: it is effective.
   - Several distinct values from different streams: a **blocking** conflict
     (`authority_vs_authority`) opens. The previously projected value stays if it is among
     them. If not, the fact is left unset.
3. **Contributory.** Otherwise, accepted claims ranked `contributory` apply. A disagreement
   opens a **non-blocking** conflict, and the newest `observed_at` wins, unless the rule's
   `tie_break` is `conflict`.
4. **Advisory.** Otherwise, accepted claims ranked `advisory` apply, but only if the rule sets
   `auto_accept`, and only while nothing ranks higher. Advisory claims never open conflicts;
   the UI shows them as alternatives.
5. **Same stream.** Within one stream, a newer revision's value supersedes that stream's older
   value.

### 7.6 Pipeline stages and their versions

| Stage | Inputs | Outputs | Version |
|---|---|---|---|
| **parse** | source bytes | stated claims; claim events for the stream | `parser@v` |
| **infer** | the stream's current stated claims; the ruleset | inferred claims in the stream `inference:<stream>`; claim events | `ruleset@v`, plus `rule_version` per rule |
| **resolve** | source refs of all claims; labels and aliases; latest inventory and IT revisions; the resolver policy | identity events; provisional records (as record events); resolved claims (`method = resolved`, e.g. `asset:` URL → inventory uid); identity candidates | `resolver@v` |
| **project** | bound claims; decisions; authority, multi-value and registry versions | fact state; attributes; asserted edges; record status; conflicts; status events | `projector@v` + `policy@v` + `registry@v` |
| **derive** | projections; the registry | derived edges; `v_installation`; display names | `registry@v` + `deriver@v` |
| **reconcile** | projections; identity candidates; the reconciliation policy | candidates; review items; merges the policy authorizes (recorded as decisions with `actor = policy:…`) | `reconciler@v` |

When each stage skips or reruns:

| Stage | Skips when | Must rerun when |
|---|---|---|
| parse | `(stream, content_hash, parser@v)` was already parsed. The revision row is still written, with no claims | new bytes; a parser version bump |
| infer | the digest of `(input claim set, ruleset@v)` is unchanged | input claims changed; a ruleset bump |
| resolve | the digest of `(source refs, label watermark, inventory watermarks, merge-decision watermark, resolver@v)` is unchanged | a label or alias changed; a merge or bind decision; an inventory or IT import; a resolver bump |
| project | the ledger watermark and all versions are unchanged | any new ledger event; any version bump |
| derive | the projection watermark is unchanged | any projection change; a scheduled clock tick that crosses an Installation boundary |
| reconcile | the input digest is unchanged | after resolve runs; on a schedule; a policy bump |

Every run writes a `job_run`. Each stage records the ledger `seq` it has consumed, so it resumes
from that watermark. As a result, re-importing identical bytes **skips parse but still reruns
resolve and project** if an alias, an inventory revision, a policy or a decision has changed
since the last run.

### 7.7 Authority policies

Policies are YAML files in the repository. They are reviewed like code, loaded as a versioned
`authority_rule` set, and validated at load time.

```yaml
policy_version: 2026.10.1
defaults:                       # used when no rule matches, by claim method
  manual: authoritative         # always paired with a confirm decision, which the UI issues
  stated: contributory
  resolved: contributory
  inferred: advisory
rules:
  - id: insight-identity
    match: {predicate: [attr:serial, attr:inventory_number, attr:manufacturer, attr:model],
            object_type: Equipment+, owner_workspace: inventory, source_kind: insight}
    rank: authoritative
  - id: it-registry-addressing
    match: {predicate: [attr:ip, attr:mac, attr:fqdn], object_type: IT Equipment+, source_kind: it-registry}
    rank: authoritative
    exclusive_set: true
  - id: config-owns-control
    match: {object_type: Control Item+, source_kind: epik8s}
    rank: authoritative
  - id: sparc-control-from-other-files       # a test branch or another beamline's file
    match: {facility: SPARC, object_type: Control Item+, source_kind: epik8s}
    rank: advisory                           # …cannot overwrite SPARC's control records
  - id: sparc-control-from-sparc-main
    match: {facility: SPARC, object_type: Control Item+,
            source_instance: "epik8s:epik8-sparc#deploy/values.yaml@main"}
    rank: authoritative
  - id: photo-serial
    match: {predicate: attr:serial, source_kind: photo}
    rank: advisory
    auto_accept: false                       # proposed: a person confirms what a photograph read
  - id: pbs-design-wp04
    match: {predicate: "attr:pbs_*", object_type: Functional Element+, source_kind: pbs, domain: WP-04}
    rank: authoritative
  - id: screen-camera-pairing
    match: {predicate: "rel:composed of", source_kind: inference, rule: infer.screen.camera_pair}
    rank: advisory
    auto_accept: false
```

**Match dimensions:** `predicate` (exact or glob), `object_type` (a trailing `+` includes
subtypes), `owner_workspace`, `facility` (`argus_facility`), `domain` (`argus_system` or work
package), `source_kind`, `source_instance`, and `rule` (for inferred claims).

**Effects:**

- `rank`: `authoritative`, `contributory`, `advisory` or `ignored`;
- `auto_accept`: defaults to true for authoritative and contributory, false for advisory;
- `exclusive_set`: for multi-value facts (§7.8);
- `tie_break`: `conflict` (the default) or `newest_observed`.

**Selecting the rule for a claim:**

1. Collect every rule that matches.
2. The most specific rule wins. Specificity is the sum of per-dimension scores:

   | Dimension | Score |
   |---|---|
   | `source_instance` | 3 |
   | `source_kind` | 1 |
   | `predicate`, exact | 2 |
   | `predicate`, glob | 1 |
   | `object_type` | 1 + its depth in the hierarchy |
   | `owner_workspace`, `facility`, `domain`, `rule` | 1 each |

   In the example above, `sparc-control-from-sparc-main` scores 6, `sparc-control-from-other-files`
   scores 4 and `config-owns-control` scores 3. So SPARC's own file is authoritative for SPARC's
   control records, and any other EPIK8s file is only advisory there.
3. A tie in score is broken by an explicit `priority`.
4. If two rules still tie with different effects, **the policy is rejected at load time**
   (I-PROJ-3). There is no ambiguity at runtime.
5. If no rule matches, `defaults` apply according to the claim's method.

**Changing a policy** means issuing a new `policy_version`. The project stage then reruns, and
every status that changes gets a `status_event` with `cause = policy:<version>`. A policy change
never affects a confirmation (I-LED-1).

### 7.8 Multi-value facts

Every multi-valued attribute and every n-valued asserted relation declares a **mode** per source
kind, in `multivalue_rule`. Each set member is its own fact, `(subject, predicate, member)`, so
an unchanged member writes nothing.

| Mode | What a source revision asserts | How a member leaves | Combining several sources |
|---|---|---|---|
| **replace set** | its complete set | a member missing from the stream's next revision is marked `disappeared`, *for that stream only* | the union of accepted members from all streams. If an authoritative rule sets `exclusive_set`, the effective set is that stream's set plus any confirmed members; members from other streams outside it appear as non-blocking conflicts |
| **members** | individual members, with no claim of completeness | only through an explicit absence claim or a decision. Absence from a snapshot means nothing | the union of accepted members |
| **delta** | add operations (`polarity = present`) and remove operations (`polarity = absent`) | an `absent` claim | per member, the highest-ranked polarity wins. An authoritative `present` against a person's `absent` is a `source_vs_confirmed` conflict |
| **ordered list** | the whole list, as one value | the list is replaced as a whole | treated as single-valued (§7.5): the list is one value |

**People editing sets.** A person who removes a member that a source states issues a `reject`
decision on that member, which confirms its absence. The member stays suppressed while the
source keeps stating it, and a non-blocking conflict is recorded. A person who adds a member
issues a `delta` claim plus a `confirm`.

Core declarations:

| Predicate | Mode by source |
|---|---|
| `zone` (FE, Control Device) | epik8s: replace set · person: delta |
| `networks` (IOC), `rel:on network`, `rel:mounts` | epik8s: replace set · person: delta |
| `argus_keywords` | person: delta · other sources: members |
| `insertion_positions`, `position_labels` | epik8s: ordered list · person: ordered list |
| `ip`, `mac` (IT Equipment) | it-registry: replace set, `exclusive_set` · others: members |
| `serial_modes` (Serial Converter) | it-registry: replace set |
| `connectivity` (Utility Requirement) | pbs: replace set |
| `rel:acts on` | epik8s and inference: replace set · review tool (epik8s-devices): members · person: delta |
| `rel:served by`, `rel:powers`, `rel:composed of`, `rel:cools` | inference and pbs: replace set · person: delta |
| `rel:traverses`, `rel:measures`, `rel:described by` | members · person: delta |

---

## 8. Installation

### 8.1 The record

| Field | Kind | Notes |
|---|---|---|
| `uid` | opaque UUIDv7 | never derived from other keys |
| `key` | `INS-<ULID>` | opaque, stable and globally unique; independent of position and asset keys |
| display name | projection | `"<asset> @ <position> [from → until]"`, recomputed whenever either end is renamed or re-keyed |
| `installed at` → Pos, `installation of` → Eq | asserted relations | exactly one each, and **immutable once Confirmed**. If the asset or position was wrong, reject this Installation and record a new one |
| `valid_from` | timestamptz or null | inclusive |
| `valid_from_kind` | `date` · `before_records` · `unscheduled` | |
| `valid_until` | timestamptz or null | exclusive |
| `valid_until_kind` | `open` · `date` · `unknown_past` | `unknown_past` requires `valid_until_bound`, no later than the time the end was recorded |
| `precision_from`, `precision_until` | `instant` · `day` · `month` · `year` | the stored value is the start of the bucket |
| `removal_reason` | enum | Failure, Maintenance, Upgrade, Relocation, Decommissioning, Unknown |
| `work_reference` | string | ticket or work order |
| **workflow status** | projection of decisions | `Proposed`, `Confirmed` or `Rejected` |
| aliases | `asset_labels` | Insight installation id, work-order id, legacy key, legacy uid |

Every field is a fact in the ledger, so its history is the history of its claims and decisions.

### 8.2 Temporal state is derived at a query time *t*

These states apply to Confirmed Installations:

| State | Condition |
|---|---|
| **Planned** | `valid_from_kind = unscheduled` |
| **Future** | `valid_from > t` |
| **Current** | the start has passed (`valid_from ≤ t`, or `valid_from_kind = before_records`), and the end has not: `valid_until_kind = open`, or `t < valid_until`, or `unknown_past` with `t < valid_until_bound` (flagged *uncertain*) |
| **Ended** | `valid_until ≤ t`, or `unknown_past` with `valid_until_bound ≤ t` |

Intervals are **half-open**: `[valid_from, valid_until)`. So a handover where A ends at `T` and B
starts at `T` is valid and leaves no gap. `before_records` is treated as −∞ and `open` as +∞.

### 8.3 Validation invariants

These apply to **Confirmed** Installations. Define the effective bounds as:

- `lo = valid_from`, or −∞ for `before_records`;
- `hi = valid_until`, or `valid_until_bound` for `unknown_past`, or +∞ for `open`.

| Id | Invariant |
|---|---|
| **I-INS-1 (one place per unit)** | for any Equipment, no two Confirmed Installations have overlapping `[lo, hi)` |
| **I-INS-2 (one unit per position)** | for any position, no two Confirmed Installations have overlapping `[lo, hi)` |
| **I-INS-3** | `lo < hi` wherever both are known; an `unscheduled` Installation has no `valid_until` |
| **I-INS-4** | `installed at` targets an installable type and `installation of` targets Equipment. Both are immutable after confirmation |
| **I-INS-5** | the Installation belongs to its position's workspace |
| **I-INS-6 (uncertain overlap)** | if the precision buckets overlap but the stored values do not, the Installation is accepted with a warning, not an error |
| **I-INS-7** | Proposed Installations may overlap anything. A decision that would confirm an overlap fails, unless the same atomic batch also ends or corrects the other Installation |

**Compatibility check.** The Equipment's type or class should match the position's
`position_class` or typed element. A mismatch is only a warning, because substitute units
happen.

### 8.4 Corrections and backdating

- **Corrections.** A correction is a `supersede` decision on `valid_from` or `valid_until` that
  names the earlier confirmation.
- **Backdating.** A backdated value is checked against I-INS-1 and I-INS-2 across every
  Confirmed Installation. A swap recorded late is therefore a two-decision batch: end A at T,
  start B at T.
- **Recomputation.** After a correction, the derive stage recomputes the current `realized by`
  and `v_installation`.
- **Past beliefs.** The old values stay in the ledger. "What did we believe on 1 June about what
  was installed in March?" is answered by replaying up to 1 June.

### 8.5 Lifecycle example: GUNSIP01

| Ledger seq | Event | Projected result |
|---|---|---|
| 1 001 | parse `epik8-sparc@6bca015`: device `GUNSIP01` appears | Control Device, Active |
| 1 002 | infer `infer.vac.sip@2`: position `SPARC:POS:GUNSIP01`, class Ion Pump | Position, Provisional → Active (the policy auto-accepts it) |
| 2 100 | inventory import: Ion Pump s/n 84321, Insight object 129573 | Equipment, Active (in `inventory`) |
| 2 101 | resolve: the IOC's `asset:` URL → object 129573 → a resolved installation claim | Installation INS-01J9…, **Proposed** |
| 2 150 | decision: operator `confirm`s, `valid_from = before_records` | **Confirmed** and Current; derived `realized by` → 84321 |
| 3 010 | re-import of the same bytes | parse skipped; resolve and project run; no events |
| 3 400 | batch: `supersede` INS-01J9… with `valid_until = 2026-03-03T09:00Z`, reason Failure; `confirm` INS-01JB… (s/n 90001) from the same instant | 84321 Ended, 90001 Current; the derived edge moves to 90001 |
| 3 401 | query at `2026-03-02` → 84321; at `2026-03-03T09:00Z` → 90001 | |
| 4 000 | revision `epik8-sparc@a41f…` drops GUNSIP01 | the device claims `disappeared`, and the device becomes Retired. The position still has a Confirmed Installation, so it is **flagged**, not retired, and the Installation is **not** ended |

---

## 9. Connectivity and Access Points

### 9.1 Paths, segments and ports

These are as described in the first revision:

- a **Communication Path** runs from one IOC to one endpoint and carries the protocol and
  transport;
- an **Access Point** is the endpoint as the configuration names it;
- a **Bus Segment** is the medium downstream of the endpoint. It holds the line parameters and a
  stated or inferred `port_number`;
- an **Equipment Port** is one physical port of one unit;
- **hops** (`traverses`) form an unordered series set.

The generalization table from the first revision (Ethernet native, Ethernet→Serial, GPIB, CAN,
fieldbus, IOC on the instrument) is unchanged.

### 9.2 Access Point semantics

An Access Point is an address in the control plane. A position does not implement an address; a
unit does. So the model separates the two links:

- **`assigned to`** (AP → position) is asserted. It says the address belongs to a place: the
  BTF supply's position for `192.168.192.40:502`, or the IT position `IT:POS:scsparcsipmxa001`
  for a converter hostname. Three sources can claim it:
  - the IT registry;
  - resolution (hostname or IP → IT position);
  - inference from the device that the configuration puts at that address.

  One position may have several addresses, for example data and management.
- **`implemented by`** (AP → Equipment) is **derived** when the AP is assigned. Its target is the
  Equipment of the Current, Confirmed Installation at the assigned position. If there is no such
  Installation, there is no edge, and the gap is visible.
- **Unassigned Access Points.** A resolver may still *assert* `implemented by`, by MAC or FQDN,
  as a transitional claim. Its history is record time only. Once the AP gets an assignment, any
  asserted `implemented by` is treated as an expectation: agreement is silent, and disagreement
  opens a non-blocking conflict (**I-AP-2**).
- **History across swaps.** "Which unit answered at this address at time *t*" is the
  Installation at the assigned position at *t* (valid time), bounded by the assignment's
  record-time history in the ledger. Nothing is re-pointed, so nothing is lost.
- **Ports follow the unit.** A Bus Segment's `attached to` is derived from its `port_number` on
  the unit now implementing the path's AP. After a converter swap, each segment attaches to the
  new unit's port with the same number. If the new unit has no such port, the gap is shown.

Invariants:

- **I-AP-1.** An AP has at most one active `assigned to`.
- **I-AP-2.** An assigned AP has no effective asserted `implemented by`.
- **I-AP-3.** An AP belongs to the beamline or IT workspace that owns the configuration naming
  it. Its assignment may point across workspaces.

### 9.3 Lifecycle example: a converter swap

Setup:

- `IT:POS:scsparcsipmxa001` is an IT-owned Equipment Position of class Serial Converter.
- Moxa M-5531 is installed there from `before_records`.
- SPARC's AP `NET:sparc:SCSPARCSIPMXA001` is assigned to that position.
- Four Bus Segments carry `port_number` 1 to 4.

IT swaps in M-7702 at time T with one decision batch. The derive stage then produces
`implemented by` → M-7702 and attaches each segment to M-7702's ports P1 to P4. For any
`t < T`, the answer is still M-5531. The root-cause walk reaches the right box both before and
after T.

---

## 10. Identity reconciliation

**Identity** is the binding `source_ref → uid`, a projection of `identity_event`s. Three
mechanisms keep duplicates out:

1. **Configuration imports never create Equipment.**
2. **A partial unique index** on active strong identifier labels: serial per manufacturer,
   inventory number, Insight objectId, MAC.
3. **Alias-aware resolution.** The resolver tries the key, then labels, then aliases, and
   creates a record only where §4.2 allows it.

**Candidates.** Each identity candidate carries a score and its evidence. The reconciliation
policy may auto-merge on a strong identifier when there is exactly one type-compatible
candidate, and the policy is recorded as the decision's actor. Everything else is proposed.

**Decisions:** `merge`, `reject_candidate`, `confirm_new`, `unmerge`. A merge:

- keeps the survivor's uid;
- re-points relations, ticket links, document relations, labels, comments and attachments to the
  survivor;
- rebinds the loser's source refs (`identity_event: rebound`), so the loser's claims now project
  onto the survivor, where the authority policy decides whether they win;
- adds `former_key` and `former_uid` labels to the survivor;
- marks the loser `Merged`, with `merged_into_uid` pointing to the survivor, and keeps it as a
  tombstone.

`unmerge` reverses a merge from the identity and record events. A rejected candidate is not
proposed again unless new strong evidence appears.

**Merges and Installations.** A merge leaves Installations unchanged, with one exception. If
both merged units were installed somewhere at overlapping times, the merge opens an I-INS-1
conflict for review.

---

## 11. Retirement and held revisions

- **Guard at parse.** A new revision is stored with `state = held` if either of these holds:
  - more than 10 % of the stream's subjects would disappear;
  - it would withdraw the last support of any record that has tickets, documents or a Confirmed
    Installation.

  A held revision's claim events are written, but projection does not consume them until an
  `approve_revision` decision. The earlier list-vs-mapping bug (AS §14.1) would have stopped
  here.
- **Retirement is a projection.** A record becomes `Retired` (`record_event: status`) when all
  of its `exists` facts are withdrawn, rejected or superseded and nothing confirmed supports it.
  Its asserted edges follow the registry's `on_source_retire` rule, and its derived edges are
  recomputed.
- **Positions are an exception.** A position with a Current, Confirmed Installation is
  **never** retired because a source withdrew it. It is flagged for review instead, because the
  hardware may still be in place.
- **Nothing is deleted.** Retired records stay reachable from their tickets and documents. They
  are hidden from default views.

---

## 12. Legacy migration

### 12.1 Evidence gathered per legacy object

| Code | Evidence | Read from |
|---|---|---|
| E-SER | `serial` or `inventory_number` is present, and **who wrote it**: the importer, a person or photo identification | attributes, `asset_history.author`, `asset_labels.issuer` |
| E-LBL | strong identifier labels (Insight `jiraObjectId`, `qrcode`), and whether each is `verified` | `asset_labels` |
| E-URL | `inventory_url` contains a resolvable `objectId`, and whether it resolves to exactly one inventory record | attributes, labels |
| E-ATT | attachments, and whether photo identification produced labels from them | `attachments`, `asset_labels` |
| E-TKT | linked tickets, with dates and summaries | `asset_tickets` |
| E-DOC | document relations and comments | `document_relations`, `asset_comments` |
| E-EDIT | fields that differ from what the importer would write today (found by re-running inference in dry mode). Split into **physical** fields (serial, location, condition, warranty, installed_on, manufacturer, model) and **functional** fields (description, zone, name) | attributes vs the dry-run output |
| E-HIST | human entries in the object's history; whether the importer or a person created it; the `inferred` keyword | `asset_history`, attributes |
| E-RULE | whether the current rules still produce this object from the current source | dry-run inference |
| E-COLL | identifier collisions with other active records | labels, attributes |

### 12.2 Outcomes

The first matching row, from top to bottom, decides the outcome:

| Outcome | Criteria | Result |
|---|---|---|
| **M-BLOCK** (blocked) | E-COLL: the object's strong identifier is already held by another active record with conflicting data; or the object changed after planning | nothing moves; the object is listed for manual resolution |
| **M-FUNC** (already functional) | a legacy inferred *element* (Quadrupole, BPM, Screen Station, Mirror…) | kept, and re-keyed only if needed. Its edges to assets are handled by the rows below |
| **M-POS** (pure control identity) | created by the importer; no E-SER, no E-LBL, no E-URL objectId; no physical E-EDIT; no E-ATT that produced an identifier | the legacy row **becomes the Position**, retyped in place with the same uid. All dependents stay |
| **M-PHYS** (confirmed physical identity) | at least one of: E-SER written by a person; a verified E-LBL; an E-URL resolving to exactly one inventory record. And no contradicting identifier | the legacy row becomes the Position. The Equipment is either the matched inventory record, or is created in `inventory` as Active. The Installation is Confirmed, with `actor = migration:<plan>` and the history entry as `basis`. `valid_from` is `installed_on` if a person set it, otherwise `before_records` |
| **M-MIXED** (mixed or ambiguous) | physical evidence that is unverified or conflicting: a photo-read serial never verified; a physical E-EDIT with no identifier; an E-URL that matches several records or none; attachments with no serial | the legacy row becomes the Position. **Provisional Equipment** is created and the Installation is **Proposed**. A review item carries the evidence |
| **M-RETIRE** (stale inference) | E-RULE is false, and there is no E-TKT, E-DOC, E-ATT, E-EDIT or E-HIST from a person | `Retired`, not deleted |

Anything that matches no row is treated as **M-MIXED**. The algorithm never guesses in favour of
physical identity.

### 12.3 Algorithm

```
plan(workspace, plan_id):
  snapshot every legacy record in the workspace: attributes, labels, attachments, tickets,
      documents, comments, relations, history → a pre-image, with updated_at
  dry-run parse + infer + resolve on the current sources (no writes)
  for each legacy record r:
      ev      = gather_evidence(r)                      # §12.1
      outcome = classify(ev)                            # §12.2, first match
      actions = actions_for(outcome, r, ev)             # new records, retypes, relation moves,
                                                        # dependent routing, decisions to write
      write migration_item(plan_id, r.uid, outcome, ev, actions,
                           pre_image_hash, status='planned')
  write the decision report (§12.5); stop               # nothing is applied

review:
  owners inspect the report. They may override an outcome per item with a
  `migration_override` decision, which is recorded; the affected items are re-planned.

apply(plan_id):                                         # resumable; idempotent per item
  for each item with status in ('planned', 'failed'), in dependency order:
      if hash(current pre-image) != item.pre_image_hash:
          mark 'stale'; continue
      begin transaction
          perform item.actions through the ledger and record events
          write migration_map rows, and migration_event('applied', inverse_actions)
          run item-level invariants (§12.6)
          on failure: roll back the transaction; mark 'failed' with the reason
      commit; mark 'applied'
  run workspace-level invariants; mark the plan 'verified' or 'needs_attention'

rollback(plan_id [, items]):                            # allowed until the plan is finalized
  for each applied item, in reverse order:
      refuse if a created record has since gained dependents not covered by the item's actions
      apply inverse_actions: restore the pre-image, move dependents back, mark created records
          Retired with cause rollback, revoke the migration's decisions
      write migration_event('rolled_back')

finalize(plan_id):
  after sign-off, rollback is no longer available; later corrections use normal decisions
```

**Dependency order:**

1. M-BLOCK and M-FUNC;
2. M-POS;
3. M-PHYS and M-MIXED, which create Equipment and Installations;
4. relation rewrites: `powers`, `composed of`, `acts on`, and `served by` in place of
   `realized by` for shared electronics;
5. M-RETIRE last.

### 12.4 Routing dependents when one legacy object becomes a Position and Equipment

| Dependent | Goes to | Rule |
|---|---|---|
| uid, key history | the **Position** keeps the legacy uid and gets the new key `FAC:POS:<tag>`, with a `former_key` label | the legacy object's relations are mostly control and functional, and it is what tickets were raised against |
| tickets | the Position. For M-PHYS they are **also** linked to the Equipment, with the link labelled `origin=migration-split` | the unit's failure history must include them, and the duplication is declared |
| documents, comments | the Position | |
| attachments | the Equipment, if photo identification produced a label from them or a person tagged them as a photo of the unit; otherwise the Position | |
| labels | strong identifiers (serial, qrcode, jiraObjectId, inventory) go to the Equipment; everything else stays | |
| attributes | physical fields become claims on the Equipment (`method = manual` if a person wrote them, with a `confirm` decision for M-PHYS and none for M-MIXED). Functional fields stay on the Position | |
| relations | the registry's domains decide: `located in` and `instance of` go to the Equipment (as attributes); `acts on`, `provided by`, `powers`, `composed of` and `served by` go to the Position | |
| legacy markers | `argus_keywords: inferred`, `argus_source*`, `argus_provenance` and `endpoint_kind_source` become claims in a `legacy:<workspace>` stream with `revision = unknown` | the first real re-import supersedes them |

The table `migration_map(legacy_uid → new_uid, role ∈ {position, equipment, installation},
plan_id)` is permanent. Every legacy reference, including external links and bookmarks, therefore
resolves to all of the records it became.

### 12.5 The decision report

One row per legacy object, written as both CSV and JSON:

```
legacy_uid, legacy_key, legacy_type, workspace, outcome, confidence,
evidence            codes + values
planned_records     [(role, uid, key, type, workspace, record_status)]
planned_installation (valid_from, kind, workflow status)
dependents_moved    {tickets, docs, attachments, labels, comments, relations: counts by destination}
warnings, reviewer_required, override
```

Examples:

```
SPARC:AST:vac-gunvpc:GUNSIP01   Ion Pump   M-PHYS   0.95
   evidence   E-SER(serial=84321, author=user:rossi), E-URL(objectId=129573 → 1 match)
   records    position SPARC:POS:GUNSIP01 (same uid) · equipment INV:… (matched)
              · installation INS-… Confirmed from before_records
   dependents tickets 3 → position (+3 split-linked to equipment)

SPARC:AST:histar:GUNQUA01       Power Supply   M-POS   1.0
   evidence   no identifiers, no physical edits
   records    position SPARC:POS:GUNQUA01/PS (same uid)
   relations  powers → Quadrupole kept

SPARC:AST:accameras:AC101       Camera   M-MIXED   0.5
   evidence   E-ATT(2 photos, no label), E-EDIT(location=Rack C3)
   records    position SPARC:POS:AC101 · equipment PROV:… Provisional · installation Proposed
   reviewer   diagnostics
```

### 12.6 Migration invariants and validation reports

Invariants are checked per item and per workspace. A failure fails the item or blocks
finalization.

| Id | Invariant |
|---|---|
| **I-MIG-1 (nothing lost)** | for each kind of dependent, the count before equals the count after, summed over the records in `migration_map`. Declared split duplicates are counted separately |
| **I-MIG-2 (traceable)** | every legacy uid appears in `migration_map`, and every legacy key resolves through labels |
| **I-MIG-3** | no relation references a Retired or Merged record, except as the registry's retire rules allow |
| **I-MIG-4** | I-INS-1 to I-INS-7, I-AP-1 to I-AP-3 and identifier uniqueness all hold |
| **I-MIG-5** | the number of registry violations in the workspace does not increase (warn-mode report, before vs after) |
| **I-MIG-6** | rebuilding the projection from the ledger gives exactly the post-migration state |
| **I-MIG-7 (behaviour)** | on a golden set of past incidents, root-cause walks return the same causes or more precisely resolved ones (equipment instead of channel, never fewer) |

The migration runs first on a restored copy of production. It then runs per workspace in
production, after a database backup, with a rollback window until finalization (decision D11).

---

## 13. Implementation plan

Each step proves something before the next step depends on it.

```
P0 safety fixes ──────────────────────────────────────────────┐
S1 vertical slice (fixture workspace) ─┬─▶ S2 shadow pipeline ─┼─▶ S4 migration apply ─▶ S5 cut-over ─▶ S6 connectivity ─▶ S7 enforce
                                       └─▶ S3a classification dry-run reports (read-only) ─┘            └─▶ S8 extensions
                     S3b registry warn + derived edges (after S2) ─┘
```

| Step | Scope | Depends on | Exit criterion |
|---|---|---|---|
| **P0 safety fixes** | stated `upsert` keeps values edited since the last import; remove `remove_all_before`; record the commit SHA; permission checks on `--it-workspace` and `create_asset`; correct the C15 figures | — | a re-import leaves a hand-edited IOC description intact |
| **S1 vertical slice** | the ledger tables; the six stages, only for the slice's predicates; authority and multi-value loaders with validators; the Installation type, its validation and the derived `realized by`; a minimal Insight fixture importer; the review API (list items, post decisions) | P0 | acceptance tests A1–A16 (§14) pass; replay equals incremental projection |
| **S2 shadow pipeline** | all EPIK8s and PBS predicates through the pipeline, on copies of production workspaces. It writes to shadow projections while the legacy importers keep writing | S1 | the diff report between shadow and legacy is empty or every difference is explained |
| **S3a classification** | the §12 plan and report on real workspaces, with no writes | S1 (for the resolver) | owners have reviewed the reports and recorded any overrides |
| **S3b registry and derivation** | registry in `warn` mode; derived edges; attribute → edge sync | S2 | the violation report has been triaged |
| **S4 migration apply** | per workspace, with rollback | S2, S3a, S3b | I-MIG-1 to I-MIG-7 hold; plan finalized |
| **S5 cut-over** | importers and the UI write only through the ledger; legacy fields become read-only; `equipment_class` governance and its reports go live | S4 | nothing writes `attributes` or `relations` directly (enforced by DB grants) |
| **S6 connectivity** | Communication Paths, Bus Segments, Equipment Ports; AP assignments; derived `implemented by` and `attached to` | S5 | the IT §4.3 box, port and switch impact figures are reproduced |
| **S7 enforce** | registry in `enforce` mode; retirement guard live on all streams | S5 | — |
| **S8 extensions** | one per trigger | S5 | an owner, a source and a query in the test suite |

---

## 14. Acceptance tests for the vertical slice

**Fixture.**

- Workspaces: `slice-sparc` (beamline), `slice-inventory` and `slice-it`.
- Configuration source: a trimmed `values.yaml` with IOC `vac-gunvpc`, devices `GUNSIP00` to
  `GUNSIP02` on `scsparcsipmxa001:4003`, and the IOC's `asset:` URL with `objectId=129573`.
- Insight fixture: Ion Pump s/n 84321 (objectId 129573, Rack B12) and Ion Pump s/n 90001
  (objectId 130004, Storage).

| # | Given | When | Then | Validates |
|---|---|---|---|---|
| A1 | an empty ledger | import revision r1 | device claims appear; Control Devices Active; position `SLICE:POS:GUNSIP01` inferred and made Active by policy; its `status_event` has cause `policy:<v>` | parse, infer, project; automatic acceptance is recorded |
| A2 | A1 | import the Insight fixture | two Equipment records in `slice-inventory`; the resolve stage produces the resolved claim `asset:` → 84321; an Installation is **Proposed** | resolution; reconciliation proposal |
| A3 | A2 | an operator `confirm`s the Installation with `valid_from = before_records` | workflow status Confirmed, temporal state Current; derived edge `GUNSIP01 realized by 84321`; key `INS-<ULID>`; display name computed | Installation; derived edges |
| A4 | A3 | re-import the unchanged bytes of r1 | `job_run(parse)` skipped; **0** claims and **0** claim events; resolve and project `job_run`s recorded; no status events | parse idempotency |
| A5 | A4 | add an alias label that makes a previously unresolved source ref resolvable; re-import r1 unchanged | parse skipped; **resolve reruns** and binds the ref; projection updates | resolution independent of parsing |
| A6 | A3 | an operator edits the device description; re-import r1 | the description is kept, because a confirmed manual value outranks a stated one. A non-blocking `source_vs_confirmed` conflict opens only if the source states a different value | precedence; I-LED-3 |
| A7 | A3 | swap batch: `supersede` INS-a with `valid_until = T` (Failure); `confirm` INS-b (90001) from `T` | 84321 Ended, 90001 Current; `realized by` re-derived; 84321's `argus_location` is not changed by the Installation | swap; half-open handover |
| A8 | A7 | historical queries at `T − 1 s` and at `T` | 84321, then 90001 | temporal model |
| A9 | A7 | try to confirm 90001 at `SLICE:POS:GUNSIP02` from `T + 1 d` while INS-b is still open | the decision fails with I-INS-1; nothing is written except the audit record of the rejected attempt | overlap validation |
| A10 | A7 | backdated correction: `supersede` INS-b with `valid_from = T − 2 h` without ending INS-a earlier | fails with I-INS-2. The same correction batched with INS-a `valid_until = T − 2 h` succeeds. Replaying to a point before the correction shows the old belief | backdating; atomic batches |
| A11 | A3 | one person confirms `argus_location = Rack B13` on 84321; a second person confirms `Rack B14` without `supersedes` | a blocking `confirmed_vs_confirmed` conflict opens; the projected value stays B13 | I-LED-2 |
| A12 | A11 | a reviewer issues a `supersede` naming the B13 confirmation, with value B14, and a `resolve_conflict` | B14 is effective and the conflict is resolved; both confirmations and the resolution remain in the ledger | explicit supersession |
| A13 | A12 | a new Insight revision states `Rack B12` | a non-blocking `source_vs_confirmed` conflict opens; B14 stays | sticky confirmation |
| A14 | A3 | revision r2 removes `GUNSIP02` (in this small fixture, above the 10 % guard) | r2 is `held` and nothing retires. After `approve_revision`, the GUNSIP02 Control Device is Retired, its edges are retired and its tickets still resolve; its position, which has no Installation, retires; `GUNSIP01`'s position is untouched | retraction; guard; non-destructive retirement |
| A15 | A1 | a reviewer `reject`s the inferred position `SLICE:POS:GUNSIP00` by fingerprint; re-import r1, then r2 | the position is not proposed again, and its status stays `rejected` | rejection memory |
| A16 | A1–A15 | drop every projection and rebuild from the ledger; then publish a new `policy_version` that changes one rule | the rebuild yields identical attributes, edges, record statuses, conflicts and `v_installation`; the policy change writes status events that cite the new version | auditability; policy versioning |

---

## 15. Invariants (collected)

| Id | Invariant |
|---|---|
| I-LED-1…5 | §7.4: sticky confirmations; conflicting confirmations; source vs confirmed; append-only; every status change has a cause |
| I-PROJ-1 | `assets.attributes` and the asserted `relations` rows equal the projection of the ledger at the project stage's watermark. Only the project stage writes them |
| I-PROJ-2 | a derived edge exists exactly when its registry rule holds on the current projections. Nothing else writes derived edges |
| I-PROJ-3 | an authority policy with two equally specific rules of different effect cannot be loaded |
| I-REL-1 | every `relations` row's type is in the registry at the recorded registry version, and its domain, range, cardinality and acyclicity hold (warn first, then enforce) |
| I-REL-2 | a `composed of` target has at most one composite; components have no `part of` of their own; `part of` never targets a Location |
| I-INS-1…7 | §8.3 |
| I-AP-1…3 | §9.2 |
| I-ID-1 | at most one active record per strong identifier. A Merged record has a `merged_into_uid` that resolves to an active record |
| I-ID-2 | every source ref has at most one binding at a time; rebinding writes an `identity_event` |
| I-RET-1 | no record referenced by a ticket, a document or a Confirmed Installation is ever deleted |
| I-RET-2 | a position with a Current, Confirmed Installation is not retired because a source withdrew it |
| I-MIG-1…7 | §12.6 |
| I-CAT-1 | every `Other Equipment` has an `equipment_class` from the current vocabulary; deprecated classes cannot be assigned |

---

## 16. Decisions needed from stakeholders

- **D1. System of record for physical assets.** Does the hub mirror Jira Insight, or become the
  record? This decides whether Installations are written back to Insight.
- **D2. Inventory and IT staffing.** Who staffs these workspaces, and who owns **IT positions**
  (rack slots or host roles) and records IT swaps?
- **D3. Review owners** for each domain (vacuum, magnets, diagnostics, IT). They handle
  proposals, conflicts and migration items.
- **D4. Auto-merge policy.** May a single strong-identifier match merge records without a
  person?
- **D5. Position granularity.** Is every configured channel a position, or only equipment that
  is swapped as a unit?
- **D6. Visibility.** May positions and Installations be readable from every workspace?
  Engineering records stay private either way.
- **D7. Thresholds.** The retirement guard (10 %) and the `Other Equipment` promotion values
  (25 objects, 2 workspaces, 5 % Unclassified).
- **D8. Split tickets.** In M-PHYS, may legacy tickets be linked to both the Position and the new
  Equipment?
- **D9. Initial authority policy.** Who signs the first `policy_version`, and who may change it?
- **D10. Projection latency.** Must the UI show a user's own edit immediately (projection inside
  the request), or is a delay of a few seconds acceptable?
- **D11. Migration rollback window** before finalization. The proposal is 30 days per workspace.
- **D12. Carried over from the first revision:** the status of the DNS naming convention;
  ownership of the lattice; and which of the C15 counts are authoritative for tests.
