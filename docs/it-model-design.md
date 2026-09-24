# IT and network model for the object catalogue

*Where do switches, hosts, consoles and Ethernet-to-serial converters (Moxa) live in the catalogue,
and how do the control configurations reach them? §0 says what is built; the rest is the design
it was built from.*

> **Implementation baseline and evidence document — not the current production specification.**
> [`asset-model-revision.md`](asset-model-revision.md) is normative. The measurements, hostname
> analysis, and source mappings below remain useful; its former ownership and connectivity model is
> superseded.

In the current target model:

- ARGUS IT inventory, not Jira Insight, is the system of record after the IT domain cutover;
  Insight is a migration source and temporary archive, while DNS/DHCP remain continuing operational
  inputs for live addressing;
- a stable IT **Position** represents the host or converter role, physical **Equipment** is installed
  there through a valid-time **Installation**, and an Access Point is assigned to that Position;
- the old `Serial Line` splits into `Communication Path`, `Bus Segment`, and `Equipment Port`;
- Access Points remain beamline or IT control-plane records and are never reused as Equipment;
- DNS prefixes and the Moxa `4000 + N` convention are advisory evidence until their owners confirm
  them; neither can establish physical identity or a port attachment by itself;
- IT imports, people, and resolvers write ledger claims. They do not overwrite attribute bags.

---

## 0. What is built

This section is a snapshot of the pre-revision implementation. It is the migration starting point,
not the desired end state.

The decisions in §9 were taken as recommended: a dedicated site workspace for IT, the serial line
as an object, and IT equipment that the configuration import makes and marks as inferred.

**Catalogue (122 types, was 104).** Under `Asset`: `IT Equipment` (hostname, FQDN, primary IP,
MAC, firmware, management URL) → `Network Device` → `Switch`, `Router`, `Serial Converter`,
`Media Converter`; and `Computing Node` → `Server`, `Workstation`. Under `Item`: `IT Record` →
`Network Segment`, `Address Record`. Under `Control Item`: `Serial Line`. `Access Point` gains
`endpoint_kind` and `endpoint_kind_source`. `Network Device` and `Computing Node`, which existed
empty, moved into the tree in place (the seeder now follows a type that changed parent).

**Import (`--it-workspace`).** For each Access Point:
- its **kind** (serial converter, host, instrument, camera) is read from the class prefix of INFN's
  DNS naming convention (`dns_convention.py`, §4.4), or, for a bare IP, from a port in Moxa's
  4001–4999 range, and the evidence is written beside it;
- a device on a port of a converter is `on line` a **Serial Line** that is `port of` the converter's
  Access Point (a `serial:` block, which the import ignored, is now an endpoint too);
- an IOC that names a `host:` `runs on` it;
- with `--it-workspace`, the converter, server or console a hostname names is made **once, in that
  workspace, flagged global**, keyed by its fully qualified name, and the Access Point is
  `implemented by` it. Two beamlines that reach one host share one object.

**Measured on the four configurations** (into a workspace `it-infrastructure`): 18 serial converters
and 12 servers, and 104 serial lines (SPARC 39, EuAPS 28, ELI 17, BTF 20; BTF's are behind bare IPs).
The converter `scsparcsipmxa001` reaches **41** objects when it stops (15 devices, 13 pumps, 6 IOCs,
4 lines, 2 NEG, its Access Point) and its port-4003 line alone **9**: the answer the flat model
could not give.

**Not built, and why.** Address Records and Network Segments exist as types and nothing fills them:
that needs the registry (Jira Insight or a DNS/DHCP export), whose real attributes I still have not
seen. Consoles come from an Ansible inventory that no configuration mentions, and no reader exists.
Switch topology (`uplinked to`) is IT's, not the configuration's. The resolver's local domains are
unchanged (`.int.eli-np.ro` is still not one), because shortening ELI's names would re-key its
Access Points. `--it-workspace` is a script option only: through the API it would let a caller write
into a workspace it may not have rights to, and that check is not written.


---

## 1. What the sources actually say

Measured on the SPARC, BTF, EuAPS and ELI configurations, and on the SPARC repository.

### In `values.yaml`

| Fact | Measured |
|---|---|
| Endpoints that serve ports (`server:` + `port:`) | **41** across the four (SPARC 22, BTF 9, EuAPS 8, ELI 2) |
| Serial lines (a distinct `server`+`port`) | **141**: SPARC 74, BTF 16, EuAPS 35, ELI 16 |
| Devices on those lines | **330** |
| Line shape, from the keys the file uses | 84 single device · 27 multi-channel controller (`channel:`) · 7 multi-drop bus (`id:`/`addr:`) · 23 shared, mostly multi-axis controllers (`axid:`) |
| Endpoints that are bare IPs, not hostnames | BTF: **9 of 9** (`192.168.192.40:4001`); SPARC 4 of 22 |
| Devices that are Ethernet-native (their own `ip:` and `port:`, mostly Modbus TCP on 502) | BTF 28; none in the other three |
| IOCs that run *on the instrument* (`host:`, over ssh) | SPARC 21 distinct hosts, ELI 10 |
| Gateways' load-balancer IPs | all four |
| VLAN hint on the gateways (`lb-network-access`) | three of the four: `vlan-10-6` (SPARC), `vlan-108` (BTF, EuAPS); ELI gives none |
| Multus network annotations | `sparc-br-cams`, `sparc-magnets`, `sparc-net`, `btf-189`, `euaps-cams`, `multus-secondary-net` (ELI) |
| One NFS server, `192.168.197.157` | named by **SPARC, BTF and EuAPS** (ELI names none) |
| Consoles | only a `console` and a `notebook` *service* (Phoebus web, Jupyter) in each |
| Network switches | **none named** (`Qswitch` in SPARC is a laser) |

### Not in `values.yaml`, but in the SPARC repository

`opi/ansible/hosts.yml` and `console_list.ini` list the **console workstations**: group
`sparc_consoles` (`pwsparcco001`…`005`, `pldanteco109`, `plsparcmagnuc001`), a test group, and a
`windows_hosts` group. Some are commented out. Nothing else in the configuration says a console
exists, so any console model needs a second source. I did not check whether BTF, EuAPS or ELI have
the equivalent.

### In the EuAPS Utility Matrix

`docs/EuAPS Utility Matrix.xlsx` is an equipment list of 391 rows, 381 of them coded (FLAME
Paradiso 62, FLAME Inferno 140, and the SPARC hall 189). It is the first source here that says
what the boxes *are*, not just where they are reached:

| Fact | Measured |
|---|---|
| Ethernet-to-serial converters | **6**, all Moxa NPort 5650: one `-8` (`FPCTR1`, motors and cameras of Paradiso) and five `-16` (`FPSAF1` ×2 for HiScroll 6 and TwisTorr controllers, `FICTR1`, `SPCTR1`, `SPCTR3`) |
| How they match the configuration | `scflameprmoxa001` is `FPCTR1` (ports to 4005, of 8), `scflameprmxavac001`/`002` are `FPSAF1-001`/`002` (the matrix note says "HiScroll6 + TwissTorr ctr FP" and "… FI"), `scflameinfmoxa001` is `FICTR1` (ports to 4008, of 16). The ports the configuration uses fit the capacity |
| Hosts of IOCs | 4 embedded PCs, ADLink MXC-6401D (motor IOCs at FP, FI and the SPARC hall) and MXC-6322D (a general one, "misticanza") |
| Dependencies (`FUNCTIONAL DEPENDENCIES`) | a motor names the controller it hangs from (`FPCTR1-K-MMIR-CTR-001`); 27 of 28 cameras, all converters and all embedded PCs name only **`switch`**, with no identity; one camera names an IOC host |
| Racks | 6 (2 Inferno, 1 Paradiso, 3 SPARC), the contents as free text: `moxa`, `switch in fibra`, `8 pollux (MP21)`, `Controller Beckhoff 1` |
| MAC addresses | the column exists and is **empty in every row** |
| Naming | `<area><zone>-<service>-<father object>-<what>-<nnn>`; `K` is the rack and controls hardware service, and `CONV-S2E` is the converter |

So the matrix answers what the converters are (model and number of serial ports), and gives every
motor its controller. It does not answer what the switches are, and it holds no address.

### In the inventory (from the code, not from data)

`network_resolve.py` and its tests name the Jira Insight types the inventory already held:
**Converter, Server, Camera** (the equipment) and **Registered Nodes, DHCP Nodes, Ethernet
Configuration, DNS, IP** (address records). A Moxa was recorded twice, as a `Converter` (the box,
with a purchase order) and as a `Registered Node` (its address), objects keyed `LNFMAC-…`. The
resolver reads attributes named `ip`/`ip_address`/`indirizzo_ip`, `hostname`/`fqdn`, and
`mac`/`mac_address`. **I have not seen these types' real attributes**, and the design depends on
them (section 9).

### What the catalogue has today

| Type | Where | Own attributes |
|---|---|---|
| `Network Device` | `Asset` (global) | `device_kind` (Switch, Terminal server, Media converter, Router), `n_ports`, `hostname`, `ip`, `fqdn`, `firmware_version` |
| `Computing Node` | `Asset` (global) | `hostname`, `ip`, `cpu`, `ram_gb`, `os`, `role` |
| `Access Point` | `Control Item` (beamline) | `address`, `ip`, `hostname`, `fqdn`, `port_count`, `network` |

No `Console`, no serial port, no address record, no network segment. **SPARC holds zero
`Network Device` or `Computing Node` objects**; its 138 Access Points are what the import made.
By the class prefix of the DNS convention (section 4.4): 86 are bare IPs, 12 serial converters
(`sc`), 10 beam instrumentation (`bd`), 9 physical Linux hosts (`pl`), 6 RF devices (`rd`),
6 cameras (`cc`), 5 DAQ devices (`dd`) and 4 generic devices (`gd`). Every one of the 52 that
has a name carries a valid class prefix.

---

## 2. The gaps, in the order they hurt

1. **A Moxa is only an address.** The import makes an `Access Point`, never the box behind it, and
   `implemented by` is never created.
2. **The port is lost.** `scsparcsipmxa001:4003` is one serial line with four pumps on it. The hub
   stores `address` and `port` as text on each device. "Which devices are on that cable" and "which
   go dark if the whole box dies" are different questions, and only the second can be asked.
3. **Hosts and consoles have no home.** IOC `host:` is text. Consoles are not in the file at all.
4. **No topology and no addressing.** No switch, VLAN or subnet objects, so "what shares this
   uplink" cannot be asked.
5. **Shared infrastructure collides.** The NFS server is named by three beamlines, and object keys
   are unique across the installation. A second beamline creating "the same host" fails with
   *already exists in workspace…*.
6. **Site conventions are hard-coded.** `LOCAL_DOMAINS` lists `.lnf.infn.it` and `.infn.it`; ELI's
   hosts are `.int.eli-np.ro`, so an ELI hostname is never shortened and never matches.

---

## 3. Design principles

- **Three layers, kept apart.** *Equipment* is what exists. *Addressing* is what the network
  registry says about it. The *control path* is what the control system reaches. They fail
  differently and are owned by different people.
- **IT infrastructure is site-wide; the wiring is a beamline's own.** A host or a converter is one
  thing however many beamlines reach it. Which device is on which port is one machine's business.
- **Stated is not inferred.** A serial line is stated by the file (`server` + `port`). "That
  endpoint is a Moxa" is an inference, from a name that is a convention. The first is built; the
  second is marked and never overwrites what is known.
- **Beamline imports link to IT equipment; they do not create it.** Creating it from a config would
  make a second copy of what the IT registry owns, and would collide across beamlines.
- **Relations carry no attributes** (`from`, `to`, `type`, `created_at`). Anything with a
  property, such as a port number, a baud rate or a bus topology, has to be an object.

---

## 4. The model

```
   EQUIPMENT (what exists)          ADDRESSING (what the registry says)     CONTROL PATH (what is reached)

   Serial Converter  ◄─implemented by─── Access Point ◄──port of── Serial Line ◄──on line── Control Device
   Server                 │                  │  (beamline)          (beamline)                 (beamline)
   Workstation            │ described by     │ on segment
   Switch  ◄─uplinked to──┤                  ▼
                          ▼            Network Segment
                    Address Record       (VLAN / subnet)
                    (Registered node,
                     DHCP lease, DNS)
```

The existing shortcut, `Control Device → reached through → Access Point`, stays: it is what the
import builds today and it answers "which devices share this box". The path through `Serial Line`
answers the finer question.

### 4.1 Types

**Equipment** (global, `Asset` branch). Replaces the two flat types with a small tree:

```
Asset
└── IT Equipment (abstract)          hostname (indexed), fqdn, ip (multi), mac (multi),
    │                                firmware_version, management_url
    ├── Network Device (abstract)
    │   ├── Switch                   n_ports, is_managed, supports_poe
    │   ├── Router
    │   ├── Serial Converter         n_serial_ports, serial_modes (RS-232/422/485), tcp_port_base
    │   └── Media Converter
    └── Computing Node (abstract)
        ├── Server                   is_virtual, hypervisor, cpu, ram_gb, os, role
        └── Workstation              role (Operator console, Engineering, Kiosk, Test), os, console_group
```

`device_kind` disappears: the type says it. `tcp_port_base` records the convention that serial port
*N* is TCP port `4000 + N` (Moxa's default), so a `Serial Line` can derive its physical port once
somebody confirms the convention holds for that box. It is empty until then.

**Addressing** (global, new abstract root `IT Record` under `Item`):

| Type | Attributes |
|---|---|
| `Network Segment` | `vlan_id`, `cidr`, `gateway`, `purpose` (Control, Cameras, Magnets, Management, Office…), `is_dhcp` |
| `Address Record` | `record_kind` (Registered node, DHCP lease, DNS name, Ethernet configuration), `hostname`, `ip`, `mac`, `registered_on`, `owner` |

**Control path** (beamline, `Control Item` branch):

| Type | Attributes |
|---|---|
| `Serial Line` | `tcp_port`, `serial_port` (optional), `line_kind` (Single device, Multi-channel controller, Multi-axis controller, Multi-drop bus), `serial_mode`, `baud`, `framing` |
| `Access Point` (existing) | adds `endpoint_kind` (Serial converter, Host, Instrument, Camera, Unknown) and a note when it was inferred |

`line_kind` is read from the keys the file already uses on the devices: `channel:` is a
multi-channel controller, `axid:` a multi-axis controller, `id:`/`addr:` a multi-drop bus, a lone
device a single line. It is not a guess.

### 4.2 Relations

A **Serial Line** is a logical line, end to end: `Ethernet Cable` + `Switch` + `Serial Converter` +
`Serial Cable` (RS-232/422/485). It is `carried by` each hop (a series path, not `composed of`: one
hop stopping cuts the line, none merely degrades it). A configuration only names the converter, so
the importer relates the line to that; the cables and switches are added by hand or from a cabling
matrix, and the impact and root-cause walks then go through them. A switch carrying two lines is a
single explanation for symptoms on both. All cables are `Cable Run` children, with `from_asset` and
`to_asset` ends.

| Relation | From → to | Source |
|---|---|---|
| `on line` | Control Device → Serial Line | stated (`server` + `port`) |
| `port of` | Serial Line → Access Point | stated |
| `carried by` | Serial Line → each hop it passes through: `Serial Cable`, `Ethernet Cable`, `Switch`, `Serial Converter` | the converter from the config; the cables and switches added by a person |
| `implemented by` | Access Point → IT Equipment | resolved by hostname, IP or MAC |
| `described by` | IT Equipment, or any Asset with a network presence → Address Record | resolved, or from the registry |
| `on segment` | IT Equipment, Access Point, Control Network → Network Segment | registry or IT, not the config |
| `uplinked to` | IT Equipment → Switch | IT, not the config |
| `runs on` | IOC → Workstation, Server, or the instrument that runs it | stated by `host:`; else the cluster |

Cameras, Libera units and Ethernet power supplies keep their `Camera`, `Digitizer`, `Power Supply`
types and are `described by` an `Address Record` rather than gaining `hostname`/`ip` attributes,
which would appear on every pump.

### 4.3 A real case: `scsparcsipmxa001`

Four lines, fifteen devices, from the SPARC file:

| Line | Endpoint : port | IOC | Devices |
|---|---|---|---|
| Multi-channel | `scsparcsipmxa001`:4001 | `vac-kly01vpc` | W1KSIP03, W1GSIP01, W1DSIP01 |
| Multi-channel | :4002 | `vac-kly02vpc` | W2KSIP03, W2KSIP04, W2ASIP01, W2BSIP01 |
| Multi-channel | :4003 | `vac-gunvpc` | GUNSIP00, GUNSIP01, GUNSIP02, GUNNEG01 |
| Multi-channel | :4004 | `vac-gac1vpc` | GUNNEG02, AC1SIP01, AC1SIP02, AC2SIP01 |

- If the **box** dies: 15 pumps lose their readout. Today's graph already says this.
- If **one cable** (:4003) fails: 4 pumps. Today's graph cannot say this.

The walk is `GUNSIP01 → on line → :4003 → port of → Access Point → implemented by → Serial
Converter` (`Moxa NPort`, purchase order, rack, VLAN), and `Serial Converter → described by →
Registered Node`.

### 4.4 The hostname convention

INFN's page *Naming Convention DNS Elements – PROPOSAL –* (Confluence, space LDCG) defines a name
as four fields with no separator, lower case, a dash and never an underscore:

```
prefix(2) + facility/group + functionality/family + sequential(3 digits)
   sc          sparc            moxa                  002        →  scsparcmoxa002
   pw          sparc            co                    001        →  pwsparcco001
```

The prefix is the class of machine. It is the field the model uses:

| Prefix | Meaning (as the page gives it) | Catalogue type |
|---|---|---|
| `sc` | Serial converter (e.g. Moxa) | `Serial Converter` |
| `sw` | Switch | `Switch` |
| `pl`, `vl`, `dl` | Linux, physical / virtual / Docker | `Server` (`is_virtual` from `vl`/`dl`) |
| `pw`, `vw`, `dw` | Windows, physical / virtual / Docker | `Server`, or `Workstation` when the family is `co` (console control room), `nuc` or `pc` |
| `il` | iLO (management controller) | an `Address Record` of its host, not equipment of its own |
| `ns` | Storage device (NAS) | `Server`, `role` = storage |
| `cc` | Camera | `Camera` |
| `mv` `ps` `bd` `fd` `rd` `vd` `qd` `un` `sd` `dd` `da` `mp` `gd` | Device controllers by discipline: motor, power supply, beam instrumentation, fluid, RF, **vacuum**, cryogenic, undulator, safety/access, DAQ, DAC, machine protection/PLC, generic | Ethernet-native instruments: they keep their own type (`Digitizer`, `Power Supply`…) and are `described by` an `Address Record`; the prefix sets `argus_system` |

The facility field (`sparc`, `btf`, `flame`, `dante`, `tex`, `cg`…) is a routing key: it says which
beamline or group a machine belongs to without a lookup. The family field (`moxa`, `icpdas`,
`nuc`, `libera`, `cam`, `co`…) is a hint, not a vocabulary: real names use `mxa`, `chlmxa`,
`enea` and other variants, so the model reads the **prefix** and treats the family as text.

**What follows from it**

- `endpoint_kind` on an Access Point is read from the prefix, not from a guess about
  substrings. `sc` gives Serial converter, `cc` Camera, `pl`/`vl`/`pw`/`vw`/`dl`/`dw` Host, and the
  discipline prefixes Instrument. It stays marked as inferred and never replaces a value a person
  set.
- An earlier reading of mine grouped `vd…` names as virtual machines. They are **vacuum
  devices**; `vl`/`vw` are the virtual machines. The classification above supersedes it.
- The convention names the kind of machine. It does not give an address, so it does nothing for
  the **bare IPs** (86 of SPARC's 138 Access Points, and every BTF endpoint). Those are still
  classified only by the registry or a reverse lookup.

**How the real names fit**, measured on names taken from the four configurations and SPARC's
console inventory (ansible):

| Source | Names | Valid class prefix | Sequential is not 3 digits |
|---|---|---|---|
| SPARC `values.yaml` | 53 | 53 | 8 |
| BTF | 1 | 1 | 0 |
| EuAPS | 23 | 23 | 15 |
| ELI | 30 | 17 (56 %) | 4 |
| SPARC consoles (`hosts.yml`) | 7 | 7 | not counted |

Across all of those names the class mix is `cc` 21, `pl` 21, `sc` 18, `bd` 12, `pw` 9,
`dd` 8, `rd` 6, `gd` 4, `vd` 2. Two deviations are systematic and the importer has to tolerate
them rather than reject the name:

1. **ELI does not use it** for its power-supply hosts: 13 of 30 names are of the form
   `lel-mag-cpsu01.int.eli-np.ro`, `lel-mag-dpsu01`, `lel-mag-qpsu01`. They are inside the
   `.int.eli-np.ro` domain, so the domain, not the prefix, tells them apart, and the resolver must
   know that domain (section 8).
2. **The digit rule is loosely followed** (`…001` expected; 8 SPARC and 15 EuAPS names differ). The
   sequential field is therefore never parsed for meaning.

The page is titled *PROPOSAL*, and I read it through a text extract, not the page itself, so
whether emphasis in its tables marks "preferred" or "mandatory" is not something I can tell. The
measurements above are the evidence that the class prefix is what people actually follow.

---

## 5. Ownership, scope and keys

- **Types.** IT Equipment, Equipment Port, IT Record, and the shared parent types are global.
  Communication Path, Bus Segment, and Access Point belong to the workspace whose configuration
  names them.
- **Objects.** `it-infrastructure` owns IT Positions, IT Equipment, Equipment Ports, Address
  Records, and IT Installations. IT staff maintain them directly in ARGUS. Beamline workspaces own
  their Access Points, Paths, and Segments and may link to the visible IT Position.
- **Authority.** After the IT cutover, ARGUS is authoritative for the inventory record. DNS and
  DHCP remain operational authorities for live addressing and feed ARGUS. Insight is frozen at the
  migration watermark and retained only as an archive.
- **Identity.** ARGUS records use opaque stable uids and keys appropriate to their class. Insight
  object ids, `LNFMAC-…` keys, FQDNs, MACs, and former keys are labels and aliases. Matching is by
  governed strong identifiers, never by a mutable display key alone.
- **Paths and segments.** Paths use `<FAC>:PATH:<ioc>:<endpoint>[:<port>]`; shared downstream
  segments use `<FAC>:SEG:<endpoint>:<port>`. Equipment Ports belong to the installed unit.
- **Naming convention.** A conforming hostname supports an advisory classification claim. It is
  not physical identity and does not authorize a merge or an Installation.

---

## 6. How each thing gets in

| Object | Source | Kind | When |
|---|---|---|---|
| Communication Path, Bus Segment, `on path`, `enters at`, `continues on` | `values.yaml` | stated | default in the configuration import |
| Access Point | `values.yaml` | stated | already built |
| Access Point `assigned to` | resolver or configuration evidence | resolved or inferred | asserted once; reassignment retires the AP and creates a successor |
| endpoint kind or provisional IT Position | the class prefix of the DNS name; the structure of the endpoint for bare IPs | inferred | advisory ledger claim pending policy or review |
| IOC `runs on` | `host:`, else the cluster | stated | default |
| `implemented by`, `attached to` | derived through the AP's Position, the current Installation, and a compatible port match | derived | after the required facts are effective |
| Serial Converter, Server, Switch, IT Position, Installation | ARGUS IT inventory; initially migrated from Insight | manual or migration | owned by IT; Insight freezes at cutover |
| Address Record, later Network Segment | ARGUS IT inventory fed by DNS/DHCP | external continuing input | owned by IT |
| Workstation (consoles) | `hosts.yml` in each beamline's repository | external | a small reader for Ansible inventories |
| Switch topology, `uplinked to` | IT (LLDP, port tables) | external | not from any file here |

Two behaviour changes the model needs:

1. **The Access Point is always made.** In the baseline, when an address matches equipment in the inventory,
   the importer reuses the equipment *as* the Access Point and creates none (`access_points_linked`).
   The model wants the Access Point (beamline) and the equipment (site) as two objects joined by
   `assigned to` an IT Position. `implemented by` is derived from that Position's current
   Installation, so a beamline keeps its wiring across equipment swaps.
2. **The resolver looks across workspaces.** `NetworkIndex` reads only the importing workspace's
   own objects. It has to read the objects of global types visible from it, or the IT workspace is
   invisible to every import.

---

## 7. Mapping from the existing Insight types

This table is a **migration mapping**, to be confirmed against the exported schemas. It is not an
ongoing synchronization contract:

| Insight type | Becomes | Note |
|---|---|---|
| Converter | `Serial Converter` (or `Media Converter`) | which one needs an attribute I have not seen |
| Server | `Server` | |
| Camera | `Camera` (existing) | its IP goes to an `Address Record` |
| Registered Nodes, DHCP Nodes, DNS, Ethernet Configuration | `Address Record`, by `record_kind` | the resolver already treats them as records, not equipment |
| IP | `Address Record` or `Network Segment` | depends on what it holds |

The migration importer adopts the governed ARGUS catalogue type, preserves every Insight object id
and key as an alias, and produces a reconciliation report. After the IT cutover watermark, the
Insight stream is frozen and no longer authoritative.

---

## 8. What has to change in the code

The normative sequence is `asset-model-revision.md` §13. For the IT slice it means:

1. land the fact ledger, relation registry, Positions, Installations, and governed identity labels;
2. migrate `Serial Line` into Communication Path and Bus Segment, always create the Access Point,
   and assign it to a Position rather than reusing Equipment;
3. import Equipment Ports from the IT registry and derive `attached to` only from a unique,
   registry-backed, fully compatible match or a confirmed Installation-scoped port map;
4. make local domains configurable and keep DNS classification advisory until IT approves the
   convention;
5. migrate Insight IT schemas with aliases and reconciliation reports, then freeze them at the IT
   cutover watermark; DNS/DHCP and later LLDP remain continuing inputs;
6. add the Ansible inventory reader for Workstations when the consoles extension is activated.

---

## 9. Decisions for you, and what I don't know

**Resolved by the normative revision**

1. **Workspace:** dedicated `it-infrastructure`, staffed by IT; the catalogue holds definitions.
2. **Connectivity:** Communication Path + Bus Segment + Equipment Port replace `Serial Line`.
3. **Access Point:** always a separate control-plane record; its Position assignment is write-once.
4. **A `Compute Cluster` object?** The configuration gives only `k8sda.lnf.infn.it` and a
   namespace, today held as text on `Control Configuration`. Promoting it lets "the cluster is
   down" reach every IOC. Optional; I left it out of the model above.
5. **Consoles:** deferred extension, activated when the Ansible reader has an owner and query.

**Not verified**

- The **Insight IT schemas** (Converter, Server, Registered Nodes, and the rest): I know their names
  and the attributes the resolver reads, not their real attributes. The section 7 mapping is a
  guess until I see them. Running the Jira import into a scratch workspace, or an export, would
  settle it.
- **How binding the hostname convention is.** It is now sourced (section 4.4), but the page is
  titled *PROPOSAL*, I read a text extract of it, and ELI's power-supply hosts (13 of its 30 names)
  do not follow it. The design therefore reads the class prefix and treats everything else in the
  name as text. Whether `il`, `ns`, `sw` and `un` machines occur in the four configurations I did
  not see: none of the names measured carried them.
- That **serial port *N* is TCP port `4000 + N`** on every converter here. It is Moxa's default and
  the ports in the files fit it, and the EuAPS matrix now gives the port counts (8 and 16) that
  the ports used (up to 4008) stay within, but neither says that port *N* is `4000 + N`.
- **What the switches are.** The matrix names `switch` as the dependency of 27 cameras and every
  converter, and never identifies one. The IT registry still has to.
- Whether **BTF, EuAPS and ELI** keep console inventories like SPARC's.
