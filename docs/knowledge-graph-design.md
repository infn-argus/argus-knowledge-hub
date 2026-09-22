# The knowledge graph for root-cause analysis

*What the object hierarchy has to be for a failure to be traced through it, what the EPIK8s
configurations already give, what was built to walk it, and what the graph cannot yet do.*

---

## 1. The question, and what was missing

ARGUS exists to answer questions like *"the gun's RF will not ramp: what is wrong?"* and *"three
cameras stopped at once: why?"*. That is not a search and not a neighbourhood: it is a walk along
**who depends on whom**, with a rule for what each dependency carries.

The hub had the pieces of a graph (`Relation` rows between objects, tickets that name objects,
documents that describe them) and a traversal (`knowledge_graph.traverse`), and that traversal is
deliberately **undirected**: it answers "what is connected to this magnet". It cannot say what a
failure reaches, because an edge stored `device → IOC` and one stored `supply → magnet` point in
opposite directions of dependence, and nothing recorded which. Two more things were missing:

- **Most edges were provenance.** In the four configurations 1 014 of 3 962 relations are
  `declared in` (a record and the configuration it came from) and 329 are `deployed on`. Walked as
  neighbours they connect everything to everything through one hub, the configuration.
- **The physical plant was not in the graph.** Chillers, timing, and the pressure a conditioning IOC
  waits on are stated in the files and were not edges.

So the work is not a bigger type hierarchy. The 104 types describe the accelerator well enough. It is
**a meaning for each relation, a walk that respects it, and the edges the configurations were leaving
out**.

---

## 2. The hierarchy, reviewed for this purpose

The catalogue (`asset-schema-design.md`) has four planes under one root, and for root-cause analysis
they are not four kinds of object but **four layers a failure crosses**:

```
  UTILITIES       chiller ─cools→ structure        supply ─powers→ magnet         (physical → physical)
  CONTROL         host ─▶ IOC ─▶ device ─acts on→ asset                            (control → physical)
  PHYSICAL        asset ─realized by→ element                                     (physical → functional)
  FUNCTIONAL      element ─part of→ section ─upstream of→ element                  (beam)
  PERMITS         IOC ─enabled by→ pump, gauge                                     (physical → control)
```

What the real sources say about the hierarchy, family by family:

| Family | State | Evidence |
|---|---|---|
| Control (IOC, device, access point, network, storage) | **Complete, and the densest part of the graph** | all four configurations state it |
| Magnets and their supplies | Complete for the graph: supply `powers` element | 24 of 24 ELI magnets agree with the matrix, including which supply feeds which |
| Vacuum: pumps, gauges | Assets and a permit link to RF conditioning | 30 gates in SPARC, 40 in ELI |
| Vacuum: valves, sectors, regions | **Types exist, no data.** No configuration controls a valve; the ELI matrix names 7 and the regions | the matrix, not the configurations |
| Cooling | Chillers `cool` the structure they name | SPARC 8 channels, ELI 5 |
| Timing | Generator, receivers, and what two receivers trigger | SPARC 3 units, ELI 8 |
| RF power chain (modulator → klystron → waveguide → structure) | **Types partly empty, no relations.** The matrix has the unit's data and no configuration links the chain | ELI matrix `MS01…MC01` against `MOD01…04`, unmatched |
| Beam path order | **Absent.** `upstream of` needs `s` positions, which live in the lattice file, not in any configuration | |
| Rooms and racks | `located in` is defined; the data is in the matrices only | ELI and EuAPS matrices |
| Safety and machine protection | Interlock types exist, `mps-a` has no devices, the PLCs are unread | |

Two decisions follow.

**Do not add types.** What blocks a deeper analysis is edges and data, and a new type nobody feeds is
another empty schema. The three types that would earn their place, and are still to decide: a
**`Utility Service`** (a cooling loop, compressed air, a mains feeder), so that "the loop lost
pressure" is a node with consumers and not a chiller with a guess; an **RF chain** modelled as
relations between the types that exist; and a **Vacuum Region** taken from the ELI matrix's own
column.

**Keep the hierarchy for describing and the relations for reasoning.** A `Quadrupole` being a
`Beam Element` tells you what it is. It is the relations that say what happens when the supply behind
it stops.

---

## 3. What a failure carries: `causal_model.py`

Every relation type has three facts (`backend/app/services/causal_model.py`, served at
`GET /v1/graph/relation-semantics`):

- **layer**: control, power, cooling, vacuum, timing, interlock, function, composition, membership,
  beam, environment, provenance. A walk can be limited to some.
- **flows**: which way a failure travels along the stored edge. `provided by` (device → IOC) flows
  *reverse*: the IOC stops and the device is affected. `powers` (supply → magnet) flows *forward*.
  `declared in` flows *nowhere*.
- **carries**: what the dependent loses.

| A dependent loses… | Meaning | Example |
|---|---|---|
| **control** | readout and command, not function | An IOC stops: nobody sees the ion pump. The pump is still pumping |
| **function** | what it does | A chiller stops: the structure is uncooled. A pump fails: its element is not pumped |
| **permit** | a condition that lets it run | Pressure above a threshold: RF conditioning will not raise power. It does not break anything |
| **degradation** | part is lost | A screen station without its camera; a section without one of its members |

**What a node has lost decides where it can go next.** A device that lost its IOC has lost control,
and can hand on control only: to the asset it acts on. It must not reach the lattice element that
asset realises, because the pump is still pumping. A permit lost is terminal, because an inhibited
process does not break what it drives. One allowance is deliberate: a lost **readout can lose a
permit**, since a permit is computed from a readout (a conditioning IOC cannot check the pressure of a
gauge it cannot read). This one rule is the difference between an analysis that says "the converter
broke the whole machine" and one that says "the converter blinded 34 objects and stopped RF
conditioning from checking two pumps".

Every relation type any importer writes must be classified. A test runs the four real configurations
through the importers and fails on an unclassified one, because an unclassified relation is ignored by
every walk, which is how a graph goes wrong quietly.

---

## 4. The analysis: `root_cause.py`

Three questions, over the dependency graph the model makes out of the stored relations.

**Impact.** *This stopped: what does it take with it?* Breadth-first over (object, loss) pairs, so an
object reached both as a lost readout and as a lost function is reported as both, each by its
shortest path. Each affected object comes with its depth, the path as relations, the layers crossed,
what it loses, whether any object on the path was inferred rather than stated, and whether a hop was
only membership.

**Root cause.** *These misbehave: what would explain them?* The caller gives the symptoms, optionally
which objects are **known to work**, and optionally what kind each symptom is (`control`, `function`,
`permit`). Every object upstream of a symptom is a candidate; each is scored by re-running its impact
and asking which symptoms it reaches with a compatible loss. Candidates are ordered by:

| Term | What it is |
|---|---|
| **fit** = coverage × (1 − contradiction) | the share of symptoms explained, cut by the share of *healthy* objects the hypothesis would also have downed. A cause that predicts a failure that did not happen is wrong |
| **parsimony** = 0.6 × specificity + 0.4 × proximity | what it explains against everything it would take down; and nearer beats farther |

Fit orders first and parsimony breaks ties, and they are never folded into one number, because a
candidate that explains half the symptoms must not outrank one that explains all of them for being
smaller. Nothing here is a probability. Beside the ranking the analysis returns **the fewest causes
that explain every symptom** (several symptoms often have several causes), excluding any refuted by a
healthy object, and for each candidate the path to each symptom, what else it would break, and how
often earlier tickets named it.

**Single points of failure.** For every object, what it would take with it, ranked by
`3 × function + readout + degraded + permit`, with the function and readout lists also on their own:
a converter that blinds two hundred channels and a supply that stops one magnet are different
problems and neither should hide the other.

They are available as `GET /v1/graph/impact`, `POST /v1/graph/root-cause`,
`GET /v1/graph/blast-radius` and as three MCP tools for ARGUS (`impact_analysis`,
`root_cause_analysis`, `single_points_of_failure`) that return paths as one quotable line:
`SPARC:IOC:rf-conditioning-gun --enabled by--> …`.

**`alarm_symptoms.py` connects this to a live feed — the translation, not the connection.** There
is no alarm server, archiver or network reachable from here, so nothing here calls one. What it
does is the step a real connection would still need afterwards: an alarm names a PV, and turning a
PV into a symptom the engine above can use is one function, done once, rather than reinvented by
whoever wires in Phoebus, the CA gateway's own alarm handler, or a CSV export next.

- **Resolution.** `Control Device.pv`, already on every device the import makes, is matched exactly;
  `IOC.pv_prefix` is matched by longest prefix for a heartbeat or connection alarm that names the IOC
  rather than a channel. What resolves neither is reported under `unresolved`, never dropped.
- **What severity means is EPICS convention, not invented here.** `INVALID` — the record could not
  determine a value — reads as a lost **readout**; `MINOR`/`MAJOR` — the value is out of range — as a
  lost **function**, and is placed on the asset the device acts on, not the device itself, since a
  bad reading is not a broken channel. `OK` is not a symptom; it becomes `healthy` automatically, so a
  caller who has a full snapshot does not have to say twice that something works. A status that names
  a disconnect is read as `INVALID` whatever the severity field says.
- **A lost permit is never inferred.** There is no severity for "a condition is not met"; the caller
  states `kind: "permit"` when they know one, and nothing here guesses it from a value alarm.
- **Two alarms on one object keep the worse.** A device reported disconnected and, moments earlier,
  out of range keeps the lost function, not the milder claim.

`POST /v1/graph/root-cause/from-alarms` and the MCP tool `root_cause_from_alarms` take a list of
`{pv, severity, status, kind?}` and return exactly what `root_cause_analysis` does, plus what could
not be placed. Checked against real SPARC data: two disconnected pump PVs point at the serial
converter they share; adding a third PV, reported `OK`, for a pump on the *same* converter refutes it
and the answer becomes the two IOCs instead — the same result `root_cause_analysis` gives when a
person supplies the same facts by hand, reached this time from PV names alone.

---

## 5. What the configurations give, measured

Relations after `import_epik8s.py --infer-elements` on the four configurations, by what a failure
does across them:

| Layer | Relations | SPARC | BTF | EuAPS | ELI |
|---|---|---|---|---|---|
| **control** | `provided by`, `reached through`, `acts on`, `connects to`, `on network`, `drives`, `mounts` | 975 | 219 | 335 | 417 |
| **power** | `powers` | 81 | 43 | 0 | 24 |
| **cooling** | `cools` | 5 | 0 | 0 | 8 |
| **timing** | `timed by`, `triggers` | 2 | 0 | 0 | 17 |
| **permit** | `enabled by` (a pump, and the readout of it, per gate) | 60 | 0 | 0 | 80 |
| **composition** | `composed of`, `realized by`, `part of` | 61 | 7 | 44 | 9 |
| provenance | `declared in`, `deployed on`, `templated from`, `configures` | 731 | 197 | 294 | 353 |

Objects: SPARC 1 002, BTF 279, EuAPS 311, ELI 405. Relations: 1 915, 466, 673, 908.

What was added in this round, all from what the files say and every one marked by an inferred object at
one end:

- **RF conditioning gates.** An RF conditioning IOC lists the pumps and gauges whose pressure it
  watches, and the level above which it will not raise power. That is the file saying RF depends on
  vacuum. The IOC is `enabled by` each pump's control channel (stated), and, with inference on, by the
  pump itself, so a pump that fails reaches the permit as well as one that cannot be read. The
  threshold is kept on the IOC as `permit_conditions`. SPARC: 30 gates, ELI: 40, none unresolved.
- **Chillers `cool` what they name.** `CHLGUN01` cools the gun, `CHLAC101` the first section, ELI's
  `ACC02` a structure, its `MOD` every modulator. A chiller whose target the rules do not know
  (`CHLBOC01`, a pulse compressor; `CHLSLS01`) is a chiller and cools nothing in the graph: an element
  of a guessed type is worse than none.
- **Timing.** Event receivers are timed by the beamline's generator (when there is exactly one:
  with two, nothing says which), and a receiver whose name says `LLRF` or `CAM` triggers those.
  `DIA:FCT01`, listed on ELI's timing IOC, is a charge monitor and is left alone.

---

## 6. Worked examples on the real graph

Run on SPARC and ELI as imported above.

**The converter.** Impact of the serial converter `scsparcsipmxa001`: 36 objects. 15 control
devices, 6 IOCs, 13 ion pumps and 2 NEG cartridges lose their **readout**, and 2 RF conditioning
IOCs lose a **permit**. No element loses a function, because no pump stopped.

**Two lost readouts.** `GUNSIP01` (IOC `vac-gunvpc`) and `W2KSIP03` (IOC `vac-kly02vpc`) disconnect.

```
fit 1.00  scsparcsipmxa001     would also affect 36    (both behind it)
fit 0.50  IOC vac-gunvpc                                (only one of them)
fewest causes: scsparcsipmxa001
```

Add that `AC1SIP01`, on the same converter, still answers: the converter is refuted, and the fewest
causes become the two IOCs.

**RF will not raise power.** The conditioning IOC's own permit is lost. Every pump it watches ties
at fit 1.00, each reached by one hop, marked inferred. The graph cannot choose among them; a caller
that knows which gauge is high can, by giving it as a symptom.

**Two screen cameras stop.** In ELI: `EVR-CAM` (fit 1.00, would also stop 6) and the event generator
`TMG` (fit 1.00, would also stop 17) both explain it; the cameras' own failures explain half each.
The generator is the more parsimonious explanation if more than the cameras stopped.

**Single points of failure.** SPARC: the `sparc-magnets` network (140 readouts), `sparc-br-cams` (64),
the access points that serve most channels (57, 51, 39, 38, 36). ELI: the two vacuum converters (60, 51) and the event
generator, which is the largest by *function*: 17.

---

## 7. What the graph cannot do yet

- **It still needs a live source.** `alarm_symptoms.py` turns a list of PVs and severities into
  symptoms; nothing here calls an alarm server, an archiver or a log. Wiring in Phoebus, the CA
  gateway's own alarm handler, or the archiver's disconnect events is the step still open — the
  translation this round did is what that connection now hands its output to.
- **No beam-level analysis.** "The orbit moved" needs the order of elements, `upstream of`, from a
  lattice. `Beam Element` objects exist with `lattice_name`; the `s` positions do not.
- **Vacuum stops at pumps and gauges.** No configuration controls a valve, and the sector a valve
  isolates is in the matrix only.
- **The RF chain is not linked.** The modulator, the RF unit, the waveguides and the structure are
  not related to one another, so a modulator fault does not reach a structure. The ELI matrix names
  the units and the configuration names the modulators, and nothing joins them.
- **Edges carry no provenance.** A relation cannot be marked inferred, so the analysis says a path is
  inferred when an *object* on it is. Every relation the inference makes has an inferred object at one
  end, which is why this holds, but a stated edge between two stated objects that someone should not
  trust cannot be flagged.
- **No probabilities.** The ranking orders hypotheses by evidence and says why. Prior failure rates,
  and a calibrated likelihood, need history the hub does not hold. Earlier tickets are returned as
  evidence, not weighed.
- **Racks and rooms** (`located in`) are defined and unfed.

---

## 8. What follows, in order

1. **DONE — the alarm-to-symptom translation** (`alarm_symptoms.py`, `POST /v1/graph/root-cause/from-alarms`,
   the `root_cause_from_alarms` MCP tool). What is still open is the live source: a connector that
   reads an alarm server or the archiver's disconnect events and calls this.
2. **Read the matrices as feeders** (ELI CSV, EuAPS workbook): racks and rooms (`located in`), the
   vacuum region, the magnet and RF-unit numbers, and the RF power chain where a matrix names it.
   Fills the physical and environment layers.
3. **Lattice ordering** from a MAD-X or elegant file: `upstream of`, `s_position`, so beam-level
   symptoms have a path.
4. **A `Utility Service` type** so cooling loops, compressed air and mains feeders are nodes with
   consumers.
5. **The IT layer** (`it-model-design.md`): serial lines, converters as equipment, switches. It
   deepens the control layer where most failures start.
6. **Weigh history**: once the hub holds enough tickets with a stated cause, a per-object prior.

**Decisions for you.** Whether the analysis should treat the symptom object itself as a candidate
(it does, ranked by parsimony); whether `part of` should carry a failure at all (it does, weakly, as
degradation); and the relation names `cools`, `timed by`, `triggers`, `enabled by`, which extend the
vocabulary of `asset-schema-design.md` §6.
