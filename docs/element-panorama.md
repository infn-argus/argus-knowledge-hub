# Element panorama: what the matrices say, what the configurations say, and how the schemas are fed

*A survey, not a proposal to build. It lays the ELI Utility Matrix next to the ELI control
configuration, family by family; sums up which elements the import already turns into typed
objects; and says, for each type, which attributes a configuration can fill and which someone has
to complete by hand.*

> **Evidence document.** The measured joins and source gaps below remain valid. The normative model
> is [`asset-model-revision.md`](asset-model-revision.md): configuration-derived equipment-like
> records become Positions, physical units are Equipment in ARGUS inventory, and Installations join
> them over valid time. Jira/Insight links are migration evidence and aliases, not continuing
> authority after cutover.

---

## 1. Sources

| Source | What it is | Size |
|---|---|---|
| `docs/2025-06-18 - Utility Matrix OFFICIAL(Utility Matrix).csv` | ELI-NP Low Energy Linac (`LEL`), a cabling and utilities matrix: what is where, on which rack, with which cable, on which vacuum region, with its electrical and cooling data | 162 equipment rows in 9 categories: `VAC` 52, `DIA` 31, `MAG` 24, `ELE` 21, `RF` 12, `TIME` 7, `NET` 6, `MPS` 5, `SYNC` 4 |
| `../epik8s-eli/deploy/values.yaml` | The ELI control configuration | 56 IOCs, 137 device entries (131 distinct names: the four LLRF IOCs each list `ad1`, `ad2`) |
| The SPARC, BTF and EuAPS configurations, and the EuAPS Utility Matrix | Already read (`asset-schema-design.md` §9.5, `it-model-design.md`) | |

The ELI matrix is dated 2025-06-18 and the configuration is newer, so some differences are the
matrix being older, not an error in either. The CSV is Windows-1252 encoded.

**What a matrix row carries** (the columns of the CSV):

| Group | Columns | Filled for |
|---|---|---|
| Identity | Ref. code (the category), Equipment Name, Room, Module, Equipment Description | every row |
| Cabling | To Rack, rack-side and module-side connector, who connectorised it, cable type, cable labels, type of connection, comments from LNF and from IFIN | every row, nearly |
| Vacuum | Vacuum Region, Vacuum Gauge Controller, Ion Pump Controller | 29, 9 and 33 of the 52 `VAC` rows; the region also on all `MAG` and `DIA` rows |
| Magnet | Magnet PSU, Polarity Reversal Crate, nominal voltage, cross section, current +10 %, nominal current, nominal power, cooling water (inlet temperature, rise, pressure drop, flow), weight, power-supply voltage, current and output power | all 24 `MAG` rows (polarity crate on 4) |
| RF power unit | frequency, peak and average power, pulse voltage and current, 3-phase input power, dissipated power, cooling water, weight | the 8 `ELE` rows of the four RF power units |

---

## 2. The ELI panorama

One row per family. *Link* is how a matrix row is found in the configuration; *Result* is what
`import_epik8s.py --infer-elements` makes from the configuration today.

| Family | Matrix | Configuration | Link | Agreement | Result today |
|---|---|---|---|---|---|
| **Magnets** | 24: 14 H/V correctors, 6 solenoid coils, 3 quadrupoles, 1 dipole | 24 devices on 13 supply IOCs (10 Sigmaphi, 3 iBILT) | the device name is the matrix name without `LEL-MAG-` (`SOL02:COIL[01-03]` is `SOL02:COIL0103`) | **24 of 24** by name, and **24 of 24** name the same supply | 24 `Power Supply`; elements 14 `Corrector`, 6 `Solenoid`, 3 `Quadrupole`, 1 `Dipole` |
| **Polarity reversal** | a crate named on 4 magnets (`QPRC01/02`, `QPRC03`, `DPRC01`) | 2 ICPDAS IOCs with 6 groups `MAG01`…`MAG06`: two relays and two status inputs each (24 channels) | none: the names do not overlap | 4 crates against 6 groups | nothing (`io/icpdas` has no rule) |
| **Ion pumps** | 33 (15 on the linac, 18 on waveguides) | 35 | name without `LEL-VAC-` (`WGS01:IONP01` is `WGS01IONP01`) | all 33 are configured; the configuration has two more (`WGS02IONP05`, `WGC01IONP05`) | 35 `Ion Pump` |
| **Ion pump controllers** | `VPCON01`–`04`, `08` | 9 IOCs (`vpcon01`–`04`, `vpcon4`–`8`) on two 16-port Moxa units (`scelimxa16001`, `…002`) | the number in the name | `VPCON01`/`02` agree. The matrix puts six pumps on `VPCON03` and omits `IONP12`; the configuration splits them over `vpcon03` and `vpcon04`, four and three. A controller here has four channels, so the configuration is the consistent one. Waveguide pumps are grouped by section in the matrix and packed four to a controller in the configuration | controllers are the IOCs; no controller asset |
| **Vacuum gauges** | 6 cold-cathode (`GAUCC`), 3 thermal-conductivity (`GAUTC`) | 6 `CC` channels on `vgcon01`/`02` | `GAUCC01` is `CC01` | the 6 cold-cathode match; the 3 thermal gauges have no channel | 6 `Vacuum Gauge` |
| **Valves, RGA** | 7 valves (4 manual, 2 pneumatic, 1 fast) and 1 residual gas analyser | none | | not controlled through EPICS; the PLCs interlock them | nothing |
| **Screens** | `SCN01`–`SCN06`, each a camera, an illuminator and a motion box (trigger and control) | `SCN0n:CAM01` (6 cameras on 6 IOCs, each with its IP), `SCN0n:MOT01` (6 axes on `diag-tml`, through a Moxa port), one `CAMILLUM` relay | the parent is in the name: `LEL-DIA-SCN01:CAM01` and `SCN01:MOT01` share `SCN01` | 6 of 6 cameras and motion boxes; 1 illuminator channel for 6 illuminators | 6 `Camera`, 6 `Motor Axis`; **no screen station**, because the code is `SCN`, not `FLG` |
| **BPMs** | `BPM01`–`BPM05` | 5 channels on two Libera Spectra units | the name | 5 of 5 | 2 `Digitizer` and 5 `Beam Position Monitor` |
| **Charge monitors** | `FCT01`, `FCT02` | `DIA:FCT01`, `DIA:FCT02`, listed on a **timing** IOC | the name with `DIA:` | 2 of 2 | nothing: a timing IOC has no rule |
| **RF: structures** | gun cavity, 3 accelerating structures (S, S, C band), 4 directional couplers | none | | not controlled | nothing |
| **RF: power units** | 4 ScandiNova units: `MS01`, `MS02`, `MS03` (S-band, 2856 MHz) and `MC01` (C-band, 5712 MHz), with their electrical and cooling data | 4 modulators `MOD01`–`MOD04` on hosts `pwelimod001`–`004` | **none**: `MS01…MC01` against `MOD01…04` | four against four, but nothing says which is which | 4 `Modulator`, empty |
| **RF: LLRF** | none | 4 Libera LLRF units | | the matrix has no LLRF | 4 `Low-Level RF Unit`, empty |
| **Cooling** | no rows, only the water figures of each magnet and unit | 5 chillers: `GUN`, `ACC01`–`03` (SMC) and `MOD` (Polyscience) | | `ACC01` in the configuration is the *chiller of* the structure `LEL-RF-ACC01`, not the structure | nothing (`cool/smc` has no rule) |
| **PLCs** | 4 junction boxes, "PLC for Magnets and Vacuum M1–M4" | 2 PLC devices, `MAG` (10.16.4.171) and `VAC` (10.16.4.170) | | 4 against 2 | nothing |
| **MPS** | 5: a fast interlock and one line per RF unit | `mps-a` at 10.16.4.230:502, no devices | | | nothing |
| **Timing, sync** | 7 timing rows, 4 sync rows | 4 IOCs of EVG and EVR, 10 channels | | | nothing (10 channels not read) |
| **Network** | 2 Catalyst C9500 switches and a data link per RF unit | none | | no switch is named in the configuration | nothing |

Not every family is in both. What matters for the schemas is the split: **the configuration
carries the channels, and the matrix carries the box, the place and the numbers.**

### What this shows

1. **ELI is the one facility where the two sources can be joined by name.** The configuration
   device name is the matrix name without its `LEL-<system>-` prefix, and where the matrix has a
   parent (`SCN01:CAM01`) the configuration keeps it. For magnets the join is exact, including
   which supply feeds which coil.
2. **The matrix is right about places and numbers, and older about wiring.** Where the two
   disagree on which controller a pump hangs from, the configuration is the physically consistent
   one, since a four-channel controller cannot hold six pumps.
3. **Some names look alike and are not the same thing.** The `ACC01` chiller channel and the `ACC01`
   structure. A join on names has to know the family first.
4. **The bigger gaps are on the matrix's side of the schemas**, not the configuration's. See §4.
5. **A rule gap was found and fixed.** `DIP01` is *Dipole A* in the matrix and was left without an
   element because the name code was unknown; the inference now reads `DIP` as a dipole.

---

## 3. The elements treated so far

What `--infer-elements` makes, across the SPARC, BTF, EuAPS and ELI configurations (measured):

| Element | Type (plane) | Read from | Facilities |
|---|---|---|---|
| Ion pump, NEG, turbo, primary pump, vacuum gauge | equipment-class **Position**; the installed unit is separate Equipment | `vac` group and function; the name (`SIP`, `NEG`, `TRB`, `PRY`, `VGA`) | all four |
| Magnet supply | `Power Supply` Position; limits remain on its Control Device | `mag` group; limits from `ps:` | SPARC 81, BTF 44, ELI 24 |
| Magnet | `Quadrupole`, `Dipole`, `Corrector`, `Solenoid`, `Sextupole` (element) | the name (`QUA`, `DPL`, `DIP`, `HCR`, `SOL`…) | SPARC, BTF, ELI |
| Camera | Camera Position; the serialised camera is Equipment | `cam` group; not a simulator | SPARC 26, BTF 3, EuAPS 15, ELI 6 |
| BPM electronics | Digitizer Position serving `Beam Position Monitor` elements | Libera templates | SPARC, ELI |
| LLRF, modulator | equipment-class Positions | Libera LLRF, ScandiNova templates | SPARC, ELI |
| Motor axis | installable `Motion Axis` Position when independently replaceable; otherwise a Control Device acting on its parent Position | `motor` template | SPARC 42, BTF 14, EuAPS 52, ELI 6 (plus flags below) |
| Flag | actuator Position and `Screen Station`; camera composition is an advisory relation pending review | `FLG` in the name; camera by name | SPARC 23, BTF 1 |
| Mirror | `Mirror` composed of its axes | EuAPS name codes, as its Utility Matrix names them | EuAPS 19 |

**Not treated, by size** (from the import's own report): ICPDAS I/O, 26 channels in SPARC and 25
in ELI (RTD temperature sensors, relays, digital inputs and outputs); scope channels (16 in SPARC);
timing modules (10 in ELI); chillers (8 in SPARC, 4 in ELI); PLC and MPS units; the soft IOCs
(orbit, calculation, RF conditioning), which are software.

---

## 4. How the schemas are fed

The catalogue's types are established, and several are still empty: `Digitizer`, `Modulator`,
`Low-Level RF Unit`, `Chiller`, `Timing Module`, `PLC`, `Instrument`, `I/O Module`,
`Electronics Crate`, `RF Amplifier`. The sources below say what could go in them.

Three feeders assert facts about related records, each under a versioned authority policy:

1. **The configuration states** control structure: IOC, Control Device, channel, axis, address,
   template, zones, and limits. These become stated claims.
2. **The configuration implies** Positions and topology. Each inference is a claim with a
   semantic rule id, evidence, and authority status; low-confidence composition is proposed.
3. **A person or matrix contributes** design, model, place, and engineering values. Conflicts are
   resolved by policy and explicit decisions rather than “fill blanks” or last-writer-wins.
4. **The AI Intake proposes** what a person would otherwise type from a matrix, a datasheet or a
   photograph (§4.1). Its output is a ledger proposal, never a written value.

Physical Equipment is created and maintained in ARGUS inventory. A matrix row or migrated Insight
record may identify that unit; the configuration never manufactures it from a channel name.

Per type, for the elements treated (*written* is what the import puts on the object today;
*available* is what a source holds that nothing writes yet):

| Type | Written today | Available in the configuration | Available in a matrix | Only by hand |
|---|---|---|---|---|
| `Ion Pump` | `argus_system`, the `asset:` link as `inventory_url` | nothing more | pumping speed is in the description (*Ion pump 75 l/s*), the controller, region, cable | serial, installed date, `nominal_voltage`, `element_count` |
| `Vacuum Gauge` | `argus_system` | the sensor kind, from `devtype` (`img`) and `sensor` (`I1`) | kind and model (*Agilent IMG300*), controller, region | serial, range |
| `Turbo Pump`, `Primary Pump` | maker and model from the template | | | rotation speed, backing pump |
| `Power Supply` | maker and model where the template is known, `current_max`, `voltage_max`, `bipolar` from `ps:` | interface (from the template), `n_channels` (the devices on the IOC) | the supply's own voltage, current and output power | serial; **ELI's `sigmaphi` and `ibilt` templates have no maker or model yet** |
| Magnet elements | `lattice_name`, `plane`, `zone`, `argus_beamline` | | nominal voltage, current, power, cross section, cooling water, weight, cables, polarity crate | `s_position`, `length`, `gradient`, `k1`: these belong to the lattice file |
| `Magnet Assembly` | **never made** | | the whole magnet block of the matrix | `coil_resistance`, and the fields the schema lacks |
| `Camera` | maker and model when `devtype` is `Vendor-model` | the address (`id`), the network (`multus`) | cable, rack, region | lens, sensor, calibration |
| `Digitizer`, `Low-Level RF Unit` | maker and model from the template | | | everything else, and the schemas have no attributes |
| `Modulator` | maker and model from the template | `v_max`, `i_max`, `pls_width_max`, `pres_warn`, `pres_alarm` (control limits, **units not stated**) | frequency, peak and average power, pulse voltage and current, input power, dissipation, cooling, weight | serial |
| `Motor Axis` | `axis_id`, `argus_system` | `dllm`, `dhlm`, `mres`, `velo`, `home` (limits, resolution, speed, homing: in `settings` on the device, with **units that differ by controller**) | | `has_home_switch` |
| `Actuator`, `Screen Station` | position labels; `lattice_name`, `insertion_positions` | | | screen material, optics, calibration |
| `Mirror` | `beam`, `mirror_kind` | | | coating, diameter, substrate |

The matrix column on the right is the largest untapped source for ELI, and it points to three
schema changes before anything is built:

1. **`Magnet Assembly` lacks the magnet's electrical and cooling data.** The matrix holds twelve
   numbers per magnet (voltage, current, power, cross section, four cooling-water figures, weight),
   and the type has three attributes (`coil_resistance`, `cooling`, `weight`). The import also never
   makes one, so those numbers have nowhere to land.
2. **`Modulator` is empty, and the matrix describes the RF power unit as a whole.** Frequency,
   peak and average power, pulse voltage and current and three-phase input are the identity of the
   unit. Whether that is a `Modulator` attribute set or an `RF Amplifier` (the ScandiNova unit is a
   modulator and a klystron) is a modelling decision.
3. **Racks, connectors and cables are in the matrix on every row** (`To Rack`, connector, cable
   type, cable labels, who connectorised it). The catalogue has `Cable Run` and a `Rack` location;
   nothing feeds them, and nothing relates a device to its rack.

**The legacy inventory link the configurations already carry.** The four configurations (259 IOCs)
hold 91 `asset:` links into Service Desk Insight that name a `typeId`:
40 on vacuum controllers (`2505`), 14 and 10 on cameras (`3799`, `2748`), 13 on magnet supplies
(`2457`), and a handful on instruments, timing, BPM electronics and motion controllers. During
migration the object id binds to ARGUS Equipment and remains an alias after cutover. On an IOC or
device the link is evidence for a proposed Installation at the inferred Position; on a template it
is evidence for a Product Model. It is not a permanent call back to Jira.

### 4.1 AI-supported extraction from matrices and photographs

The *Only by hand* column above is where the AI Intake
([`asset-model-revision.md`](asset-model-revision.md) §23) saves the most typing. Its output is
always a **ledger proposal**: an AI claim with its evidence, routed to the record's owner. It is
never a value written into the attribute bag, and never a fill-blanks rule.

| Input | What the model proposes | Evidence kept | What it does not do |
|---|---|---|---|
| a matrix row (ELI Utility Matrix, EuAPS workbook, PBS) | attribute values for the types above (a magnet's twelve electrical and cooling figures, a modulator's power figures), a rack, a cable, a vendor or Product Model match | sheet, row and cell, and the column header as read | invent an attribute the type lacks. A figure with no home (the `Magnet Assembly` gap in point 1) is reported as missing, and the schema change comes first |
| a matrix description (*Ion pump 75 l/s*, *Agilent IMG300*) | normalized values (pumping speed with its unit; manufacturer and model), and a Product Model candidate | the cell and the quoted text | guess units that the matrix does not state. The control limits flagged above with **units not stated** stay proposals without a unit, for a person to settle |
| a photograph of a nameplate or a rack | manufacturer, model, serial, inventory number (risk R2); a Position or Installation candidate (R4) | the image region | create Equipment from a channel or a PV; confirm a serial; start an Installation |
| a delivery note or datasheet page | the Product Model's specifications; the unit's serial | page and text span | overwrite a confirmed value. A difference opens a conflict |

**Matrix extraction is a proposal, and so is a deterministic reader.** Where a matrix column maps
one-to-one to an attribute, a deterministic importer under a semantic rule id (revision §7.9)
remains the better feeder: it is reproducible and needs no model. The AI Intake is for what a
rule cannot read: free-text descriptions, inconsistent layouts, photographs, one-off
spreadsheets. When both read the same cell, the deterministic claim ranks higher by policy, and
a disagreement between them is a conflict for a person.

**Spreadsheets are untrusted content.** A cell that reads as an instruction, a formula that calls
out, or a hidden sheet is data to be extracted or flagged, never followed (revision §23.10).

---

## 5. What would follow, in order

None of this is built. Each step stands on its own.

1. **Add only the extension attributes justified by the matrices**: magnet and RF-unit values and
   governed location references. Activate a new type only with a source, owner, and query.
2. **Read a matrix into the fact ledger.** A CSV or workbook reader like the PBS importer, keyed by
   the normalized name (ELI) or PBS code (EuAPS), writes source claims with cell evidence. Authority
   policy and explicit decisions handle conflicts. For ELI the join is exact for magnets, pumps,
   gauges, cameras, motion boxes and BPMs.
3. **Add the ELI screen rule.** `SCN01` is the parent of `SCN01:CAM01` and `SCN01:MOT01`, and the
   matrix says the screen is the camera, illuminator and motion box. This is the same composition
   the SPARC flags already get, with a stated parent instead of a paired name.
4. **Treat the ICPDAS channels**: RTD as `Temperature Sensor`, `rly` and `di` as relay and
   input channels, with the ELI polarity-reversal groups linked to the magnets they reverse.
5. **Treat timing, chillers and PLCs** with the types they already have (`Timing Module`,
   `Chiller`, `PLC`), and link a chiller to what it cools.

**Open, and the matrices cannot say:** which ScandiNova unit is which modulator (`MS01…MC01`
against `MOD01…04`); whether ELI's four PLC junction boxes are two PLCs; which polarity-reversal
group belongs to which magnet; and whether the RF power unit is one object or two.
