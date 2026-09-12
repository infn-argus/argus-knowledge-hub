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
  import configurations and merge strategies (override / don't override / update-if-newer /
  wipe-and-reimport).
- **Data integrity tools**: relink of unresolved references, and a report of missing
  references, dangling links and orphaned objects, with targeted cleanup actions.

## Development

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app
export TOKEN_PEPPER=dev-only
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

Web app:

```bash
cd webapp
npm install
npm run dev
```

The web app asks for the API base URL and either a personal access token or a Google sign-in
at first launch.

### Environment variables (backend)

| Variable              | Purpose                                                        |
|-----------------------|----------------------------------------------------------------|
| `DATABASE_URL`        | PostgreSQL connection string.                                   |
| `TOKEN_PEPPER`        | Pepper for hashing API tokens (required).                       |
| `IMPORT_SECRETS_KEY`  | Key used to encrypt stored import credentials at rest.          |
| `ATTACHMENTS_DIR`     | Where uploaded files are stored (defaults to `/data/attachments`). |
| `OIDC_ISSUER` / `OIDC_JWKS_URI` / `OIDC_AUDIENCE` | OIDC token verification.            |

## Deployment

See [`k8s/README.md`](k8s/README.md). Images are built and pushed with `backend/deploy.sh
<version>` and `webapp/deploy.sh <version>`, then rolled out with `kubectl set image`.

## License

See the INFN project terms; contact the maintainers for reuse outside INFN.
