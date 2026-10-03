"""Portable ARGUS archives and the Git portability project (docs/export-import-design.md).

Four mechanisms are kept apart:

1. **Disaster-recovery backup** — `app.ledger.ops` (pg_dump, WAL, attachments). Same deployment,
   infrastructure-specific, never in Git.
2. **Full portable archive** — `argus-archive/1` with mode `full`: every workspace, the ledger,
   catalogue, governance, identities and blobs, enough to rebuild ARGUS elsewhere.
3. **Selective workspace package** — mode `workspace`: chosen workspaces plus an explicitly decided
   dependency closure (`closure.py`).
4. **Git portability project** — `gitrepo.py`: the archive's manifest, schemas, catalogue,
   governance and immutable chunks committed and tagged with a signature; blobs are
   content-addressed artifacts outside Git (`artifacts.py`).

What is authoritative travels as the ledger's audit rows and the domain records; projections travel
only as data to compare against after the importer has rebuilt its own (`importer.rebuild`). Exact
ARGUS-to-ARGUS import is deterministic: no LLM is involved anywhere in this package.
"""

FORMAT = "argus-archive/1"
FORMAT_MAJOR = 1
REPOSITORY_LAYOUT = "argus-portability/1"
