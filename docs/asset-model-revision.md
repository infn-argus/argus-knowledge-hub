# ARGUS asset model: revision

*A review of `asset-schema-design.md` and `it-model-design.md`, checked against the code that
implements them, and a revised model that keeps their architecture and makes it operable:
provenance, installation history, connectivity, relation governance, identity reconciliation and
ownership.*

Status: **proposal**. Where this document and the two design notes disagree, this one states the
intended model. It does not repeat what they get right; it refers to them by section
(`AS §n` = `asset-schema-design.md`, `IT §n` = `it-model-design.md`).

---

## 0. Summary

The model's central idea is sound and is kept. It separates **what the machine does**
(functional), **what is installed** (physical), **what kind of thing it is** (catalogue) and **how
it is controlled** (control), with place, IT and engineering records beside them. The weaknesses
lie in the joints between those planes. Links that change over time are stored as if they never
change. Facts from five sources end up in one attribute bag, where the last writer wins. Inferred
objects cannot be confirmed, rejected or merged. The relation vocabulary is a convention that
nothing checks.

The revision adds **three mechanisms** and **one concept**, and removes more types than it adds:

| | What | Replaces |
|---|---|---|
| Mechanism | **Fact ledger**: a provenance record for every imported, resolved, inferred or manual fact, keyed to a **source revision** | `argus_keywords: inferred`, `argus_source` / `argus_source_ref` (last writer wins), `argus_provenance` free text, `endpoint_kind_source` |
| Mechanism | **Relation registry**: canonical names, direction, domain and range, cardinality, derivation, lifecycle and causal semantics in one declaration, enforced at write time | free-form `relation_type`, `causal_model.SEMANTICS`, the edge naming that `relink_workspace` takes from attribute display names |
| Mechanism | **Identity reconciliation**: provisional records, match candidates, confirm or reject, merge with aliases and tombstones | inferred duplicates of inventory equipment "for whoever merges them" (AS §9.5) |
| Concept | **Position** (functional location) + **Installation** (an asset at a position, for a time interval) | timeless `realized by`, `installed_on` / `removed_on`, `replaced`, inferred "assets" keyed by control channel |

With these, the connectivity model splits cleanly. **Communication Path** is the logical path
from an IOC to a device. **Bus Segment** is the downstream serial, GPIB or CAN medium.
**Equipment Port** is the converter's physical port. **Hops** are cables and switch ports. The
first production release uses **54 concrete types**, not 122. The rest of the 122-type catalogue
is a target ontology, delivered in extensions as sources and owners appear.

---

## 1. Architectural assessment

### 1.1 What is right and is kept

- **Planes kept apart.** Keep functional, physical, catalogue, control, location and engineering
  as separate planes. The rest of this revision depends on it.
- **Configuration as objects** (AS §9). The configuration's own edges (`provided by`,
  `reached through`, `enabled by`) are the ones root-cause analysis needs.
- **Access points in the control plane** (AS §9, IT §4). 319 of 509 devices sit behind a shared
  address, and that address is the thing that fails.
- **Site-owned IT equipment** (IT §5): a converter is one object however many beamlines reach it.
- **Composite functional elements** (AS §4): a screen station is one element with parts.
- **Secret filtering** (AS §9.4), **idempotent imports** (AS §14), and the distinction between
  **stated, resolved, inferred and manually confirmed** (IT §3, §6).
- **Honest reporting**: importers report odd source data and keep the original words. They do
  not guess.
- **Semantics for failure propagation** (`causal_model.py`). This is the seed of the relation
  registry (§6), not something to replace.

### 1.2 Structural problems

1. **Physical identity comes from control addressing.** Inferred assets are keyed by channel,
   for example `SPARC:AST:vac-gunvpc:GUNSIP01`. Renaming the IOC creates a new "pump". Swapping
   the pump creates nothing. The object is really a **position** (the slot that `GUNSIP01`
   names), but it is typed and treated as a serialised box.
2. **Time is missing from the plane joints.** `realized by` has no interval. The asset has one
   `installed_on` / `removed_on` pair, and `replaced` runs Asset → Asset. That is three partial
   history mechanisms, and none of them answers "what was at GUNSIP01 on 3 March".
3. **Provenance is one attribute deep.** `argus_source` and `argus_source_ref` hold a single
   value, and the last importer to touch an object overwrites it. `inferred` is a user keyword
   that nothing ever removes. Confirmation cannot be recorded, and a rejection cannot be
   remembered.
4. **Relations are ungoverned.** The same verb takes different domains in different importers
   (`part of` → Section, Area or Module; `composed of` → Asset or element). Direction is implicit.
   Cardinality is never checked. Derived edges carry display names.
5. **One link has two representations.** `product_model` and `instance of`, `argus_location` and
   `located in`, `wbs_code` and `assigned to`, `spare_for` and `spare for`, `is_spare` and
   `Spare Part`. Nothing defines which form wins.
6. **No retirement.** A re-import adds and never removes. The only alternative, `remove_all_before`,
   hard-deletes and cascades to ticket links, relations and history.
7. **Ownership is implicit.** Physical assets live in whichever workspace inferred them. The
   `--it-workspace` path writes into another workspace without a permission check (IT §0).
8. **The catalogue is wider than its sources.** 122 types exist, and fewer than half have a
   source that fills them or an owner that maintains them.

### 1.3 Contradictions found

| # | Contradiction | Where |
|---|---|---|
| C1 | `Spare Part` must not carry PBS/WBS keys, yet it inherits them through `Asset → Engineered Item` | AS §4 tree vs §5.1 |
| C2 | `composed of` is defined as "Functional Element → its Asset parts", but the catalogue also lists an Asset composite (`Magnet Assembly` composed of a Power Supply), element→element composites (`RF Station` → Accelerating Structures, `Spectrometer Station` → Dipole), and inference writes `Mirror` → Motor Axis assets | AS §4, §6, §9.5 |
| C3 | `part of` is defined as membership in a section or system, but it is also written to **locations**: `zones:` → Area, and PBS `AREA/ZONE` → "Section or Area" (`pbs_import.py:494`), although `located in` exists | AS §9.1, §10.2 |
| C4 | `composed of` implies "removing a part breaks the whole", yet an X-band modulator shared by stations is composed into one of them | AS §4 vs §11.5 |
| C5 | Swap history is held three ways, none of them complete: `installed_on`/`removed_on` (one pair), `replaced` (Asset→Asset), and re-pointing `powers` edges | AS §5.3, §6, §11.1 |
| C6 | The worked example says `Power Supply → powers → Magnet Assembly` and `Quadrupole → realized by → Magnet Assembly`. Inference writes `Power Supply → powers → Quadrupole` and never creates a Magnet Assembly | AS §11.1 vs `element_inference.py:355` |
| C7 | "Beamline imports link to IT equipment; they do not create it", but the import does create it | IT §3 vs IT §0, `_it_equipment` |
| C8 | "The Access Point is always made" is listed as decided, but `access_point()` still returns matched equipment *as* the Access Point | IT §0, §6 vs `epik8s_import.py` `access_point` |
| C9 | "A person outranks it" holds only for inferred objects. `upsert()` replaces the whole attribute bag of every **stated** object on each re-import, so manual edits to IOCs, devices and access points are silently lost | AS §9.5 vs `epik8s_import.py` `upsert` |
| C10 | `argus_source_ref` is labelled "Source revision" but holds `repo@branch:path`. `Control Configuration` is "one values.yaml at one git revision" but is a single object updated in place | AS §5.1, §5.6 |
| C11 | "Nothing is deleted when it comes out" contradicts `merge_strategy=remove_all_before`, which hard-deletes and cascades | AS §5.3 vs `run_epik8s_import` |
| C12 | Spares are held four ways: `is_spare`, the `Spare Part` type, the `spare_for` attribute and the `spare for` relation | AS §5.3, §6 |
| C13 | `drives` is "the link to the physical asset" from `asset:`, but one `asset:` URL on an IOC that lists devices of several kinds cannot name one box per device | AS §9.2 |
| C14 | 156 planned PBS components (RF loads, couplers…) are created as `Asset`, defined as "the serialised box, with a purchase order". They have not been built and have no serial number | AS §10, §14.10 |
| C15 | Figures disagree: 141 serial lines measured vs 104 made, with BTF 16 vs 20; 17 abstract types vs "8"; 76/46 global/beamline types vs 59/44 in the diagram; 45 seeder tests vs 27 | IT §1 vs §0; AS §4, §8, §15, §14.3, §16 |

C15 probably reflects different counting rules, but the figures must be reconciled before they
are quoted as acceptance criteria.

### 1.4 Where the platform forces an intermediate object

`Relation` rows carry only `from`, `to` and `type`. The table below says, for each link that
carries information of its own, where that information goes.

| Link carries… | Example | Resolution | Why not a platform change |
|---|---|---|---|
| a time interval, evidence, a work order | asset at a position | **`Installation` object** | It is a business entity. It gets tickets, documents, search and permissions from the object machinery at no extra cost |
| protocol, transport, TCP port | IOC → device | **`Communication Path` object** | Same reason; it is also what fails |
| baud, framing, medium, topology | the RS-485 run behind a Moxa port | **`Bus Segment` object** | Several devices share one segment |
| port number, port kind, mode | converter port 3 | **`Equipment Port` object** | The port is a physical thing that cables plug into |
| hop order along a path | cable → switch port → converter | not stored. Hops form an unordered series set (§9.4) | Order does not change impact analysis. If troubleshooting needs it, add a `Path Hop` object in a later extension |
| a bus address or channel | device 5 on a bus | on the **Control Device** (`address`, `channel`), where the configuration states it | It is already there |
| a permit threshold | RF conditioning enabled by GUNSIP01 at 3E-7 | stays in the source device's `settings` (AS §9.3); an `Interlock Condition` object only if thresholds must be queried | Deferred |
| **provenance of any fact** | "stated by epik8-sparc@6bca015, path …" | **platform table** (§7), not objects | There are tens of thousands of facts. Objects would flood search and the graph |
| derivation and status of an edge | derived, retired | **platform columns** on `relations` (§6.1) | System metadata, not domain data |

---

## 2. Revised principles

The existing principles in IT §3 remain. These are added or sharpened:

1. **Functional location vs equipment.** A *position* is the stable place in the machine where a
   function is performed. An *asset* is the unit currently doing it. Control, supply and
   composition topology is recorded between positions, so it survives swaps. Physical units
   attach to positions only through `Installation`.
2. **Configuration names positions, not boxes.** An LNF device name such as `GUNSIP01` or
   `AC1FLG01` is a functional tag. It keys a position. It never keys a physical asset.
3. **Every fact has a source.** The attribute bag and the relation table hold the *current
   effective state*. The fact ledger holds *why*. No importer writes an attribute or an edge
   without a ledger record.
4. **One authoritative form per link.** Each form is either an attribute, a relation or an
   intermediate object (§6.3). The other forms are derived, marked as derived, and never
   edited directly.
5. **Owners create; others propose.** A workspace creates only the object classes it owns
   (§4). It links to visible objects it does not own. It changes them only by proposing facts.
6. **Nothing that other records point at is deleted.** Stale objects are *retired*, duplicates
   are *merged* into a tombstone, and history stays queryable.
7. **Types follow sources and questions.** A type enters production when a source fills it,
   an owner maintains it and a query needs it.

---

## 3. Revised core metamodel

### 3.1 The planes and their joints

```
                               FUNCTIONAL  (beamline)                       CATALOGUE (catalogue ws)
                 Facility ◄─part of─ Section ◄─part of─ Screen Station          Product Model ──supplied by──▶ Vendor
                                                     │ composed of                     ▲
                                                     ▼                                 │ instance of (derived from attribute)
   Control Device ──acts on──▶ Equipment Position  SPARC:POS:AC101 (Camera)            │
        │                            ▲                                                 │
        │ on path                    │ installed at            PHYSICAL (inventory / it ws)
        ▼                            │                                                 │
   Communication Path          Installation ──installation of──▶ Camera  s/n 22817 ────┘
        │ enters at             valid_from 2024-05-02                 │
        ▼                       valid_until —                         │ located in (derived from attribute)
   Access Point ──implemented by──▶ Serial Converter (it)             ▼
        (beamline)                     ▲ port of                  Rack B12 ─within─▶ Area LNT ─within─▶ Building
                                       │
   Communication Path ──continues on──▶ Bus Segment ──attached to──▶ Equipment Port 3

   FACT LEDGER (platform table): every attribute value, relation and object above
        → source revision · method · rule · evidence · confidence · status · confirmation
```

### 3.2 Metamodel elements

| Element | Kind | Purpose |
|---|---|---|
| **Item** | abstract type | Shared keys that join objects to tickets and documents (`argus_*`, `description`) |
| **Functional Element** | abstract type | A place in the machine's function, including breakdown (PBS/WBS) keys. Its subtypes include **Equipment Position**, the generic slot |
| **Physical Asset** | abstract type | Anything physical and trackable. **Equipment** (serialised unit) and **Equipment Port** sit under it |
| **Catalog Item** | abstract type | Product Model, Vendor |
| **Control Item** | abstract type | Configuration as objects, including Communication Path and Bus Segment |
| **IT Record** | abstract type | Address Record (later Network Segment) |
| **Record** | abstract type | **Installation**, and the Engineering Records |
| **Location** | abstract type | Building, Area, Rack |
| **Source Revision** | platform table | One input to one import run: source, revision, hash |
| **Assertion** | platform table | One fact from one source, with method, rule, evidence, status and confirmation |
| **Relation Type** | platform table, seeded from code | The registry |
| **Identity Candidate** | platform table | A proposed "these two records are the same thing" |
| **Asset Label** (existing) | platform table | External identifiers and aliases: serial, MAC, FQDN, Insight objectId, former key |
| `assets.record_status` | new column | `Provisional`, `Active`, `Retired`, `Merged`: the record's state, separate from `argus_lifecycle` (the equipment's operational state) |
| `relations.derivation`, `.status` | new columns | `authored`, `imported`, `inferred` or `derived`; `active`, `proposed` or `retired` |

`record_status` is a column, not an attribute, because constraints and every default query
filter on it (`Active` only). It is system state, not domain data.

---

## 4. Ownership and authority

### 4.1 Workspaces

| Workspace | Owns (creates, edits, retires) | Authoritative sources | Objects visible elsewhere |
|---|---|---|---|
| `catalogue` | all shared **types**; Product Model, Vendor | vendor data, catalogue editors | all (flagged global) |
| `inventory` (site) | **Physical Assets that are not IT**, Location | Jira Insight asset schemas; inventory staff | all (flagged global) |
| `it-infrastructure` (site) | IT Equipment, their Equipment Ports, Address Records, later Network Segments | IT registry (Insight IT schemas, DNS/DHCP), IT staff | all (flagged global) |
| beamline (`sparc`, `btf`, …) | Functional Elements and Positions, Control Items (incl. Paths, Bus Segments, Access Points), **Installations**, Engineering Records | its configuration repository, its PBS matrix, its operators | positions, elements and installations flagged global (read-only elsewhere); engineering records never |

**Answer to "which workspace is authoritative for physical assets?"** `inventory`, or
`it-infrastructure` for IT equipment. A beamline never owns a physical asset. It owns the
*positions* those assets are installed at, and the *installations* that say so. The beamline
owns installations because its operators perform and witness swaps. The inventory team
reaches them because installations are global-readable, and can propose changes to them
(§4.4).

### 4.2 What each import may create

| Import | Creates (own workspace) | Proposes (review queue) | Never creates |
|---|---|---|---|
| EPIK8s configuration | Control Configuration, IOC Template, IOC, Control Device, Control Service, Control Network, Storage Mount, Access Point, Communication Path, Bus Segment | Positions and elements it infers (created as `Provisional`); Installations from `asset:` evidence; `acts on`, `composed of` and `served by` edges from name rules; Product Model links from template `asset:` | Physical Assets; Locations; Product Models; IT equipment, except under §4.3 |
| PBS matrix | Functional Elements and Positions (lifecycle *Planned*), Machine Module, RF Station, Section, Work Package, Procurement Record, Utility Requirement | Areas it names (to `inventory`) | Physical Assets (a planned component has no serial yet) |
| Inventory (Insight) | Physical Assets, Locations | Product Models (to `catalogue`); Installations when Insight records where a unit is | Positions |
| IT registry | IT Equipment, Equipment Ports, Address Records | — | Access Points (these are the beamline's) |
| Person (UI) | anything the workspace owns | facts on objects in other workspaces | — |

### 4.3 When inferred IT equipment may be created

The import may create a **provisional** IT equipment object in `it-infrastructure` only when
all of the following hold:

1. The run uses a service identity with the `it-contributor` role in `it-infrastructure`. The
   script's `--it-workspace` bypass is removed, and the same check applies through the API.
2. The FQDN is in a domain that IT has listed as *provisional-allowed*. Before a registry import
   exists, IT opts in per domain. After one exists, a domain is provisional-allowed only while
   that registry export is fresher than a set age. Absence from a fresh registry is evidence;
   absence from a stale one is not.
3. No identifier match exists. The FQDN, IP and MAC labels of all active IT records produce no
   candidate.
4. The DNS class prefix names equipment (`sc`, `sw`, `pl`/`vl`/`dl`, `pw`/`vw`/`dw`, `ns`), not
   an instrument or an `il` management interface.

Such an object is `record_status = Provisional` and keyed `PROV:HOST:<fqdn>`. It carries the
FQDN as a label and appears in IT's review queue. §10 describes how it is later merged into the
registry's record. Otherwise the Access Point keeps an inferred `endpoint_kind` and no box.

### 4.4 Visibility vs editing authority

These are four separate permissions:

| Permission | Rule |
|---|---|
| **Read** | owner workspace; or anyone, if the *object* is flagged global. Type globality shares the definition only (unchanged) |
| **Edit / retire** | members of the owner workspace with an editor role; importers only through their service identity in that workspace |
| **Link** | any workspace may create a relation *from its own object* to any object it can read, if the registry allows the relation to cross workspaces. The edge belongs to the source's workspace |
| **Propose** | any workspace may add an assertion with status `proposed` to any object it can read. The owner accepts or rejects it. This is how a beamline reports a serial number seen on a photograph of an inventory asset |

Two platform gaps must be closed for this to hold. `create_asset` must check that the type is
usable from the workspace (AS §8). Toggling a global type must not cascade the flag into
beamline child types.

### 4.5 Retiring stale objects

See §11. In short, each import run is a source revision. A fact the new revision no longer
states is *retracted*. An object with no remaining active support is *retired*, never deleted.
Retirement has a threshold that stops the run for approval when too much would retire.

---

## 5. Minimum viable type hierarchy (first production release)

### 5.1 Rules for the core

A type is in the core only if (a) a source that exists today fills it, or it is the join
without which the plane model fails, (b) a named owner maintains it, and (c) a query in
§8–§10 or in the root-cause walk needs it. Everything else is an **extension** with a trigger
(§5.4).

### 5.2 The core: 54 concrete types, 12 abstract

```
Item (abstract)                         description, argus_facility, argus_system, argus_subsystem,
│                                       argus_keywords, argus_lifecycle, argus_criticality, argus_responsible
│
├── Functional Element (abstract)       [beamline]  + argus_beamline, zone, argus_location (→ Location),
│   │                                   pbs_code…sequence_index, design_status, work_package (→ Work Package)
│   ├── Facility
│   ├── Section
│   ├── Machine Module                  composite
│   ├── RF Station                      composite
│   ├── Screen Station                  composite
│   ├── Mirror                          composite (its axes)
│   ├── Beam Element (abstract)         lattice_name, s_position, length, family, design_value, polarity
│   │   ├── Dipole  ├── Quadrupole  ├── Sextupole  ├── Corrector  ├── Solenoid
│   │   ├── Accelerating Structure      ├── RF Gun
│   │   └── Beam Position Monitor
│   ├── Motion Axis                     was Motor Axis (an Asset): axis_id, travel, resolution, velocity_max
│   └── Equipment Position              position_class (indexed), role, expected_product_model (→ Product Model)
│
├── Physical Asset (abstract)           [inventory | it-infrastructure]  argus_location (→ Location)
│   ├── Equipment (abstract)            manufacturer, model, serial (reserved), product_model (→ Product Model),
│   │   │                               inventory_number, condition, warranty_until, is_designated_spare
│   │   ├── Power Supply   ├── Magnet Assembly
│   │   ├── Ion Pump   ├── NEG Cartridge   ├── Turbo Pump   ├── Primary Pump   ├── Vacuum Gauge
│   │   ├── Camera   ├── Actuator   ├── Digitizer   ├── Low-Level RF Unit   ├── Modulator   ├── Chiller
│   │   ├── Other Equipment             equipment_class (indexed): the fallback, so no inventory row is refused
│   │   └── IT Equipment (abstract)     hostname, fqdn, firmware_version, management_url
│   │       ├── Serial Converter        n_serial_ports, serial_modes
│   │       ├── Switch                  n_ports, is_managed
│   │       └── Server                  is_virtual, os, role
│   └── Equipment Port                  port_number, port_kind, tcp_port, operating_mode
│
├── Catalog Item (abstract)             [catalogue]
│   ├── Product Model   └── Vendor
│
├── Control Item (abstract)             [beamline]
│   ├── Control Configuration           one per repository + path (revisions are Source Revisions)
│   ├── IOC Template   ├── IOC   ├── Control Device   ├── Control Service
│   ├── Control Network   ├── Storage Mount   ├── Access Point
│   ├── Communication Path              was Serial Line (the logical part)
│   └── Bus Segment                     was Serial Line (the physical medium)
│
├── IT Record (abstract)                [it-infrastructure]
│   └── Address Record
│
├── Record (abstract)
│   ├── Installation                    [beamline]  see §8
│   └── Engineering Record (abstract)   [beamline, private]
│       ├── Work Package   ├── Procurement Record   └── Utility Requirement
│
└── Location (abstract)                 [inventory]  parent_location (→ Location), access_rule
    ├── Building   ├── Area   └── Rack
```

Counts: 16 functional, 18 physical (14 equipment, 3 IT, plus Equipment Port), 2 catalogue,
10 control, 1 IT record, 4 records, 3 locations, which gives **54 concrete** and **12
abstract** types.

### 5.3 The `Engineered Item` fix (C1)

`Engineered Item` is removed. The breakdown keys (`pbs_*`, `component_id`, `module_code`,
`station_name`, `design_status`, `unit_count`, `sequence_index`, `work_package`) move to
**`Functional Element`**. A PBS row describes a *slot in the design*, and that slot is a
position. Consequences:

- `Equipment` carries no PBS keys. A spare pump on a shelf is an `Equipment` with no active
  Installation. `is_designated_spare` records *intent* (this unit is held as a spare), while
  *availability* is derived (no active Installation, lifecycle not Faulty or Scrapped). The
  `Spare Part` type is deferred as `Stock Item` (§5.4), for non-serialised stock counted by
  quantity. That removes all four spare representations of C12 except these two, and each of
  those has a distinct meaning.
- The 156 PBS components of physical types (C14) become `Equipment Position` objects with
  `position_class = "RF Load"` (and so on). When a load is delivered, it is an `Equipment` in
  `inventory`, installed at that position. Cost and procurement stay on the position, where the
  design put them. The delivered unit's purchase order can reference the same Procurement
  Record.
- `Machine System` objects are deferred. `argus_system` (the string shared with tickets and
  documents) is the one form of system membership in the core (§6.3).

**Equipment Position vs typed functional elements.** Use a typed subtype only where the element
has its own functional attributes (lattice physics, composites, motion ranges). Everything else
is one generic `Equipment Position` with an indexed `position_class`. This keeps the hierarchy
from mirroring every equipment type in the functional plane. The cost is that MCP search, which
matches on type name (AS §3), must also match `position_class`. That is a one-line change in
`mcp_tools.py` and is part of Phase 2.

### 5.4 Extensions: the rest of the target ontology

The deferred types stay designed (AS §4–§5 remain the reference). Each one enters production
when its trigger is met.

| Extension | Types (from the 122) | Trigger: source, owner, query |
|---|---|---|
| RF distribution | Waveguide Component tree (10 leaves), RF Amplifier | serialised RF components delivered into `inventory`; WP-04 owner; "which coupler serial is in station 3" |
| Diagnostics | Beam Charge Monitor, Faraday Cup, Wire Scanner, Emittance Meter, Spectrometer Station, Beam Loss / Arrival / Bunch Length Monitor, Diagnostic Element (abstract), Scintillator Screen, Optical Assembly | the WP-08 PBS matrix, or a diagnostics inventory |
| Magnets and undulators | Undulator, Plasma Module, Collimator, Beam Stopper, Vacuum Sector, Vacuum Valve, Vacuum Chamber | the WP-07 matrix; the lattice importer (AS §15) |
| Cabling | Cable Run tree | a cabling database or matrix |
| Network topology | Network Segment, Router, Media Converter, Network Device (abstract) | the IT registry, LLDP or port tables; IT owner |
| Consoles | Workstation, Computing Node (abstract) | Ansible inventory reader (IT §8.4) |
| Stores | Stock Item (was Spare Part), Storage Location | a stores or spares system and its owner |
| Safety | Interlock Unit, Radiation Monitor, Interlock Condition | PSS/MPS owners. Safety data needs its own review policy |
| Plant and electronics | I/O Module, PLC, Timing Module, Electronics Crate/Board, Instrument, Motion Controller, Cooling Circuit Component, Cryogenic Device, Laser System, Mechanical Support | per system, when an inventory or matrix lists them. Until then they go into `Other Equipment` with `equipment_class` |
| Engineering | Machine System (object), Section-level budgets | a system owner who maintains responsibilities |

The seeder gains tiers (`core`, `ext:<name>`). Extension types are seeded only on request.
Types already seeded in a workspace are kept but marked `metadata.tier` and hidden from creation
menus while they hold no objects.

---

## 6. Relation registry

### 6.1 Registry fields

One declaration per relation type, in code (`services/relation_registry.py`, which absorbs
`causal_model.SEMANTICS`). It is seeded into a `relation_types` table so the API and UI can read
it, and a test pins every `relate()` call site to it.

| Field | Meaning |
|---|---|
| `name` | canonical forward name, as stored in `relations.relation_type` |
| `inverse_name` | display name read from the target (`composed of` ↔ `component of`) |
| `source_types`, `target_types` | allowed schema names; `+` means including subtypes |
| `card_source` | maximum edges of this type *from* one source (`1` or `n`) |
| `card_target` | maximum edges of this type *into* one target (`1` = exclusive) |
| `unique` | always `(from, to, type)`, enforced by a DB constraint; the registry can add a scope such as "one active per source" |
| `acyclic`, `transitive` | graph constraints; queries may use the transitive closure |
| `cross_workspace` | may the target live in another workspace |
| `derivation` | `authored` (people), `imported`, `inferred`, or `derived` (computed from another authoritative form; read-only) |
| `derived_from` | for derived relations: the attribute key, intermediate object or path rule |
| `on_source_retire`, `on_target_retire` | `retire` the edge, `flag` for review, or `keep` |
| `on_merge` | always `repoint` to the survivor (§10) |
| `temporal` | `current` (history through the ledger) or `via Installation` (valid time) |
| `causal` | layer, flow and carried loss, as in `causal_model.py` today |
| `mode` | `warn` (log and report) or `enforce` (reject). All start in `warn` |

Two new columns on `relations` make this operable. `derivation` lets a sync job rebuild derived
edges without touching authored ones. `status` (`active`, `proposed`, `retired`) plus
`retired_at` let edges be proposed and retired without deletion. Add a unique constraint on
`(workspace_id, from_asset_uid, to_asset_uid, relation_type)`.

**Direction.** Existing verbs keep their stored direction, so re-imports do not churn. Direction
is never read from a name. The registry's `causal.flow` says which way a failure travels, as it
does today.

### 6.2 The registry, core relations

`FE` = Functional Element, `EP` = Equipment Position, `Eq` = Equipment.

| name | inverse | source → target | card (src/tgt) | derivation | lifecycle | causal |
|---|---|---|---|---|---|---|
| **part of** | contains | FE+ → Facility, Section | 1 / n; acyclic, transitive | imported, authored | target retired → flag | membership, weak |
| **composed of** | component of | composite FE (Machine Module, RF Station, Screen Station, Mirror) → FE+ | n / **1** (exclusive); acyclic | imported, inferred (proposed), authored | source retired → flag parts; target retired → retire edge | composition, reverse, degradation |
| **served by** | serves | FE+ → FE+ | n / n | imported, inferred, authored | retire with either end | function, reverse, function |
| **realized by** | realizes | FE+ → Eq+ | 1 per role / 1 (unless multi-position) | **derived** from active Installations | follows Installation | function, reverse, function |
| **installed at** | has installation | Installation → FE+ | 1 / n | authored, imported, proposed | position retired → flag | none |
| **installation of** | installations | Installation → Eq+ | 1 / n | authored, imported, proposed | asset merged → repoint | none |
| **acts on** | acted on by | Control Device, IOC* → FE+; Eq+ only when the asset has no position | n / n | inferred, authored (review), imported where stated | retire with source | control, forward |
| **drives** | driven by | IOC → Eq+ | n / n | **derived**: IOC ← provided by ← device → acts on → FE → realized by → Eq | recomputed | control, forward |
| **implemented by** | implements | Access Point → IT Equipment+, EP | 1 / n; cross-workspace | resolved, inferred, authored | target merged → repoint; AP retired → retire | control, reverse |
| **provided by** | provides | Control Device → IOC | 1 / n | imported | retire with source | control, reverse |
| **declared in** | declares | Control Item+ → Control Configuration | 1 / n | imported | — | none |
| **templated from** | template of | IOC → IOC Template | 1 / n | imported | — | none |
| **deployed on** | hosts | IOC, Control Service → Facility | 1 / n | imported | — | none |
| **configures** | configured by | Control Configuration → Facility | 1 / n | imported | — | none |
| **on network** | network of | IOC, Access Point → Control Network | n / n | imported | — | control, reverse |
| **mounts** | mounted by | IOC, Control Service → Storage Mount | n / n | imported | — | control, reverse |
| **runs on** | runs | IOC → Server, EP, Eq+ | 1 / n; cross-workspace | imported, resolved | — | control, reverse |
| **uses path** | used by | IOC → Communication Path | n / 1 | imported | retire with either | control, reverse |
| **on path** | carries | Control Device → Communication Path | 1 / n | imported | retire with either | control, reverse |
| **enters at** | entry of | Communication Path → Access Point | 1 / n | imported | retire with source | control, reverse |
| **continues on** | continuation of | Communication Path → Bus Segment | 1 / n | imported | retire with source | control, reverse |
| **attached to** | attachment | Bus Segment → Equipment Port | 1 / 1; cross-workspace | resolved, authored (inferred port → proposed) | port retired → flag | control, reverse |
| **port of** | ports | Equipment Port → Eq+ | 1 / n | imported (registry) | **retire with target** | control, reverse |
| **traverses** | traversed by | Communication Path, Bus Segment → Equipment Port, Switch, (ext: Cable Run) | n / n; unordered series | authored, imported (cabling) | retire with target → flag path | control, reverse |
| **reached through** | reaches | Control Device → Access Point | 1 / n | **derived**: on path → enters at | recomputed | control, reverse |
| **connects to** | connected from | IOC → Access Point | n / n | **derived**: uses path → enters at | recomputed | control, reverse |
| **enabled by** | enables | Control Device, IOC → Control Device | n / n | imported | — | interlock, reverse, permit |
| **powers** | powered by | EP, FE+ → FE+ | n / n | inferred, authored | — | power, forward, function |
| **cools** | cooled by | EP → FE+ | n / n | inferred, authored | — | cooling, forward, function |
| **triggers** / **timed by** | as today | EP → FE+ / EP → EP | n / n | inferred | — | timing |
| **upstream of** | downstream of | Beam Element → Beam Element | n / n; acyclic | imported (lattice) | — | beam, forward |
| **measures** | measured by | Beam Position Monitor, Screen Station → Beam Element, Section | n / n | authored | — | none |
| **instance of** | instances | Eq+ → Product Model | 1 / n; cross-workspace | **derived** from `product_model` | recomputed | none |
| **located in** | contains (place) | Physical Asset+, FE+ → Location+ | 1 / n; cross-workspace | **derived** from `argus_location` | recomputed | environment, reverse |
| **within** | contains (place) | Location → Location | 1 / n; acyclic | **derived** from `parent_location` | recomputed | environment |
| **supplied by** | supplies | Product Model → Vendor | 1 / n | **derived** from `vendor_ref` | recomputed | none |
| **assigned to** | assigned | FE+ → Work Package | 1 / n | **derived** from `work_package` | recomputed | none |
| **requires** | required by | FE+ → Utility Requirement | 1 / **1** | imported | **source retired → retire target** (owned dependent) | none |
| **procured under** | procures | FE+, Eq+ → Procurement Record | n / n | imported, authored | — | none |
| **described by** | describes | IT Equipment+ → Address Record | n / n; cross-workspace | resolved, imported | — | none |

`IOC*`: only for an IOC that lists no devices and is itself the unit (AS §9.5, the "modulator
IOC"). **Deprecated verbs**, migrated in §12: `replaced` (derived from Installation
succession), `carried by` (→ `traverses`), `on line` (→ `on path`), `port of` from a Serial Line
(→ `enters at`), and `spare for` (deferred with Stock Item).

### 6.3 The six relations that need care

**`part of` vs `composed of`.** These answer different questions and must not overlap.

- `part of` is the **breakdown tree**. Each element has one parent (Facility or Section), the
  tree is acyclic, and the closure answers "what is in the injector". It never points at a
  Location (C3: use `argus_location` → `located in`) or at a Machine Module.
- `composed of` is **assembly**. The part is exclusive to one composite (`card_target = 1`),
  and a composite without its part is degraded. A Machine Module is an assembly, so the PBS
  `MODULES` column produces `composed of`, not `part of`.
- **Mutual exclusion.** A component has no `part of` of its own. It inherits its composite's
  membership. So "what is in the injector" returns the screen station, not its camera
  position, until the query expands composites. This is the behaviour AS §4 asked for, and it
  is now enforced.
- **Shared providers are not parts** (C4). A modulator feeding two stations is `served by` from
  each station (or `powers`, when the dependency is electrical). Exclusivity rejects it as a
  component of two composites. The PBS importer reports such rows instead of writing them.
- **Physical containment** (a board in a crate) is not composition in the functional plane. In
  the core it is not modelled. When electronics extensions arrive, it is an Installation of the
  board at a slot position in the crate.

**`realized by`** becomes **derived**. It holds exactly when an Installation with status
`Active` and an interval covering *now* links the asset to the position. It is materialized
(`derivation = derived`) so the graph walk and the causal model keep working unchanged. Nobody
edits it; you edit the Installation. C5 and C6 are resolved: the supply is installed at the
supply position, which `powers` the quadrupole position, which is realized by the magnet
assembly installed there.

**`acts on`** points at **positions**. The control channel acts on whatever is installed at
GUNSIP01, and the current asset follows through `realized by`. Its polymorphism (AS §4) is no
longer a design goal. It survives only for equipment with no position (lab and IT equipment),
and the registry reports those cases.

**`drives`** is **derived**. The `asset:` URL on an IOC or device (AS §9.2) is **evidence for
an Installation** (§8.4), not an edge. That resolves C13: one URL on a multi-device IOC
produces a candidate list, not a wrong edge.

**`implemented by`** has **one active target per Access Point** and may cross workspaces. For
an Ethernet-native instrument (BTF's Modbus TCP supplies), the target is the instrument's
**position**. The IP belongs to the place in the machine, and the unit behind it follows the
Installation. For a converter or a host, the target is site IT equipment. Swapping an IT box
behind an unchanged hostname is a service operation: it retires one assertion, proposes the
next, and re-attaches Bus Segments to ports of the same number. History comes from the ledger
(§7.5).

### 6.4 One authoritative form per link

| Form | Authoritative when | Other forms |
|---|---|---|
| **(a) reference attribute** | the link is N:1, the target is a master or classifier record (product model, location, vendor, work package), and it is edited on the object's form | relation **derived** by the sync job, keyed by `attribute.relationType` (a new attribute property naming the registry entry), **add and remove** |
| **(b) relation** | many-to-many, part of a tree or topology, or the link needs its own provenance or confirmation (anything inferred) | no mirror attribute. A form that needs it shows a computed, read-only field |
| **(c) intermediate object** | the link has attributes or valid time | relations to and from it are authoritative; shortcut relations are **derived** |

Applied:

| Semantic link | Authoritative | Derived | Retired |
|---|---|---|---|
| asset → product | `Equipment.product_model` (a) | `instance of` | — ; `manufacturer` and `model` stay as *observed* strings (photo identification, as found), and a mismatch with the product model is a report item |
| asset or position → place | `argus_location` (a) | `located in` | `part of` → Area |
| place → place | `Location.parent_location` (a) | `within` | — |
| element → work package | `work_package` (a) | `assigned to` | `wbs_code` becomes a read-only projection |
| product → vendor | `Product Model.vendor_ref` (a) | `supplied by` | `vendor` string kept as *as found* |
| element → section / facility | `part of` (b) | — | `module_code`, `station_name` and `pbs_area` stay as **source identifiers**, read-only; the importer resolves the relation from them, and divergence is reported, not silently fixed |
| system membership | `argus_system` string | — | `Machine System` objects deferred |
| position ↔ asset | `Installation` (c) | `realized by`, `drives` | `installed_on`, `removed_on`, `replaced` |
| device → access point | `Communication Path` (c) | `reached through`, `connects to` | `Serial Line` |
| spare stock | Stock Item (extension) | — | `Spare Part`, `spare_for`, `spare for`; `is_spare` becomes `is_designated_spare` |

**Sync semantics.** The sync job replaces `relink_workspace`'s edge step. For each reference
attribute that has a `relationType`, it computes the desired derived edges and diffs them
against edges with `derivation = derived` and the same source attribute. It then adds or
retires edges and **never touches authored edges**. Edges are labelled with the registry
name, not the attribute's display name, so renaming the attribute "Instance of" no longer
renames its edges. It runs on write, and in bulk after imports.

---

## 7. Provenance

### 7.1 Source Revision

One row per input that one import run reads:

```
source_revision
  id
  source_kind        epik8s | pbs | insight | it-registry | ansible | lattice | photo | manual-batch
  source_locator     "https://baltig.infn.it/epik8s/epik8-sparc.git#deploy/values.yaml"
                     | "docs/2026-06-11 - EuPRAXIA PBS_ver2.xlsx" | "insight:schema=44"
  revision           git commit SHA (resolved at fetch, never a branch name) | file SHA-256 | export timestamp
  content_hash       SHA-256 of the bytes read
  observed_at        commit time / file mtime / export time: when the source said it
  retrieved_at       when the hub read it
  importer           "epik8s_import@3.0" (code version)
  import_job_uid     → import_jobs
```

If a run finds the same `content_hash` and the same `importer` as the last revision of its
locator, it is a no-op. That is idempotency by construction.

### 7.2 Assertion

One row per fact per source:

```
assertion
  id
  subject_uid          the object the fact is about
  predicate            "exists" | "attr:<key>" | "rel:<relation_type>"
  value                JSONB: the attribute value, or {"to": <uid>} for a relation
  method               stated | resolved | inferred | manual | derived
  rule                 "epik8s.device@3" | "infer.vac.sip@2" | "resolve.jira_object_id@1" | null
  source_revision_id   null for manual
  asserting_workspace  who asserted it (a proposal across workspaces is an assertion like any other)
  evidence             JSONB: {"path": "epicsConfiguration.iocs.vac-gunvpc.devices[1]",
                                "excerpt": "{name: GUNSIP01, channel: 146}",
                                "matched_on": "name pattern SIP", …}
  confidence           0..1 for resolved and inferred; null for stated and manual
  status               proposed | accepted | confirmed | rejected | retracted | superseded
  first_seen_revision, last_seen_revision, first_seen_at, last_seen_at
  decided_by, decided_at, decision_note
  fingerprint          hash(source_kind, rule, subject key, predicate, value): suppresses re-proposal after rejection
```

**Method** and **status** are separate axes, and together they preserve the four-way distinction
the notes rely on:

| The notes say | Here |
|---|---|
| stated | `method = stated` (the source says it in as many words) |
| resolved | `method = resolved` (joined to another record by an identifier: objectId, hostname, IP) |
| inferred | `method = inferred` (a rule read it from a name or a convention) |
| manually confirmed | `status = confirmed`, `decided_by` set, whatever the method. A person typing a value is `method = manual, status = confirmed` |

Statuses: **proposed** (in the review queue, not in effective state); **accepted** (in
effective state, not signed by a person); **confirmed** (signed); **rejected** (never applied,
and its fingerprint suppresses re-proposal); **retracted** (the source no longer states it);
**superseded** (the same source now states a different value).

Each rule declares its default. Stated and resolved-by-strong-identifier facts are `accepted`.
Name-rule inferences that today create objects (pumps, supplies, magnets) are `accepted`, which
keeps current behaviour: the objects exist and are visibly unconfirmed. Composition by name
pairing (the camera of a screen) and anything with `confidence < 0.8` is `proposed`, as AS
§11.4 argued.

### 7.3 Effective state

`assets.attributes` and active `relations` rows are the **projection** of the ledger. A single
service, the FactWriter, computes them. No importer writes attributes directly again. For each
`(subject, predicate)`:

1. a `confirmed` assertion wins; the newest confirmed one if there are several;
2. otherwise an `accepted` assertion from the **authoritative source for that predicate** (§4.2:
   Insight for `serial`, the configuration for `pv`, the PBS for `pbs_code`);
3. otherwise any other `accepted` stated or resolved assertion, then inferred;
4. ties break by `observed_at`.

When two accepted assertions at the top applicable tier disagree, the object is flagged with a
**conflict** and goes to the review queue. The projection keeps the previous value until
someone decides. This replaces both `upsert` behaviours (C9). A stated re-import no longer
erases a manual edit, because the manual edit is `confirmed` and outranks it. An inferred value
still fills only what is empty, because inferred ranks last.

### 7.4 What replaces the keyword

- `argus_keywords: inferred` is removed by the migration. `argus_keywords` returns to users.
- Every object view and the API show a **provenance summary**: sources, methods, and the count
  of unconfirmed and conflicting facts. Filters include "provisional records", "has
  unconfirmed inferred facts" and "conflicts". These are ledger queries, not keywords.
- `argus_source` and `argus_source_ref` remain for one release as read-only projections (the
  source of the object's `exists` assertion with the earliest `first_seen`) and are then
  dropped.

### 7.5 Examples

A device, stated:
```json
{"subject": "SPARC:DEV:vac-gunvpc:GUNSIP01", "predicate": "attr:channel", "value": 146,
 "method": "stated", "rule": "epik8s.device@3", "status": "accepted",
 "source_revision": "epik8-sparc@6bca015:deploy/values.yaml",
 "evidence": {"path": "epicsConfiguration.iocs.vac-gunvpc.devices[1]"}}
```

A position, inferred:
```json
{"subject": "SPARC:POS:GUNSIP01", "predicate": "exists", "value": {"type": "Equipment Position",
 "position_class": "Ion Pump"}, "method": "inferred", "rule": "infer.vac.sip@2", "confidence": 0.9,
 "status": "accepted", "evidence": {"devgroup": "vac", "name_token": "SIP", "template": "agilent-vac"}}
```

An Access Point's implementation, resolved and later confirmed:
```json
{"subject": "NET:sparc:SCSPARCSIPMXA001", "predicate": "rel:implemented by",
 "value": {"to": "it:LNFMAC-00417"}, "method": "resolved", "rule": "resolve.fqdn@1",
 "confidence": 0.95, "status": "confirmed", "decided_by": "…", "decided_at": "2026-10-02T09:12Z"}
```

`implemented by` history is read from this record's `first_seen_at` / `last_seen_at` and its
`superseded` successors. That is **record time** (when a source said it). It is not valid time.
Only Installations carry valid time (§8.2).

---

## 8. Installation history

### 8.1 The Installation object

`Installation` (a `Record`) is owned by the workspace that owns the position and flagged global.

| key | type | notes |
|---|---|---|
| `valid_from` | datetime, nullable | null means "before records began" (a back-filled installation) |
| `valid_from_precision` | enum | Exact, Day, Month, Year, Unknown |
| `valid_until` | datetime, nullable | null means still installed |
| `installation_status` | enum | Proposed, Planned, Active, Ended, Rejected |
| `role` | string, indexed | disambiguates positions with several slots, and multi-position units (a Libera channel `A`) |
| `removal_reason` | enum | Failure, Maintenance, Upgrade, Relocation, Decommissioning, Unknown |
| `work_reference` | string | ticket or work-order key; the ticket link itself is the existing `asset_tickets` row |
| `evidence_summary` | text, read-only | projection of the ledger's evidence for `exists` |
| `confirmed_by`, `confirmed_at` | user, datetime, read-only | projection of the ledger's confirmation |

Relations: `installation of` → Equipment (exactly one), `installed at` → Functional Element
(exactly one). Key: `<position key>@<asset key>#<n>`, for example
`SPARC:POS:GUNSIP01@INV:ICP-23-0032#1`.

**Service-level constraints**, since the platform cannot express them:

- no two `Active` installations at the same `(position, role)` with overlapping intervals;
- no two `Active` installations of the same asset with overlapping intervals, unless the
  asset's type is flagged `multi_position` (a Digitizer serving several BPMs), in which case
  `role` is required;
- `valid_until ≥ valid_from`; setting `valid_until` in the past moves the status to `Ended`;
- the asset's type should be compatible with the position's `position_class` or typed element.
  A mismatch is a warning, not an error, because it is sometimes a genuine substitute.

### 8.2 Two time axes

- **Valid time**: when the unit was physically there. Only Installation carries it.
- **Record time**: when a source or a person said so. The ledger holds it for every fact.

A back-filled Installation for a pump that has been in place for years has `valid_from = null`,
`precision = Unknown`, and record time = today. The model states what is known without
inventing a date.

### 8.3 Queries

Current state goes through derived `realized by`:
```sql
SELECT a.* FROM relations r JOIN assets a ON a.uid = r.to_asset_uid
WHERE r.from_asset_uid = :position AND r.relation_type = 'realized by' AND r.status = 'active';
```

Historical state goes through a view over Installation objects (`v_installation`: uid,
position_uid, asset_uid, role, valid_from, valid_until, status), maintained from the object and
its two relations:
```sql
-- what was at GUNSIP01 on 2025-03-03
SELECT asset_uid FROM v_installation
WHERE position_uid = :pos AND status IN ('Active','Ended')
  AND coalesce(valid_from, '-infinity') <= :t AND :t < coalesce(valid_until, 'infinity');

-- where has serial 84321 been (chronic-failure view, joined with asset_tickets)
SELECT * FROM v_installation WHERE asset_uid = :asset ORDER BY valid_from NULLS FIRST;

-- which positions were served by a unit that later failed
SELECT i.position_uid FROM v_installation i
JOIN v_installation later ON later.asset_uid = i.asset_uid AND later.removal_reason = 'Failure';
```

### 8.4 Where installations come from

| Evidence | Proposal |
|---|---|
| a person records a swap (UI "replace unit" action: end one, start one, one ticket) | Active, confirmed |
| `asset:` Insight URL on an IOC or device → `asset_labels` `jiraObjectId` → inventory asset | Proposed, at the positions the IOC's devices act on. A single compatible position gives `confidence` 0.9; several give a candidate list |
| serial or inventory number in an IOC name (`ocem-dvl644-ser23001`, AS §11.3) | Proposed, if an inventory asset carries that serial or number |
| Insight records a unit's location as a rack, and exactly one compatible position in that rack is empty | Proposed, low confidence |
| PBS delivery or Procurement Record references a delivered serial | Planned, then Active on commissioning |

The configuration never *states* an installation, so config-derived installations are always
proposals.

---

## 9. Connectivity

### 9.1 The four things a "Serial Line" was

```
IOC vac-gunvpc ─uses path─▶ Communication Path  SPARC:PATH:vac-gunvpc:scsparcsipmxa001:4003
                             protocol Modbus RTU · transport Ethernet→Serial · tcp_port 4003
Control Device GUNSIP01 ─on path─┘   │ enters at                        │ continues on
                                     ▼                                  ▼
                   Access Point NET:sparc:SCSPARCSIPMXA001      Bus Segment SPARC:SEG:scsparcsipmxa001:4003
                                     │ implemented by           medium RS-485 · topology multi-drop
                                     ▼                          baud 9600 · framing 8N1
                   Serial Converter (it) Moxa NPort 5650-16     serial_port_hint 3 (inferred, 4000+N)
                                     ▲ port of                          │ attached to (once the box is known)
                                     └────────── Equipment Port P3 ◄────┘   port_kind RS-485-2w · tcp_port 4003
Communication Path ─traverses─▶ Switch port, Ethernet cable…   (added by IT or from a cabling source)
```

| Object | Plane / owner | Is | Keyed |
|---|---|---|---|
| **Communication Path** | control / beamline | the end-to-end logical path from one IOC to one endpoint, with protocol and transport | `<FAC>:PATH:<ioc>:<endpoint>[:<port>]` |
| **Access Point** (unchanged) | control / beamline | the network entry: address and port as the configuration names them | as today |
| **Bus Segment** | control / beamline | the physical medium downstream of the entry, shared by the devices on it | `<FAC>:SEG:<endpoint>:<port>` |
| **Equipment Port** | physical / the box's owner | one physical port of one box | `<asset key>:P<n>` |
| hop | physical | a switch port (an Equipment Port of a Switch) or, in the cabling extension, a Cable Run | — |

Two IOCs on one `endpoint:port` produce **two paths and one segment**, which is the
distinction the old model could not make. Where the configuration gives `line_kind` (IT
§4.1), it becomes the segment's `topology`.

### 9.2 Attributes

- **Communication Path**: `protocol` (indexed: Modbus RTU, Modbus TCP, StreamDevice ASCII,
  SCPI, GigE Vision, CANopen, IEEE-488, EtherCAT, vendor TCP…), `transport` (enum: Ethernet
  native, Ethernet→Serial, Ethernet→GPIB, Ethernet→CAN, Local bus, Fieldbus), `endpoint`
  (stated `host:port`), `tcp_port`.
- **Bus Segment**: `medium` (enum: RS-232, RS-422, RS-485 2-wire, RS-485 4-wire, GPIB, CAN,
  EtherCAT, Other), `topology` (Point-to-point, Multi-drop, Daisy chain, Line, Ring), `baud` or
  `bitrate`, `framing`, `termination`, `serial_port_hint` (inferred, never used as a link).
- **Equipment Port**: `port_number`, `port_kind`, `tcp_port` (as configured on the box),
  `operating_mode` (Real COM, TCP server, RFC 2217…).

Line parameters (baud, framing) live **only** on the Bus Segment, because both ends must agree
on them. The port holds only the box's mapping and mode.

### 9.3 Generalization

| Case | Path transport | Entry (Access Point) | Downstream | Device address |
|---|---|---|---|---|
| Moxa + RS-485 bus (SPARC vacuum) | Ethernet→Serial | converter host:port | Bus Segment RS-485 → converter Equipment Port | `channel` / `id` on Control Device |
| Ethernet-native Modbus TCP (BTF, 28 devices) | Ethernet native | the device's IP:502, `implemented by` its **position** | none | Modbus unit id on Control Device |
| GigE camera | Ethernet native (GigE Vision) | camera IP | none | — |
| Ethernet–GPIB gateway | Ethernet→GPIB | gateway host | Bus Segment GPIB (daisy chain) → gateway's GPIB port | GPIB address on Control Device |
| GPIB card in the IOC host | Local bus | none; IOC `runs on` the host | Bus Segment GPIB → host's card port | GPIB address |
| CAN via gateway or card | Ethernet→CAN / Local bus | gateway host / none | Bus Segment CAN (bitrate, termination) | node id |
| EtherCAT or other fieldbus | Fieldbus | none | Bus Segment EtherCAT (line/ring) → master port on host | slave position |
| IOC on the instrument (`host:` over ssh) | Local bus | none; IOC `runs on` the instrument's position | none | — |
| Soft or simulated IOC | no path | — | — | — |

### 9.4 Hops and impact

`traverses` holds an **unordered** set of hops. Every hop is in series, so any one failing cuts
the path. This is all impact and root-cause analysis need. Order would need an intermediate
`Path Hop` object (§1.4). It is deferred until a troubleshooting query needs it. Switch ports
and cables are added by IT or from a cabling source, never inferred from a configuration.

The IT §4.3 case now resolves at three levels:

- **Box** (`scsparcsipmxa001`) down: 4 paths, 15 devices.
- **Port 3** down (Equipment Port P3, or its segment): 1 path, 4 devices.
- **Switch port** upstream: every path that traverses it, across beamlines.

---

## 10. Identity reconciliation

### 10.1 Where duplicates come from, and how to prevent them

The biggest source of duplicates is removed at the root. **Configuration imports create
positions, not physical assets** (§4.2). The inventory's pump and the configuration's GUNSIP01
are different kinds of object, joined by an Installation, so they cannot be duplicates. What
remains are provisional records created under §4.3 or by hand, and records that two sources
create for the same thing (for example, an Area that both the PBS and the inventory name).

Prevention:

1. **Strong identifier labels.** `asset_labels` rows with `namespace` (`serial:<manufacturer>`,
   `insight`, `mac`, `fqdn`, `inventory`) and a partial unique index over active records
   `(namespace, type, value)`. A second active record with the same serial or MAC cannot exist.
2. **Alias lookup in every importer**: key, then alias label, then create. A merged record's
   old key resolves to the survivor, so a re-import never recreates it.
3. **Provisional records age out**: flagged after 30 days in review; excluded from inventory
   counts throughout.

### 10.2 Workflow

```
            ┌──────────── candidates computed on create and on every source update ───────────┐
            ▼                                                                                  │
 Provisional ──confirm match──▶ Merged (tombstone) ──▶ survivor Active, with aliases           │
     │        ──reject candidate──▶ stays Provisional; rejection remembered ───────────────────┘
     │        ──confirm as new────▶ Active (moved to the owning workspace if created elsewhere)
     └─────── ──discard──────────▶ Retired; rule fingerprint rejected, so no re-inference
```

**Candidates** (`identity_candidate`: provisional_uid, candidate_uid, score, evidence, status,
decided_by, decided_at). Blocking and scoring:

| Evidence | Strength | Policy |
|---|---|---|
| Insight objectId, inventory number, serial + manufacturer, MAC | strong | auto-merge allowed if it is the only candidate and the types are compatible; otherwise propose |
| FQDN (IT) | strong for the *address record*, medium for the box (hostnames survive box swaps) | propose; auto-merge only into the registry's Address Record |
| IP only | weak (DHCP, reuse) | propose |
| type-compatible + same location + name similarity | weak | propose |

**Merge** (one transaction, logged in `asset_history` on both records):

1. Choose the survivor: the record in the owning workspace, normally the authoritative source's.
2. Re-point every relation, ticket link, document relation, label, comment and attachment from
   the loser to the survivor. The unique constraint deduplicates.
3. Re-assert the loser's attribute values on the survivor as **proposed** assertions, never
   silent overwrites. A value is accepted automatically only where the survivor has none and
   the predicate's authority allows it.
4. Add the loser's key and uid to the survivor as `former_key` / `former_uid` labels.
5. Set the loser to `record_status = Merged`, `merged_into_uid = survivor`. Keep it as a
   tombstone (its key stays reserved, its URL redirects). The ledger keeps its facts, so an
   administrator can undo the merge.

Rejected candidates are stored and never re-proposed for the same pair unless new strong
evidence appears.

---

## 11. Import lifecycle: idempotence and retirement

Each run:

1. **Register** a Source Revision. Resolve the commit SHA at fetch time. If the hash and
   importer version are unchanged, stop.
2. **Parse to facts.** Turn the input into a fact set (objects, attributes, relations, each with
   rule and evidence), as a pure function. `element_inference.py` already works this way; the
   configuration walk is refactored to match.
3. **Plan** against this locator's previous revision: new, unchanged (bump `last_seen`),
   changed (supersede), missing (retract). Drop facts whose fingerprint was rejected.
4. **Guard.** If more than a set share would retire (default 10 % of this source's objects),
   or if any object with tickets or documents would retire, the run stops in *needs approval*
   and shows the plan. This guard would have caught the list-vs-mapping bug (AS §14.1), in
   which a production file silently read as zero IOCs.
5. **Apply** through the FactWriter (§7.3).
6. **Retire.** An object whose `exists` assertions are all retracted or rejected, and that has
   no confirmed or other-source support, becomes `Retired`. Its derived edges are retired, and
   edges with `on_source_retire = retire` follow. A retired **position** with an `Active`
   Installation is flagged, not ended. The device may have left the configuration while the
   hardware is still in the tunnel.
7. **Report**: counts per status, conflicts, candidates, proposals.

`merge_strategy = remove_all_before` is removed (C11). `override` is replaced by the precedence
rules in §7.3. Retired records are hidden from default views and remain reachable from their
tickets and documents.

---

## 12. Migration implications

### 12.1 Platform (Alembic)

| Change | Notes |
|---|---|
| `source_revisions`, `assertions`, `identity_candidates`, `relation_types` tables | new |
| `assets.record_status` (default `Active`), `assets.merged_into_uid` | backfill: every object `Active` |
| `relations.derivation`, `.status`, `.retired_at`; unique `(workspace_id, from, to, type)` | deduplicate first (the importers deduplicate in code, `POST /v1/relations` does not); backfill `derivation` from the relation type (registry) and `imported` for importer-made rows |
| `asset_labels` partial unique index on active strong identifiers | report collisions before enforcing |
| attribute definition property `relationType` | on every reference attribute |

### 12.2 Code

| File | Change |
|---|---|
| `services/relation_registry.py` (new) | registry; `causal_model.py` reads semantics from it |
| `services/fact_writer.py` (new) | the only writer of attributes and relations for importers; precedence, conflicts, ledger |
| `services/epik8s_import.py` | `upsert` / `upsert_inferred` → FactWriter (fixes C9); `_fetch` returns the commit SHA; `access_point()` always creates the Access Point and relates `implemented by` (fixes C8); Serial Lines → Paths and Segments; positions instead of assets; the §4.3 IT policy; remove `remove_all_before`; retirement |
| `services/element_inference.py` | rules unchanged; the output type changes to position and element; every rule gets an id and a version; screen–camera pairing emits a proposal |
| `services/pbs_import.py` | components of physical types → `Equipment Position`; `part of` → Area becomes `argus_location`; module → `composed of` from the module; station exclusivity check with `served by` for shared providers; `wbs_code` → `work_package` |
| `services/integrity.py` (`relink_workspace`) | edges named by registry, add-and-retire derived edges only |
| `routers/assets.py` | relation create/delete validated by registry (warn, then enforce); `create_asset` checks the type is usable from the workspace |
| `services/asset_types.py` | the §5.2 hierarchy, tiers, removal of `Engineered Item` as an in-place re-parent (the seeder already follows changed parents) |
| `services/network_resolve.py` | read visible global objects across workspaces; match through labels and aliases |
| `services/root_cause.py`, `knowledge_graph.py` | walk only `status = active` edges, optionally `proposed` at a lower weight; skip `Retired` and `Merged` records |
| `services/mcp_tools.py` | type search also matches `position_class` and `equipment_class` |
| `services/jira_import.py` | inventory objects into `inventory`; identifiers as labels; adopt catalogue types by name (IT §8.5) |
| `scripts/import_epik8s.py` | drop the unchecked `--it-workspace` path in favour of a service identity |

### 12.3 Data

Run per workspace, with a dry-run report first. The figures below are the ones the notes
publish (AS §9.5, IT §0).

| Current | Becomes |
|---|---|
| 492 inferred "assets" (SPARC 249, BTF 62, EuAPS 94, ELI 87), keyed `FAC:AST:<ioc>:<chan>` | `Equipment Position` (`position_class` = old type) or `Motion Axis`, keyed `FAC:POS:<tag>`, `record_status = Provisional`; old key as a `former_key` label; tickets and documents carried over (they are about the channel name, which is the position) |
| `Power Supply --powers--> Quadrupole` | supply **position** `powers` the Quadrupole (same verb) |
| `Element --realized by--> inferred Digitizer` | BPM `served by` the electronics position (shared Liberas are not exclusive) |
| `Screen Station / Mirror --composed of--> asset` | `composed of` the actuator, camera or axis **position**; camera pairings re-asserted as `proposed` |
| `Control Device --acts on--> asset`, `IOC --drives--> asset` | `acts on` the position; `drives` dropped (derived) |
| 104 Serial Lines, `on line`, `port of`, `carried by` | 104 Communication Paths + Bus Segments; `on path`, `enters at`, `continues on`; `carried by` → converter dropped (redundant with `enters at` → `implemented by`) |
| 30 inferred IT objects (`HOST:<fqdn>`) | `Provisional`; FQDN label; candidates computed once the registry is imported |
| Access Points that are really equipment (`access_points_linked`) | a proper Access Point + `implemented by` |
| 156 PBS components of physical types (Assets) | `Equipment Position`, lifecycle Planned; Procurement and Utility edges unchanged |
| 383 PBS `part of` | → Area: `argus_location`; → module: `composed of` (module as source); → Section: kept |
| `argus_keywords: inferred`, `argus_source`, `argus_source_ref`, `argus_provenance`, `endpoint_kind_source` | ledger assertions with `source_revision` = "legacy import, revision unknown", `method` from the marker; markers removed |
| `installed_on` / `removed_on` / `is_spare` with values | an Installation where a position exists, otherwise an `asset_history` note; `is_spare` → `is_designated_spare` |
| types outside the core with zero objects | tier `ext:*`, hidden; with objects: kept and listed in the migration report |

The legacy ledger rows are honest about what is not known: "imported before provenance
existed; the revision is unknown". The first re-import of each source then supersedes them with
real revisions.

---

## 13. Implementation plan

Ordered by harm: data loss first, then trust, then duplicates, then new capability.

| Phase | Work | Exit criterion |
|---|---|---|
| **0. Stop the bleeding** (small, now) | stated `upsert` merges instead of replacing, keeping values edited since the last import; remove `remove_all_before`; resolve the commit SHA into `argus_source_ref`; permission check on `--it-workspace`; `create_asset` type check; fix the C15 figures in both notes | re-import leaves a hand-edited IOC description intact (test) |
| **1. Ledger and registry** | tables and columns (§12.1); FactWriter; registry in `warn` mode with a report of every violating edge in each workspace; legacy provenance backfill | every importer writes through the FactWriter; the registry report is empty or triaged |
| **2. Positions and Installations** | core hierarchy and tiers; data migration of inferred assets and PBS components; Installation type, constraints, `v_installation`, derived `realized by`; "replace unit" action; MCP `position_class` search | "what was at GUNSIP01 on date t" and "where has serial s been" answered by tests over migrated data |
| **3. Attribute/relation sync** | `relationType` on references; add-and-retire sync; derived `instance of`, `located in`, `within`, `assigned to`, `supplied by`; PBS `part of` corrections | no reference attribute and derived edge disagree (integrity report) |
| **4. Reconciliation and inventory** | labels as strong identifiers; candidates; review queue UI (proposals, conflicts, candidates, retirements); Insight import into `inventory`; `asset:` resolution → Installation proposals; §4.3 IT policy | provisional → merged round trip with alias resolution on re-import (test); SPARC `asset:` URLs produce proposals |
| **5. Connectivity** | Paths, Segments, Ports; migration of Serial Lines; IT registry ports; derived `reached through` / `connects to`; root-cause walk through ports | the IT §4.3 box / port / switch impact figures reproduced from the new objects |
| **6. Retirement** | plan/guard/retire (§11); registry `enforce` mode | a re-import with a device removed retires exactly that device; a broken parse stops at the guard |
| **7. Extensions** | per §5.4, each when its trigger is met | owner named, source importer written, query in the test suite |

Phases 2 and 3 can overlap. Phase 5 depends on 1 but not on 4.

---

## 14. Decisions needed from stakeholders

1. **System of record for physical assets.** Does the hub mirror Jira Insight (read-only
   assets, with Installations held in the hub), or does it become the record? This decides
   whether Installations are ever written back.
2. **Inventory workspace staffing.** Is it one `inventory` workspace for non-IT equipment and a
   separate `it-infrastructure`, or one site workspace? Who holds the editor role in each?
3. **Review owners.** Who confirms inferred facts and candidate matches per domain (vacuum,
   magnets, diagnostics, IT)? Without named reviewers, the proposal queues grow and nobody
   empties them.
4. **Auto-merge policy.** Is a single strong-identifier match (serial + manufacturer, Insight
   objectId, MAC) allowed to merge without a person?
5. **Position granularity.** Does every configured channel get a position, or only equipment
   that is swapped as a unit? For example, is each motor axis a position, or only its stage?
6. **Visibility of beamline structure.** May positions, functional elements and Installations
   be global-readable, so that the inventory team sees where its assets are? Engineering records
   stay private either way.
7. **Retirement thresholds** (default 10 %), and whether retired objects with tickets stay
   listed in default searches.
8. **The DNS convention's status.** It is still titled *PROPOSAL* (IT §4.4), and §4.3 relies on
   its class prefixes to allow provisional IT equipment.
9. **Lattice ownership** (AS §15). It decides whether `Beam Element` attributes are imported or
   left empty, and who may assert `upstream of`.
10. **The counting disagreements** (C15). Which serial-line count (141 or 104) and which type
    counts are authoritative for acceptance tests?
