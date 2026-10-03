# Export, import and the Git portability project

ARGUS is becoming the system of record for assets, documents and tickets. This document designs
its **institutional escape hatch**: a way to rebuild the authoritative information somewhere else,
without the original deployment, with ledger history, provenance, catalogue versions, permissions,
classifications and attachments intact. It also says, for every part, how far it has got.

The normative rules are in [`asset-model-revision.md`](asset-model-revision.md) §25. Operating
procedures are in [`operations.md`](operations.md) ("Portable exports and the Git portability
project"). Compatibility guarantees are in [`api-policy.md`](api-policy.md) ("Archive format").

## 0. Status

Each capability is one of:

* **Proposed** — designed here, not built.
* **Implemented** — in the code (`backend/app/portability/`), not yet covered by an automated test.
* **Tested** — implemented, and covered by `backend/tests/test_portability.py`.
* **Production-approved** — tested, and approved for production use by the institution.

**Nothing in this document is production-approved yet.** §19 lists what must happen first.

| Capability | Status |
|---|---|
| `argus-archive/1` format: manifest, NDJSON+zstd chunks, blob manifest, checksums, Ed25519 signature | Tested |
| JSON Schemas of the manifest, envelope, blob manifest and every family | Tested (generated, published) |
| Consistent ledger watermark (lock, exported snapshot) | Tested (A27) |
| Export modes `workspace`, `full`, `incremental`, `evidence-only` | Tested |
| Export mode `backup-reference` | Proposed (refused with `not_generated`) |
| Dependency closure with explicit outcomes | Tested (A25) |
| Restricted classes and fields left out, leak-free manifest | Tested (A18) |
| Secret scanning of rows and committed files | Tested (A19, A20) |
| Content-addressed artifact store, directory backend | Tested (A3, A4) |
| S3-compatible and OCI-artifact stores | Proposed |
| Encryption of chunks and blobs per recipient | Proposed |
| Git publication: signed commit, signed annotated tag, no force push | Tested |
| Quarantine fetch: signed tag or signed commit only, hostile-tree checks, no checkout | Tested (A5, A7, A21) |
| Moved-tag detection | Tested (A5) |
| Git LFS pointers resolved only from an independent store | Tested (A29) |
| Verification (checksums, signature, chunks, blobs, limits) | Tested (A6, A22) |
| Import modes `clone`, `merge`, `evidence`; `restore` (empty instance, identity adopted) | Tested (`restore`: dry-run gate only) |
| Import mode `selective` | Implemented (loads the archive's workspaces; choosing a subset is proposed) |
| Dry run with merge outcomes | Tested (A12–A14) |
| Staged, idempotent, resumable load; exact discard | Tested (A8, A9, A23) |
| Rebuild of projections from the ledger, and comparison with the exported ones | Tested (A2) |
| Signed reconciliation report | Tested |
| Committing reconciliation reports to the repository | Proposed (setting reserved) |
| Increments: chain, order, equality with a checkpoint | Tested (A10, A11) |
| Periodic restore drill | Tested (A30); its schedule is operations' |
| API with state machines, audit, separation of duties | Tested |
| Web user interface (Administration → Portability) | Implemented; checked by hand in a browser (export, publish, evidence import, blocked clone, discard), no automated UI test |
| Step-up authentication for high-risk exports | Proposed (§15) |
| Foreign and legacy schemas through AI-assisted mapping | Proposed (§11) |
| Catalogue and policy changes reviewed in Git, then activated | Proposed (the repository shows them; activation from Git is not built) |
| Merge into an instance whose audit days are already sealed | Proposed (§19, blocker) |

## 1. Principles

1. The append-only ledger and the immutable domain history are authoritative.
2. Projections, indexes and derived graph edges can be rebuilt; they travel only to be compared.
3. Import and export never silently overwrite history, never bypass authority policies, and
   never disclose restricted information.
4. Git versions, reviews and distributes. It is not the database, not the operational backup, and
   not the system of record.
5. ARGUS-to-ARGUS restoration is deterministic and needs no LLM.
6. AI may help only to map a foreign or legacy schema, under the AI Intake rules.

## 2. Four mechanisms, kept apart

| | Disaster-recovery backup | Full portable archive | Selective workspace package | Git portability project |
|---|---|---|---|---|
| What | `pg_dump`, WAL archive, attachments tarball | `argus-archive/1`, mode `full` | `argus-archive/1`, mode `workspace` | a repository of manifests, schemas, catalogue and governance views, immutable chunks, checksums, signatures |
| Restores | the same deployment, to a moment | ARGUS on another compatible deployment | chosen workspaces and their decided dependencies | nothing by itself: it carries archives for review and distribution |
| Format | infrastructure-specific | open, documented, versioned | the same | Git |
| In Git | never | its manifest and chunks, yes; its blobs, as references | yes | — |
| Code | `app.ledger.ops` | `app.portability` | `app.portability` | `app.portability.gitrepo` |
| Doc | operations.md, "Point-in-time recovery" | this document | this document | this document, §9 |

The older `argus-export/1` bundle (`app.ledger.portability`, `/v1/export`) stays. It is an
open-format view of what a viewer may see. It is not an archive: it carries no watermark,
signature or claims, and its projections are not compared.

## 3. Export modes

| Mode | Scope | Labels |
|---|---|---|
| `full` | every workspace not being staged by an import | complete when no restricted class or field is left out |
| `workspace` | chosen workspaces plus the decided closure (§8) | selective |
| `incremental` | the base export's scope; ledger rows of the window `(base W, W]`; record state at `W` | incremental (selective when its base is) |
| `evidence-only` | as `workspace`, meant to be read, not activated | selective, evidence-only |
| `backup-reference` | names a disaster-recovery backup (its manifest hash and location) | *proposed* |

**The watermark.** A short transaction takes `SHARE` locks on the ledger's sequenced tables.
This waits for every transaction already writing to them and holds new writers back for
milliseconds. It then reads each table's highest `seq` and exports its snapshot. A read-only
`REPEATABLE READ` transaction imports that snapshot, and the lock is released. As a result:

* every row with `seq <= W` is committed and visible;
* no later transaction can take a `seq <= W`;
* records (assets, tickets, documents) are read at the same instant.

`W` is recorded per table, together with the time. Its label is the sum of the per-table
high-water marks, which is monotonic as long as no workspace is purged.

## 4. The archive format, `argus-archive/1`

A checkpoint is a directory:

```
<export-id>/
  manifest.json                       the manifest (§4.2)
  workspaces.ndjson                   the workspaces in scope (ids), for a reader without zstd
  catalogue-types-000001.ndjson.zst   one or more chunks per family: <group>-<family>-<n>
  identity-identities-000001.ndjson.zst
  access-…  governance-…  records-…  ledger-…  projection-…
  blobs.manifest.ndjson               one line per blob (§7)
  relation-registry.json              the relation registry and semantics, stable form
  reconciliation.json                 the exporter's counts, hashes and invariant summary
  checksums.sha256                    sha256sum format, every file above
  signature.json                      Ed25519 over the checksums and the manifest
```

The layout sketched in the request (`records-000001.ndjson.zst`, `ledger-000001-010000.ndjson.zst`,
`provenance-000001.ndjson.zst`, `identities.ndjson`) maps onto this. Each family has its own
chunks, named by group and family. The sequence range of a ledger chunk is in the manifest
(`first`, `last`) rather than in its name. Provenance is the ledger group.

### 4.1 Chunks

Each line of a chunk is an envelope, `{"f": <family>, "k": <key>, "d": <row>}`:

* JSON with sorted keys and no insignificant whitespace;
* UTF-8;
* compressed with zstd at level 10, in a single thread.

The same rows therefore always give the same bytes. `k` is the row's natural key, or the exporting
instance's `seq` for sequenced families. A chunk holds at most 50 000 rows. A file is written once
and never rewritten.

### 4.2 The manifest

`format/manifest.schema.json` defines the manifest. It records:

* the format and its major version;
* the export id and mode;
* labels: `complete`, `selective`, `incremental`, `evidence_only`, `signed`, `encrypted` and
  `artifact_complete`;
* the ARGUS application version, the database schema (the alembic head) and the exporting
  instance's identity;
* the repository name, as `repository`;
* the workspaces;
* the watermark (per table, label, time);
* the base export and its watermark, for an increment;
* versions: the active policy, the rules lock hash, the relation registry hash and the workflows
  hash;
* the creation time, the requester and the approver;
* per family: group, authoritative or not, row count, SHA-256 and chunks;
* blob count and total size;
* included and excluded classifications;
* dependencies and their outcomes;
* an invariants summary;
* encryption (none yet);
* the signature key id;
* the capabilities an importer needs.

**What the manifest cannot hold.** The commit and tag that publish a checkpoint can't be inside
it, because a commit cannot contain its own hash. They are recorded in three places instead:

* the signed tag names the commit;
* the tag message names the manifest's path and SHA-256, the export id and the previous tag;
* ARGUS records commit, tag, tag object and repository identity on the export and on every import
  (`/provenance`).

### 4.3 Record families

Families are an allow-list (`app/portability/families.py`). Load order: catalogue, identity,
access, governance, records, ledger.

| Group | Families | Notes |
|---|---|---|
| catalogue | `types`, `icons` | the scope's own types, the shared types its records use, and their ancestors |
| identity | `identities` | uid, OIDC subject, directory DN, e-mail, display name, source, active. Never credentials |
| access | `workspaces`, `roles`, `memberships`, `role_bindings` | ownership, default access, visibility |
| governance | `policies`, `rulesets` | authority policies and the protected predicates they name; rule sets |
| records | `assets` (Positions, Equipment, Installations, Product Models, Locations, …, in every status, tombstones included), `relations` (asserted only), `asset_comments`, `asset_history`, `asset_labels`, `asset_tickets`, `tickets`, `ticket_comments`, `ticket_history`, `ticket_links`, `ticket_watchers`, `documents`, `document_revisions` (approvals, supersession), `document_relations`, `attachments`, `workflows`, `migration_domains` | |
| ledger | `streams`, `source_revisions` (content as a blob), `claims`, `claim_events`, `revision_events`, `decisions`, `status_events`, `identity_events`, `record_events`, `conflict_events`, `migration_map`, `reconciliation_reports` | the authority |
| projection | `p_fact_state`, `p_identity_bindings`, `p_conflicts`, `p_derived_relations`, `p_ticket_links`, `p_stream_heads` | **not authoritative**: compared after rebuild, never loaded |

Jira and Insight keys, ids and URLs are attributes and source references (`argus_source_key`,
`argus_source_url`, `insight:object:…`). They travel as they are.

## 5. What never leaves ARGUS

The following have no family, so they cannot be selected:

* passwords;
* access, refresh and identity tokens;
* personal access tokens and API keys (`api_tokens`);
* model-provider and import credentials (`llm_configs`, `import_configs`);
* application settings;
* field-client devices and their push tokens;
* sessions;
* idempotency keys;
* upload sessions;
* notifications, escalations, caches, search and knowledge indexes, queues and locks.

On top of the allow-list, every row is scanned for credential formats and for credential-named
fields holding credential-like values (`secret_scan.py`). A finding fails the export before anything
is written to Git. The report says where, never the value. Every text file is scanned again before
the commit.

## 6. Restricted information

* An export names the restricted classes it includes. Including any makes the export high-risk
  (§15).
* A record whose class is not included is left out entirely. So is every row that names it:
  claims and claim events about it, decisions, status, identity and record events, relations,
  comments, attachments, fact state. Fields restricted for a type are removed from included
  records, along with claims, decisions and fact state on those predicates.
* Rows naming a left-out record form one dependency, `restricted_reference`, whose only outcomes
  are `exclude_referrers` and `block`. It is never decided silently. In the manifest, which every
  repository reader sees, it appears without counts or examples (A18).
* The manifest states which classes were left out, and labels the archive not `complete`.
* **Git has repository-level access, not record-level access.** Restricted and unrestricted
  exports must not share a repository unless every reader is entitled to everything in it. Highly
  restricted material belongs in a separate repository, or in encrypted artifacts (proposed, §7).
  Removing a file from a later commit does not remove it from history.

## 7. Blobs and artifacts

Attachments, icons and source-revision contents are stored as content-addressed artifacts:

```
sha256:<digest>  →  argus-artifacts://<store>/sha256/<digest>
```

A row holds `"sha256:<digest>"` in place of its path or bytes. `blobs.manifest.ndjson` records,
for each blob:

* the digest and size;
* the MIME type;
* the classification;
* encryption (none yet), recipients and the retention class;
* the locator;
* every row that references it.

The **directory store** is implemented: a mounted institutional volume, or a staging area that
operations synchronizes to object storage. Artifacts are written once (mode `0444`) and verified on
every fetch.

*Proposed:*
* an S3-compatible store (presigned, short-lived read URLs; Object Lock for retention);
* signed OCI artifacts (an `oras` push of the checkpoint's blobs, with a signature, e.g. cosign);
* per-recipient encryption (age or OpenPGP), with the recipients and key ids in the blob manifest.

Signed OCI or encrypted archive artifacts are preferred over Git LFS. LFS is accepted only for a
file whose object is independently recoverable: the verifier resolves an LFS pointer from a
configured artifact store by its SHA-256, and fails with `missing_lfs_object` otherwise (A29).

Cloning the repository and fetching every locator the blob manifest names is sufficient to verify
and rebuild a checkpoint (A28).

## 8. Dependency closure

Each reference from the scope to something outside it is a dependency. Dependencies are grouped by
rule and by the workspace holding the target:

| Rule | Example |
|---|---|
| `merge_survivor` | a tombstone needs its survivor |
| `relation_endpoint` | an asserted relation needs both endpoints |
| `derived_endpoint` | an Installation's edges need its Position and Equipment |
| `ticket_subject`, `ticket_involves`, `ticket_link` | a ticket needs its subject |
| `document_subject`, `document_relation` | a document's subject and links |
| `claim_subject` | a claim of an exported stream about a record elsewhere |
| `foreign_claims` | another workspace's stream asserts facts about an exported record |
| `restricted_reference` | §6 |

The outcomes are `include_workspace`, `external_reference`, `exclude_referrers` (restricted only)
and `block`. Generation refuses while any dependency has no outcome, an invalid outcome, or
`block`. `include_workspace` adds the workspace and computes its closure in turn, until it settles.

These are applied automatically and recorded in the manifest:

* `catalogue`: types and their ancestors;
* `actor`: people named by rows travel as historical identity references;
* `subject_decisions`: decisions about an exported record, wherever recorded.

Proposed refinements:

* an anonymized-actor outcome, which replaces a person's display data with a pseudonym while
  keeping the uid;
* `include` at record rather than workspace granularity.

## 9. The Git portability project

```
argus-portability/
  README.md  VERSION  .argus-portability.json        (repository id, layout, creating instance)
  format/      manifest.schema.json  record.schema.json  ledger.schema.json  blob-manifest.schema.json
               families/<family>.schema.json
  catalogue/   types.yaml  attributes.yaml  units.yaml  enumerations.yaml  relations.yaml
  governance/  authority-policy.yaml  workflows.yaml  retention-policies.yaml
  mappings/    jira-insight/  legacy-inventory/  foreign-schemas/
  exports/checkpoints/<export-id>/   (§4)
  tools/       validate  inspect  dry-run  import  reconcile
```

`catalogue/` and `governance/` are reviewable views regenerated from each checkpoint. Changing them
activates nothing (activation from Git is proposed). The tools:

* `validate` and `inspect` verify a checkpoint without ARGUS;
* `dry-run`, `import` and `reconcile` only point to ARGUS's own commands;
* ARGUS never runs anything from a repository.

**Rules.**

* **Identifying an export.** An export is identified by a commit and a signed annotated tag, never
  by a branch:

  ```
  export/full/<date>@ledger-<W>
  export/workspace/<workspace>[+n]/<date>@ledger-<W>
  export/increment/<full|workspace>/<date>@ledger-<W>
  ```

  Increments have their own prefix because an increment and a checkpoint can share a watermark.
* **Signing.** One commit per export. It is SSH-signed (Ed25519) with the same key as
  `signature.json`, and pushed without force.
* **Immutability.** A checkpoint directory that already exists is refused (`immutable`). Increments
  add new directories and never rewrite old ones. A periodic full checkpoint is just another
  directory, and the chain before it stays.
* **Incremental chains.** Each increment names its base and watermark in the manifest, and its
  previous tag in the tag message. The importer refuses an increment whose base is not the last
  export applied here from the same origin (`out_of_order`), and one whose previous tag is not an
  ancestor of its commit (`missing_commit`).
* **No Git merges.** Ordinary Git merges never resolve ledger or identity conflicts; ARGUS's dry run
  does.
* **What import accepts.** Only a signed export tag, or a signed commit named by its full hash
  (A7).
* **Protecting the repository.** These are settings of the Git server (operations.md):
  * protected tags `export/*`, which cannot be deleted or moved;
  * a protected `main` with no force push;
  * reviewers for `catalogue/`, `governance/` and `mappings/` through code owners;
  * short-lived credentials.
* **Moved tags.** ARGUS remembers the commit and tag object of every tag it imported, and refuses
  the tag if it has moved (`moved_tag`, A5).
* **Continuous integration.** *Proposed:* CI on the repository would run `tools/validate` on new
  checkpoints, check schemas, manifests, checksums, signatures, closure and mapping-profile
  compatibility, and reject unsigned tags.

**What goes in Git.** Schemas and documentation; catalogue, attribute, enumeration, unit and
relation definitions; policies and workflows; mapping profiles; manifests, checksums and
signatures; reconciliation and invariant reports; compressed immutable NDJSON chunks; references
to blobs.

**What never goes in Git.** Database backups and WAL; photos, videos, PDFs and document packages;
object-storage contents; secrets, tokens, credentials and private keys; temporary uploads, caches,
indexes and queues.

## 10. The import pipeline

| # | Step | Where | Status |
|---|---|---|---|
| 1 | Register repository and ref (a registered name; never a URL from the caller) | `create_import` | Tested |
| 2 | Fetch into quarantine with read-only credentials | `fetch_into_quarantine`, a bare repository, no checkout | Tested; credential injection proposed |
| 3 | Reject unsigned, lightweight, branch or unexpected input | `fetch_into_quarantine` | Tested |
| 4 | Verify repository identity, commit and tag signatures | `verify-tag`, `verify-commit` against allowed signers; identity file and root commit | Tested |
| 5 | Parse and validate the manifest | `verify.verify` | Tested |
| 6 | Retrieve artifacts into quarantine | `DirectoryStore.fetch` | Tested |
| 7 | Verify checksums, sizes and signatures | `verify.verify` | Tested |
| 8 | Decrypt under an authorized session | — | Proposed |
| 9 | Format and importer compatibility | required capabilities; unknown families or columns refused | Tested |
| 10 | Deterministic archive-format migrations | `verify.MIGRATIONS` (empty: format 1 is the first) | Implemented |
| 11 | Validate catalogue, policies, workflows, relations | dry run: type conflicts; governance gated in merge | Tested |
| 12 | Calculate dependency closure | dry run: references neither here nor in the archive | Tested |
| 13 | Complete dry-run report | `importer.dry_run` | Tested |
| 14 | Approvals | `approve_import`; a second person for merge, restore and restricted content | Tested |
| 15 | Load catalogue and governance | `importer.execute` | Tested |
| 16 | Workspace and identity mapping | `decisions.workspace_map`; known people kept as they are | Implemented (map), tested (identities) |
| 17 | Load ledger rows idempotently | the row map, by origin, family and source key | Tested |
| 18 | Import blobs through quarantine | blobs copied from quarantine, content-addressed | Tested |
| 19 | Attach blobs atomically | written before the row that names them | Tested |
| 20 | Rebuild projections, derivations, indexes | `importer.rebuild` (bindings, heads, `engine.rebuild`, event-sourced conflicts) | Tested; the knowledge index (RAG) is rebuilt by its own job |
| 21 | Run all invariants | `invariants.report` | Tested |
| 22 | Compare counts and hashes with the manifest | `importer.reconcile`, row by row | Tested |
| 23 | Produce and sign the reconciliation report | `_sign_report` | Tested |
| 24 | Commit the report to an approved location | — | Proposed |
| 25 | Finalize or discard | `finalize`, `discard` | Tested |

**Staging.**
* Workspaces an import creates carry `import_state = staging`. Nobody can open them,
  administrators included, until finalization.
* Shared types whose owner the target lacks get a stub owner workspace, staged the same way.
* Merging into an existing workspace is visible while staged. It is undone exactly by a discard.

**Resumption.** Each chunk is one step. A finished step is committed with the import's checkpoint
list, so an interrupted import resumes from there (A9). Replaying a step changes nothing, because
rows are found through the row map or by their key.

**Discarding.** A discard removes exactly what this import wrote, newest first, audit rows included
(the sanctioned purge), then its staged workspaces. Active state is left as it was (A23).

## 11. Import modes and merge outcomes

| Mode | What it does |
|---|---|
| `restore` | into an empty instance (the dry run refuses otherwise); every uid and the history kept; the instance adopts the archive's instance identity at finalization |
| `clone` | uids and provenance kept; this instance keeps its own identity |
| `merge` | into an instance with its own data; never replaces; governance families are loaded only by decision (`governance: load`) |
| `selective` | the archive's workspaces into an instance that has other work. Choosing a subset of an archive's workspaces is proposed |
| `evidence` | verified and kept read-only in the evidence store; rows browsed from the archive (`/evidence/{family}`); no projection, no active record (A24) |

Merge outcomes:

| Situation | Outcome |
|---|---|
| identical row | skip, recorded in the row map |
| export already applied from this origin | the whole import is recognized as identical history and changes nothing (A8) |
| next increment of the chain | resume the chain |
| new row | create |
| same key and origin, unchanged here since the last import | update (an increment) |
| same uid, divergent content | block (A12) |
| the same immutable external identifier (serial, MAC, source key) on another record | an identity candidate in the dry run; after import the identity engine opens a candidate, never a merge (A13) |
| same type id, same definition | reuse |
| same type id, another definition | a catalogue conflict to review; never overwritten (A14). Proposing a new type version is proposed |
| reference neither here nor in the archive | block; by decision `unresolved_references: defer`, left unresolved (nullable) or left out (not nullable), and listed in the reconciliation |
| person not known here | created as a historical reference; actor strings in the ledger are kept verbatim (A26) |
| person known here | kept as is |

## 12. Projections

The ledger is the portable authority. After loading, the importer:

* replays identity bindings from identity events and stream heads from revision events;
* runs the engine's own rebuild (fact state, managed attributes, record status, derived relations,
  conflicts, identity candidates);
* replays the conflicts the engine keeps only as events;
* restores record timestamps, which are not ledger state.

It then compares every projection family the export carried with what it rebuilt, ignoring when
a projection row was derived. Finalization is blocked on any difference. A projection from the
archive is never written to the target.

Two observations from building this:

* The engine's rebuild re-detects identity candidates, and so writes new conflict events. The
  reconciliation reports them as `events_written_by_rebuild`.
* A ticket's record links and its occurrence-source attribute are derived (`app.ledger.tickets`).
  The ticket links travel as the projection `p_ticket_links`. A ticket written without the derive
  step makes the comparison fail, which is the intended signal: the source's projection was stale.

## 13. Increments

* An increment states the ledger as a strict delta. Sequenced rows in `(base W, W]`; claims and
  source revisions are first referenced in that window.
* An increment states records as their state at `W`. Rows of the same origin are updated when
  nobody here has changed them since. Set-valued families (memberships, role bindings, asserted
  relations, ticket links and watchers, document relations) are restated whole, and what the same
  origin wrote earlier and is now absent is removed. Deletion in the ledger is always an event
  (retirement, withdrawal, supersession).
* Applying the complete chain gives the same authoritative state as a checkpoint at the final
  watermark (A10).
* *Proposed:* record deltas by modification time, to make increments smaller.

## 14. API and state machines

Under `/v1/portability/`. The request sketched `/v1/exports` and `/v1/imports`, but `/v1/imports`
already belongs to the Jira, Insight and Git import jobs.

```
POST /v1/portability/exports                      request (and analyse)
GET  /v1/portability/exports[/{id}]
POST /v1/portability/exports/{id}/decisions       dependency outcomes; analyses again
POST /v1/portability/exports/{id}/approve
POST /v1/portability/exports/{id}/generate
POST /v1/portability/exports/{id}/publish-git
GET  /v1/portability/exports/{id}/manifest
POST /v1/portability/exports/{id}/download-token  10 minutes, HMAC, audited
GET  /v1/portability/exports/{id}/download?token= the checkpoint as a tar, audited
POST /v1/portability/exports/{id}/revoke

POST /v1/portability/imports                      register (repository name, ref, expected commit)
GET  /v1/portability/imports[/{id}]
POST /v1/portability/imports/{id}/fetch-git | upload | verify | dry-run | approve
POST /v1/portability/imports/{id}/execute | resume | finalize | discard
GET  /v1/portability/imports/{id}/reconciliation | provenance | evidence/{family}
```

```
Export:  requested → analysing → awaiting_approval → approved → generating → verifying
         → ready_to_publish → publishing → published → expired | failed | revoked
Import:  created → fetching → quarantined → verifying → invalid | awaiting_mapping | dry_run_ready
         → awaiting_approval → approved → importing → rebuilding → reconciling → ready_to_finalize
         → finalized | failed | discarded
```

* Every transition is checked against the table and audited in `portability_events`. That table is
  append-only through the ledger's database guard and sealed in the daily digest chain, so there is
  no second audit system.
* Every transition is idempotent: repeating a transition already made returns the current state
  and writes nothing. The `Idempotency-Key` middleware replays stored answers.
* Errors use the one problem shape, with codes such as:
  `separation`, `closure`, `secret_found`, `blob_missing`, `not_a_tag`, `unsigned`,
  `bad_signature`, `moved_tag`, `missing_commit`, `unsafe_repository`, `checksum_mismatch`,
  `missing_artifact`, `missing_lfs_object`, `incompatible`, `divergent`, `unresolved_reference`,
  `invalid_transition`.
* `awaiting_mapping` is reserved for foreign schemas (§16).
* `expired` has no job yet (proposed: an export's artifacts expire with its retention class).

The CLI `python -m app.portability` runs the same lifecycles: export, approve, generate, publish,
import, step, drill and schemas.

## 15. Security and key management

* **People only.**
  * API tokens can't request, approve, generate, publish or import.
  * A workspace export needs the `approve` right on each workspace.
  * Full and restricted exports, approval, generation, publication, download tokens and every
    import step need an instance administrator.
* **Separation of duties.**
  * A high-risk export (full, evidence-only, or including restricted classes) needs an approver
    other than its requester.
  * So do merge and restore imports, and imports of archives with restricted classes.
* **Step-up authentication** is *proposed*. ARGUS keeps no `auth_time` or `acr` from the identity
  provider today. The intended rule is a re-authentication younger than 5 minutes (`max_age`, or
  `acr` at the institution's MFA level) for approving and generating high-risk exports.
* **Signing key.**
  * An Ed25519 private key in OpenSSH format, mounted from the institution's secret store and named
    by `ARGUS_PORTABILITY_SIGNING_KEY`.
  * It is never in the database or a repository.
  * One key signs checkpoints, commits and tags; rotation adds the new public key to the allowed
    signers before the old one is retired.
  * Verifiers trust an allowed-signers file (`ARGUS_PORTABILITY_TRUSTED_KEYS`). The public key
    inside `signature.json` is informative only.
* **Repository credentials.**
  * Repositories are registered by name (`ARGUS_PORTABILITY_REPOSITORIES`); callers never give
    URLs.
  * Credentials are not stored in a manifest.
  * *Proposed:* short-lived deploy tokens injected per operation (`GIT_ASKPASS`), read-only for
    fetching.
* **Untrusted Git content.** ARGUS treats everything fetched from Git as hostile:
  * no checkout, hooks disabled, no submodules, `transfer.fsckObjects`;
  * symbolic links, gitlinks, `.gitmodules`, unsafe paths, executables outside `tools/` and
    oversized objects are refused;
  * chunk reads are bounded in size, ratio and line length;
  * envelopes are validated;
  * nothing from a repository is executed.
* **Audit.** Request, analysis, decisions, approval, generation, verification, publication,
  download token, download, import steps, interruption, discard and finalization are all audited.
* **Retention and legal holds** of Git history and artifacts are institutional decisions
  (operations.md, §19).

## 16. Foreign and legacy schemas (proposed)

An exact ARGUS export is always imported deterministically. A repository holding a foreign or
legacy schema, under `mappings/foreign-schemas/` or with a manifest that is not `argus-archive/*`,
goes to `awaiting_mapping` and then through the governed path of `asset-model-revision.md` §23.17:

* AI may propose type, attribute, enumeration, unit and relation mappings, under the AI Intake rules
  (the requesting user's permissions, untrusted content, server-side only).
* Deterministic validation and authorized reviewers approve the mapping. Catalogue extensions need
  the catalogue curator.
* Identity merges, Installations, retirement and protected predicates need explicit
  authorization.
* The approved mapping profile, the model profile and the source commit are kept separately in
  provenance. A change of model never redefines an approved mapping rule.

ARGUS already has the parts this reuses: AI Intake, catalogue mapping with AI passes, record
mapping and legacy migration plans. Wiring them to `awaiting_mapping` is not built.

## 17. User experience

The API returns, for each export and import, the labels a page must show:

* complete or selective;
* full or incremental;
* signed;
* encrypted;
* Git-published;
* artifact-complete;
* verified;
* restorable;
* evidence-only.

It also returns the dependency report and its outcomes, size estimates, the manifest, verification
results, the dry-run report (catalogue, identity and merge conflicts, unresolved references,
chain), checkpoints, the reconciliation and the provenance.

**Administration → Portability** (`webapp/src/pages/admin/portability/`, implemented) shows them:

* **Exports.** A list with state and labels. "New export" chooses the scope (workspaces, everything, an
  increment of a published export, evidence only), the registered repository and artifact store, and
  the restricted classes to include, and warns when the export is high-risk. Its page shows:
  * the lifecycle as steps;
  * the estimate and warnings;
  * every dependency with a choice of outcome, analysed again on saving;
  * approval, refused to the requester of a high-risk export;
  * generation, publication to Git with a confirmation, a download, and revocation with a reason;
  * the watermark, the Git tag and commit, and the manifest (summary by group, or raw JSON).
* **Imports.** "New import" takes a registered repository and a signed tag or commit (with an
  optional expected commit), or an uploaded checkpoint, and a mode. Its page shows:
  * the source and signature, and the verification results;
  * the archive;
  * decisions for the dry run: workspace mapping, unresolved references, loading governance;
  * the dry-run report per family and outcome, with blocking items, catalogue conflicts, identity
    candidates, unresolved references and the chain;
  * approval, refused to the requester when a second person is needed;
  * execute and resume, with the number of finished steps; finalize; discard;
  * the reconciliation: authoritative families row by row, projections rebuilt against exported,
    and events the rebuild wrote;
  * an evidence browser for evidence imports, and the provenance and audit timeline.
* Labels are shown only once a checkpoint is verified. Confirmations are inline, never browser
  dialogs.

*Still proposed:* live progress while a long generation or import runs (the request waits for the
step to finish today), and showing the analysis of a selective export before it is requested.

## 18. Acceptance tests

`backend/tests/test_portability.py`. Every test uses two fresh databases at the migration head:

| # | Test |
|---|---|
| A1–A3, A15–A17, A26, A28 | `test_A1_A2_A3_A28_a_signed_git_checkpoint_rebuilds_the_same_state_in_an_empty_instance` |
| A4, A5, A7 | `test_A4_A5_A7_missing_commits_moved_and_unsigned_tags_and_branches_are_refused` |
| A4 (artifact), A6, A29 | `test_A6_A29_a_modified_file_or_a_missing_lfs_object_fails_verification` |
| A8, A10, A11 | `test_A8_A10_A11_increments_in_order_equal_a_full_export_and_out_of_order_is_refused` |
| A9, A23 | `test_A9_A23_an_interrupted_import_resumes_without_duplicates_and_a_discard_leaves_nothing` |
| A12–A14 | `test_A12_A13_A14_merge_blocks_divergent_uids_proposes_candidates_and_never_overwrites_types`, `test_A13_a_candidate_is_opened_never_merged` |
| A18–A20 | `test_A18_A19_A20_restricted_records_and_secrets_never_reach_git_or_the_archive` |
| A21 | `test_A21_malicious_paths_links_submodules_hooks_and_executables_are_refused` (4 cases) |
| A22 | `test_A22_decompression_bombs_oversized_and_malformed_lines_are_rejected` |
| A24 | `test_A24_an_evidence_import_creates_no_active_projection` |
| A25 | `test_A25_a_selective_export_includes_or_explicitly_resolves_every_dependency` |
| A27 | `test_A27_an_export_at_W_excludes_later_transactions` |
| A30 | `test_A30_the_restore_drill_verifies_the_latest_signed_full_checkpoint` |
| API | `test_the_api_enforces_people_administrators_separation_and_idempotent_transitions` |

## 19. Limits, open decisions and blockers

**Compatibility limits.**
* An importer accepts only archives whose families and columns it knows. An archive from a newer
  ARGUS with new columns is refused (`incompatible`) until a format migration exists.
* An older archive missing a column loads with the column's default.
* Reference-typed attribute values that name another record by uid are carried as values. They
  are not dependencies.
* Restore adopts the archive's instance identity; clone does not.
* The knowledge index (RAG) and search are rebuilt by their own jobs after finalization.
* Imported events keep their original timestamps. Merging them into an instance whose audit days
  are already sealed would change those days' digests, so **merge into a sealed instance is a
  blocker**. Two options: digests sealed by ingestion time, or imported events kept in a separate
  sealed chain.

**Decisions for stakeholders.**
1. The retention of portable archives, Git history and artifacts, and legal holds (asset-model
   U1). Legal holds are not modelled in ARGUS yet.
2. Who holds the signing key, who approves full exports, and the second approver for imports.
3. Which Git server and object storage hold escrow. Whether a third party holds an escrow copy.
4. Which classes may go to which repository, and whether restricted exports are ever produced
   without encryption.
5. The restore-drill cadence and who signs off its evidence.
6. Whether reconciliation reports are committed back to the portability repository.

**Blockers before production activation.**
1. Step-up authentication (§15).
2. Encryption of restricted chunks and blobs, if decision 4 needs it.
3. An S3 or OCI artifact backend, unless a mounted volume is accepted.
4. Git-server protections in place and tested: protected tags, no force push, code owners.
5. The signing key in the secret store, with a rotation procedure.
6. Short-lived repository credentials.
7. The merge-into-sealed-instance audit question.
8. The web page is implemented but has no automated UI test, and long steps block the request
   (no background job or live progress yet).
9. A restore drill on production-sized data, with timings.
10. The full export of production rehearsed; its memory and time measured. Chunks are written in
    memory per family today, and a streaming writer is needed for large families.
