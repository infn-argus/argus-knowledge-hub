# ARGUS Knowledge Hub

Structured-knowledge backbone for **ARGUS** (*AI-based Retrieval-Grounded Understanding and
Supervision for Accelerator Operations*, INFN CSN5).

It manages the three bodies of structured knowledge an accelerator facility needs to keep
alongside its live machine data — **assets & spare parts**, **tickets/incidents** and
**controlled documentation** — and exposes them over a REST API so they can feed ARGUS'
hybrid knowledge layer (Knowledge Graph + vector retrieval).

Within the ARGUS work-package breakdown this is the data substrate for **WP3 — AI-Native
Services** (*Asset & Maintenance Management*, *Intelligent Incident Management*) and a source
for **WP2 — Hybrid Knowledge Layer**.

## Why it matters for ARGUS

The typed `Asset` + `Relation` model is already a property graph: a chain such as

```
EPICS IOC → serial port → Ethernet/serial converter → power supply → quadrupole magnet
```

is stored as typed relations between assets, which is exactly the topology ARGUS walks for
root-cause analysis. Documents carry a full revision workflow (draft → review → approved →
published → superseded/retired) so retrieval can be pinned to the *currently published,
currently valid* revision rather than to an arbitrary PDF.

## Components

| Path       | What it is                                                                 |
|------------|----------------------------------------------------------------------------|
| `backend/` | FastAPI + SQLAlchemy + Alembic on PostgreSQL. REST API, imports, auth/RBAC. |
| `webapp/`  | React + TypeScript + Vite + Tailwind operator/admin UI.                     |
| `k8s/`     | Kubernetes manifests (deployments, ingress, PVC) and deployment notes.      |

## Main capabilities

- **One application for assets, service and knowledge.** Every asset shows its tickets and the
  documents that apply to it (its own, its product model's and its type's); every ticket shows its
  equipment, the relevant procedures and what else is open on that equipment; every document shows
  where it applies and what is broken there. A single search (Ctrl/⌘ K) covers all three, and the
  operations cockpit opens on what needs attention. Served by `/v1/hub` (`search`, `overview`,
  `assets|tickets|documents/{uid}/context`), which fills each section only for callers who may read it.
- **Workspaces** with per-user, per-resource permissions (read/create/modify/delete/approve),
  OIDC sign-in (Firebase today, Keycloak-ready) plus API tokens for automation.
- **Types (schemas)** with inheritance: attributes are inherited down the hierarchy, and a type
  can be marked *global* to be referenced across workspaces.
- **Assets** with typed attributes (string/number/date/enum/reference/user/…), typed relations,
  attachments, comments, history and labels.
- **Tickets** with configurable types and a status workflow (New → In Progress → Pending →
  Resolved → Closed), priority, assignee and links to the affected asset.
- **Documentation** with the controlled revision workflow described above, confidentiality
  levels, authority levels and relations to assets/types/other documents.
- **Global values**: shared enumerations (status, priority, …) scoped per context.
- **Imports** from Jira Insight/Assets and from Git repositories, with saved, re-runnable
  import configurations and merge strategies (override / don't override / update-if-newer).
  Imports never delete: a re-import keeps values people edited since the last run (import
  snapshots) and records the commit it read. The old wipe-and-reimport strategy is retired.
- **Fact ledger and installations.** Sources (EPIK8s configuration, Insight) are ingested as
  revisions of claims in an append-only ledger; an authority policy decides which source owns
  each fact, people's confirmations stick, and every value on a record can show where it came
  from (*Provenance* tab). A position's history of installed units is kept as Installation
  records, with swaps and "what was installed on date X" queries. A revision that would retire
  too much is held, and conflicts, inferred facts and proposed installations wait in the
  *Review queue*. Served by `/v1/ledger` and `/v1/installations`.
- **Connectivity and attribution.** An address's Access Point is assigned to one position, once:
  when the configuration moves the address, the old Access Point retires with a successor and
  keeps its tickets, and "who used this address on date X" answers with a certainty around the
  handover. Bus segments attach to the port of whichever unit is installed now, but only on a
  unique, registry-backed, compatible match; safety-classed segments need a person to confirm
  the port for each new installation. Tickets are linked to the unit installed at incident time,
  and counts never add up the same ticket twice. Inference rules are versioned: a new meaning
  needs a new rule id, which a CI check enforces (`python -m app.ledger.rules`). Served by
  `/v1/access-points` and `/v1/ledger` (`segments`, `tickets`, `rules`, `rulesets`).
- **Migration from Jira and Insight, domain by domain.** A migration domain moves through the
  stages T0 Prepare … T5 Retire (*Migration to ARGUS*). While a domain is imported and shadowed,
  ARGUS holds it read-only (no dual write); at cutover its streams are frozen at the watermark W,
  and a reconciliation report compares the export manifest with ARGUS — records, comments,
  history, links, attachments by SHA-256, workflow states and users. The exit is signed only
  when every difference is resolved or explained and the criteria hold; ARGUS is then the
  system of record. Old Jira keys, Jira URLs, Insight keys and objectIds resolve through
  `/lookup/<key>`, or point to the archive when never migrated. Served by `/v1/domains`,
  `/v1/lookup` and `/v1/export` (JSON lines).
- **Identity.** Insight objects are bound by their objectId, so a re-keyed object stays the same
  record with its old key as an alias. Different source objects sharing a serial (per
  manufacturer), inventory number or MAC become a review item — merged by a person, never
  automatically — and once a scope is cut over, creating a duplicate is refused.
- **Restricted records.** A record or ticket classified `restricted:<class>` (costs, personnel,
  security incidents, safety investigations, sensitive designs) is absent from lists, search,
  counts, exports, MCP tools and the ledger views for anyone without that grant, and appears in
  graphs only as an anonymous node. Grants come from a role's `restricted` permissions or a
  token's `restricted_grants`.
- **Equipment lifecycle, custody and spares.** A unit's lifecycle moves only along allowed
  transitions (Installed follows from its installation); custodian and location keep their full
  history with who changed them and when; designated spares show whether they are available, and a
  position lists the spares that fit it (*Lifecycle & custody* tab). Served by `/v1/equipment`.
- **Controlled bulk changes.** Set an attribute on, or retire, many records at once: always
  previewed first, approved by a second person above 100 records, applied as one ledger batch and
  undone as one (*Bulk changes*). Plain bulk deletes above 100 records are refused. Served by
  `/v1/bulk-changes`.
- **Tamper-evident audit log.** The ledger's audit tables are append-only in the database itself
  (a trigger refuses UPDATE and DELETE). Each day is sealed with a SHA-256 digest chained to the
  previous day (`python -m app.ledger audit-digest`, run daily; keep the digests outside ARGUS);
  `python -m app.ledger verify-audit` finds the first altered day. Every record has an audit trail
  under *Provenance*. Restricted fields (an attribute definition with `"restricted": "<class>"`)
  are hidden, and kept intact on edit, for viewers without that grant.
- **Data integrity tools**: relink of unresolved references, and a report of missing
  references, dangling links and orphaned objects, with targeted cleanup actions.

## Design notes

- [The asset model revision](docs/asset-model-revision.md) — positions and installations, the fact
  ledger, the relation registry, identity reconciliation, and ARGUS as the system of record that
  replaces Jira/Insight domain by domain. The implementation follows its plan (§13); the unified
  hub and the P0 import fixes are the first increment; the S1 vertical slice (fact ledger,
  authority policy, installations, review queue, Access Points, port mapping, ticket
  attribution, rule versions; acceptance tests A1–A32) is the second; the transition and
  readiness gates (A33–A41: cutover, identity, restrictions, lookup, reconciliation) the third.
- [Object schema design for a large-scale accelerator](docs/asset-schema-design.md) — the
  type catalogue (122 types over four planes), the relation vocabulary, composite elements such
  as a screen station, and how a beamline's EPIK8s control configuration and a EuPRAXIA-style
  product breakdown both come in as equipment rather than as files.
- [The knowledge graph for root-cause analysis](docs/knowledge-graph-design.md) — what each
  relation means for a failure (which way it travels, and whether the dependent loses its readout,
  its function, a permit or part of itself), impact and root-cause analysis over it
  (`GET /v1/graph/impact`, `POST /v1/graph/root-cause`, `GET /v1/graph/blast-radius`, and the
  `impact_analysis`, `root_cause_analysis` and `single_points_of_failure` MCP tools), what the
  configurations give, and what the graph cannot yet do.
- [The element panorama](docs/element-panorama.md) and [the IT model](docs/it-model-design.md) —
  what the utility matrices say next to the control configurations, and where switches, hosts and
  serial converters live.
- [A local Keycloak for testing multi-workspace users](docs/oidc-dev-setup.md) — how one person
  ends up with different rights in different workspaces (`RoleBinding`, not a PAT, which can only
  ever be one workspace), the dev-only identity provider that proves it end to end, six test users
  covering the permission model, and what's simulated about a future GODiVA-backed sign-in versus
  what isn't.

## Development

### Everything at once, with Docker Compose

The quickest way to a working hub on your own machine: database, API and web UI, with
migrations applied on start.

```bash
docker compose up -d --build --wait
docker compose exec api python scripts/create_token.py dev "Local development" local
```

The second command prints an API token **once**. Open <http://localhost:5173>, give the API
address `http://localhost:8080` (plain `http`, the API does not speak TLS) and that token.

- `TOKEN_PEPPER=dev-only` is a secret mixed into token hashes, **not** a token. Use the one the
  script prints.
- Something already on 8080 or 5173, such as a dev server started by hand? Move the published
  ports: `API_PORT=18080 WEB_PORT=15173 docker compose up -d --build --wait`.
- Load the accelerator object types. In a hub with one workspace, `all` puts everything in it:
  `docker compose exec api python scripts/seed_asset_types.py all dev`.
  With several beamlines, the shared types go in one catalogue workspace, once, and each
  beamline gets only its own, hanging from them:
  `... seed_asset_types.py global catalogue`, then
  `... seed_asset_types.py beamline sparc --catalogue catalogue`.
  Each workspace has to exist first (`create_token.py <id> "<name>"` creates it), and
  `--dry-run` shows what would happen without writing.
- Read a beamline's control configuration into a workspace, as objects of those types:
  `docker compose cp ../epik8-sparc/deploy/values.yaml api:/tmp/sparc.yaml`, then
  `docker compose exec api python scripts/import_epik8s.py sparc /tmp/sparc.yaml`
  (`--dry-run` reads it in full and keeps nothing). Add `--infer-elements` to also make what the
  channels drive, which the file never lists: the ion pumps, magnets and their supplies, cameras,
  BPM electronics, LLRF and modulator units, motor axes, screens (a flag and the camera its name
  pairs it with) and mirrors. They are inferences, marked `inferred`, and a person's later edits
  survive a re-read. The catalogue gained a `Mirror` type for this: run
  `scripts/seed_asset_types.py beamline <workspace> --catalogue <catalogue>` again on a workspace
  seeded before.
  Each Access Point also says what kind of endpoint it is, and each device on a port of a serial
  converter is on a Serial Line. Add `--it-workspace it-infrastructure` (a workspace made with
  `create_token.py`) to make the converters, servers and consoles the hostnames name, once, in that
  site-wide workspace, flagged global; each beamline's Access Point is `implemented by` them.
- State lives in two named volumes and survives `docker compose down`;
  `docker compose down -v` wipes it.

The defaults in `docker-compose.yml` are public and meant for one machine. Never reuse them
anywhere that holds real data.

### Running the pieces by hand

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app
export TOKEN_PEPPER=dev-only
alembic upgrade head
python scripts/create_token.py dev "Local development" local   # prints an API token once
uvicorn app.main:app --reload --port 8080
```

This needs a reachable PostgreSQL at `DATABASE_URL`; `GET /health` answers 500 when it is not.
Run `create_token.py` from `backend/` and under the same `TOKEN_PEPPER` the server uses, or
the token it prints will not be accepted.

The tests use the same environment plus `IMPORT_SECRETS_KEY` (any Fernet key) and a database
they may write to: `pytest tests`. Two drawing tests also need the `dwg2dxf` converter on `PATH`.

Web app:

```bash
cd webapp
npm install
npm run dev
```

The web app asks for the API base URL (`http://localhost:8080` when running locally) and either
a personal access token or a Google sign-in at first launch.

### Environment variables (backend)

| Variable              | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `DATABASE_URL`        | PostgreSQL connection string.                                   |
| `TOKEN_PEPPER`        | Pepper for hashing API tokens (required).                       |
| `IMPORT_SECRETS_KEY`  | Key used to encrypt stored import credentials at rest.          |
| `ATTACHMENTS_DIR`     | Where uploaded files are stored (defaults to `/data/attachments`). |
| `OIDC_ISSUER` / `OIDC_JWKS_URI` / `OIDC_AUDIENCE` | OIDC token verification.            |
| (worker) | `python -m app.ledger derive-worker` runs queued derives when `LEDGER_USER_EDIT_DERIVE=manual`; `python -m app.ledger backfill-checksums` records SHA-256 for older attachments. |
| `LEDGER_USER_EDIT_DERIVE` | How derived links follow a user's edit: `background` (default), `inline`, or `manual` (left for a worker). |

## Deployment

See [`k8s/README.md`](k8s/README.md). Images are built and pushed with `backend/deploy.sh
<version>` and `webapp/deploy.sh <version>`, then rolled out with `kubectl set image`.

## License

See the INFN project terms; contact the maintainers for reuse outside INFN.
