# Operating ARGUS

What has to run, and how to prove it works, for ARGUS to hold data as the
system of record (asset-model-revision §19).

## Scheduled jobs

| When | Command | Why |
|---|---|---|
| continuously (or every minute) | `python -m app.ledger derive-worker` | runs the derived links a user edit queued, when `LEDGER_USER_EDIT_DERIVE=manual` (the default `background` runs them in the API process) |
| every 5–15 minutes | `python -m app.ledger escalate` | escalates tickets that outstayed their state's SLA; sends pending notifications by e-mail when `SMTP_HOST` is set |
| daily, after midnight UTC | `python -m app.ledger audit-digest` | seals yesterday's audit events into the digest chain. **Copy the printed digest outside ARGUS** (a ticket in another system, a signed e-mail, write-once storage) |
| weekly | `python -m app.ledger verify-audit` | recomputes the chain; a non-zero exit names the first altered day |
| daily | `python -m app.ledger backup --out /backups` | base backup: `pg_dump`, the attachments, and a manifest with checksums and row counts |
| quarterly (at least) | `python -m app.ledger rehearse-restore /backups/argus-….manifest.json` | restores into a scratch database, checks counts and the audit chain, drops it. Keep the JSON report as evidence |

E-mail: `SMTP_HOST`, `SMTP_PORT` (25), `SMTP_FROM`, and `ARGUS_URL` for links.
Notifications are always stored in-app; e-mail is a delivery channel.

## Point-in-time recovery (RPO ≤ 15 min, RTO ≤ 4 h)

The daily dump alone gives a one-day RPO. For the §19 target, run Postgres
with continuous WAL archiving:

```
# postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /wal-archive/%f && cp %p /wal-archive/%f'
archive_timeout = 300          # a segment at least every 5 minutes
```

Take a physical base backup weekly (`pg_basebackup -D /base/$(date +%F) -Ft -z -X stream`).
To recover to a moment: restore the latest base backup before it into a new
data directory, then

```
# postgresql.conf of the restored cluster
restore_command = 'cp /wal-archive/%f %p'
recovery_target_time = '2026-10-03 14:25:00+00'
recovery_target_action = 'promote'
```

`touch recovery.signal`, start Postgres, and it replays WAL to that moment.
Restore the attachments directory from the tarball of the same day, then run
`python -m app.ledger verify-audit` and `python -m app.ledger backfill-checksums`
before opening the instance. Rehearse this in staging at least quarterly (§17.4
entry criterion 5) and record the elapsed time against the 4-hour RTO.

A damaged ARGUS is recovered this way — never by restoring Jira (§17.7).

## Export and load (escrow, moving instances)

```
python -m app.ledger export --workspace sparc --out /escrow/sparc      # every grant
python -m app.ledger load --dir /escrow/sparc --attachments /escrow/sparc-files   # into an empty instance
```

The bundle is JSON lines per kind (workspace, schemas, assets, tickets,
comments, relations, attachments, ledger). `load` checks every attachment
against its SHA-256 first and refuses a mismatch. Links to records of other
workspaces are loaded when the other workspace is already there, and listed
otherwise. `tests/test_readiness_ops.py` loads a bundle into a freshly
migrated database and compares a fingerprint of everything.

## Performance targets

```
python -m app.ledger probe --base-url https://argus.example --token $TOKEN \
    --asset <uid> --asset <uid> … --query pump --query SIP --edit <probe-record-uid>
```

It reports the p95 of record pages and searches, how long an own edit takes to
be visible, and whether each meets its target (record page < 500 ms, search
< 1 s, own edit < 1 s). `--edit` writes an `argus_probe` value: point it at a
record kept for the purpose. Run it at 10× the current volume before a
cutover (§19 item 13). `--reproject <workspace>` also times a full
re-projection of that workspace in-process (rolled back, target < 30 min);
it needs `DATABASE_URL`.

### 10× volume run

`scripts/generate_volume.py` builds a synthetic workspace of that size and
prints the token and record uids to probe with:

```
cd backend
PYTHONPATH=. python scripts/generate_volume.py --workspace volume --assets 50000 \
    --tickets 20000 --documents 5000 --ledger-devices 2000 --token volume-token
python -m app.ledger probe --base-url http://127.0.0.1:8000 --token volume-token \
    --asset <uid> … --query "Ion Pump" --query SN0012345 --query "Rack C12" \
    --edit <uid> --reproject volume
```

Measured on a development container (one uvicorn worker, Postgres 16 on the
same host), with 50 000 records, 100 000 relations, 20 000 tickets,
5 000 documents and a 2 000-device configuration ingested through the ledger:

| Measure | Result | Target |
|---|---|---|
| Record page p95 (40 records) | 230 ms (median 82 ms) | 500 ms |
| Search p95 (5 queries) | 188 ms | 1 s |
| Own edit visible | 843 ms | 1 s |
| Full re-projection of the workspace | 278 s | 30 min |
| Ingest of the 2 000-device revision | 188 s | — |
| Bulk load of the rest | 18 s | — |

Two hot paths were fixed on the way. Claim presence is now cached per
session against the stream's last event, where it used to replay the whole
stream once per projected subject. And a publication re-derives only the
tickets whose links the ledger can move: those on positions, control devices
and installed units, and those with no links yet. Before, it re-derived every
ticket in the workspace. The own-edit time is the closest to its target;
watch it first when the volume grows.

## The Jira host after retirement

When Jira is retired, point its host name at ARGUS. Every old link then
opens the ARGUS lookup page, which resolves it with the reader's own
access. The redirect itself shows nothing about what exists.

```
JIRA_LEGACY_HOSTS=jira.example.org,insight.example.org
ARGUS_WEB_URL=https://argus.example.org
```

A request whose `Host` is one of these gets a 301 to
`$ARGUS_WEB_URL/lookup/<the original URL>`. A proxy that cannot route by
host name can forward the old host to `/legacy/jira/<path>` instead:

```
server {
    server_name jira.example.org;
    location / {
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://argus-api:8000/legacy/jira$request_uri;
    }
}
```

## Retiring Jira

Jira is retired once, for the whole instance, from *Migration to ARGUS →
Jira retirement* (administrators only; `GET/POST /v1/retirement`). ARGUS
checks for itself:

- every domain is past its signed exit and in T4;
- every domain's export was attested as verified at its exit;
- the retention decision (U1) is recorded, with the records policy it
  comes from (`POST /v1/retirement/retention`);
- every workspace with a domain has an access review signed in the last
  year;
- the audit chain verifies;
- every Jira workflow of a ticket domain passes its rehearsal;
- a restore rehearsal passed in the last quarter
  (`python -m app.ledger rehearse-restore` records it);
- a probe run in the last quarter measured and met all four targets,
  re-projection included (`python -m app.ledger probe … --reproject <ws>`
  records it);
- the Jira host redirect is configured.

The signer also attests three things ARGUS cannot see: a
disaster-recovery drill, the owners' sign-off of the targets (U10), and
their acceptance of items 1–13. Signing records one decision and moves
every domain from T4 to T5. A domain reaches T5 in no other way.

## Legacy migration (§12)

This converts the records the old importer inferred (`argus_keywords:
inferred`) into Positions, Equipment and Installations. It is done per
workspace, before the workspace's domain is frozen for cutover: the freeze
is refused while any item is M-BLOCK, an M-MIXED item is not yet accepted,
or an inferred record is not in a plan.

1. **Back up** (`python -m app.ledger backup`). Run it first on a restored
   copy of production.
2. **Plan**: *Migration to ARGUS → Legacy records → Plan the migration*, or
   `POST /v1/migration/plans` with an optional `inventory_workspace_id`.
   This is where Equipment that matches no inventory record gets created.
   Nothing changes. Download the decision report (CSV) and give it to the
   owners.
3. **Review**: the owners override an outcome where they disagree. Each
   override needs a reason and is recorded as a decision. An M-BLOCK item
   (an identifier held by another record) is resolved at its source, then
   re-planned or overridden.
4. **Apply**: items are applied in dependency order, each in its own
   savepoint:
   - an item whose record changed since planning becomes `stale`;
   - an item that breaks I-MIG-1 (nothing lost) or I-MIG-2 (traceable)
     becomes `failed` and leaves nothing behind.

   The plan is `verified` when every item is applied and I-MIG-2 and
   I-MIG-3 hold across the plan.
5. **Deep verification** (*Deep verify*, `POST /v1/migration/plans/{id}/verify`):
   - **I-MIG-4:** runs the data invariant report over the plan's workspaces
     (below). Every invariant must hold.
   - **I-MIG-5:** compares the relation registry's report with the
     baseline taken before the first item moved. The total number of
     violations must not grow; a rule that grew is named even when the
     total fell.
   - **I-MIG-6:** rebuilds the plan's workspaces from the ledger inside a
     savepoint, compares every record the plan touched, then rolls back.
     A difference means something was written around the ledger.

   Finalizing needs a passing deep verification taken after the last
   apply. People still check I-MIG-7: the root-cause walks on a golden set
   of past incidents.
6. **Roll back** at any point until the plan is finalized, and never after
   the domain has cut over:
   - records the migration created are retired by ledger decisions;
   - Installations are rejected;
   - labels and photos move back;
   - the legacy rows get their pre-images back.

   `migration_map` is append-only, so its rows stay as history.
7. **Finalize** after sign-off. From then on, corrections are ordinary
   decisions.

What each outcome does:

| Outcome | Result |
|---|---|
| M-FUNC | a lattice element: kept |
| M-POS | the row becomes an `Equipment Position` with key `FAC:POS:<tag>`. The old key is kept as a `former_key` label and still resolves through `/v1/lookup` |
| M-PHYS | Position, plus the inventory's matching record or new Active Equipment, plus a Confirmed Installation. `valid_from` is the day a person set in `installed_on`, otherwise `before_records` |
| M-MIXED | Position, plus Provisional Equipment (stated as the migration's inference), plus a Proposed Installation. A reviewer confirms both |
| M-RETIRE | the importer no longer produces it and no person touched it: Retired, with its relations kept in the pre-image |
| M-BLOCK | nothing moves |

## Cutover entry criteria (§17.4)

A domain is frozen for cutover (T3) only when every entry criterion holds.
They are listed in *Migration to ARGUS → the domain → Entry criteria and
freeze*, and in `GET /v1/domains/{id}` as `entry_criteria`.

ARGUS checks these itself:

| Criterion | What ARGUS checks |
|---|---|
| 2 stewards | a primary steward and a different backup, set with `PUT /v1/domains/{id}/stewards` and recorded as a decision |
| 2 blocking queues | no blocking conflict and no held revision (never waived) |
| 2 queue ageing | no open item past its §18.2 target, in working days: port mapping 5, identity candidate 10, retirement flag 10, other non-blocking 30. A safety-relevant port confirmation is never left open |
| 3 shadow validation | the domain is in T2, entered at least 14 days ago, with 10 consecutive passing reconciliation runs since. Past 8 weeks it is flagged for the governance group |
| 4 legacy migration | no M-BLOCK item, every M-MIXED item accepted, no inferred record unplanned (never waived) |
| 5 restore | a restore rehearsal passed in the last 30 days (`python -m app.ledger rehearse-restore` records it) |
| 7 performance | a probe run that met every target, in the last quarter |

People attest the rest: the readiness items and tests A33–A41 pass for
the domain's data (1), the users are trained (6), and the Jira
read-only change is approved and scheduled (6).

The governance group may waive a criterion with a reason, for example a
rehearsal on staging, or a domain it decided to cut over at the T2 limit.
The waivers and attestations are written into the `freeze` decision.

## Review queues and escalation (§18.2)

Every open review item is in one queue. Each queue has three targets in
working days: when an item is due, when it goes to the domain's backup
steward, and when it goes to the governance group.

| Queue | Due | To backup | To governance |
|---|---|---|---|
| blocking conflicts, held revisions | 2 | 3 | 5 |
| port confirmations, safety-relevant | 0 | 0 | 1 |
| other port confirmations and mappings | 5 | 7 | 10 |
| identity candidates | 10 | 15 | 30 |
| proposals (inferred facts) | 20 | 30 | 60 |
| non-blocking conflicts, possible overlaps | 30 | 45 | 90 |
| retirement flags | 10 | 15 | 30 |

The scheduled `python -m app.ledger escalate` job, or *Review queue →
Queue ageing → Escalate overdue now*, sends an in-app notification once
per level. It is also e-mailed when SMTP is configured:

- level 1 goes to the backup steward, with the steward in copy;
- level 2 goes to the governance group, with the backup in copy.

The stewards are the ones set on the workspace's domain. The governance
group is set here:

```
ARGUS_GOVERNANCE=governance-lead@example.org,platform-lead@example.org
```

A notification names the queue, the workspace and the age, never the
record. The recipient opens the review queue with their own access, so a
restricted record is not disclosed. The dashboard (`GET
/v1/ledger/review/queues`) shows, for each queue:

- its size and age distribution;
- how many items are overdue, at backup and at governance;
- the age of the oldest item.

Migration items are not in a queue of their own: they are due before the
domain's cutover, and the freeze enforces that (§12, §17.4).

## The relation registry, in warn mode (§6)

`GET /v1/ledger/registry/report` lists every edge of the workspace that
breaks the registry. It checks:

- deprecated verbs (`replaced`, `carried by`, `on line`, `spare for`, and
  `assigned to` a Work Package);
- the types each end may have (`installed at`, `installation of`,
  `realized by`, `assigned to`, `powers`, `acts on`, `port of`, `runs on`,
  `part of`);
- cardinality: one position per unit at any instant, one Installation
  edge each way, one `part of`, exclusive `composed of`;
- cycles in `part of` and `composed of`;
- edges pointing at retired or merged records.

Nothing is refused in warn mode. The report is what stewards triage
before the registry moves to `enforce` (§13 S7), and it is the measure
that I-MIG-5 compares.

## Data invariant report

`GET /v1/ledger/invariants/report` checks the workspace's data as it is,
whatever wrote it. The ledger enforces these invariants when a decision is
made; this report catches what the legacy importer, a migration or a write
around the ledger left behind.

| Invariants | What is checked |
|---|---|
| I-INS-1, I-INS-2 | no unit in two places, and no two units in one position, in definite overlap (Confirmed Installations) |
| I-INS-3 | Confirmed intervals are not inverted |
| I-INS-4 | an Installation is installed at an installable position, of Equipment |
| I-INS-5 | an Installation is in its position's workspace |
| I-INS-6 | a possible overlap has its review item |
| I-AP-1 to I-AP-3 | one Active Access Point per address; one assignment each; no definite overlap of service |
| I-AP-4 | an assigned Access Point has no asserted `implemented by` |
| I-AP-5 | an Access Point lives in the workspace whose configuration names it |
| I-PORT-1 | every derived `attached to` edge is exactly what the port matching gives now |
| I-PORT-2 | a confirmed port map names a port of its Installation's unit |
| I-PORT-3 | an unresolved mapping has its review item |
| I-TKT-1 | each ticket has exactly one subject link |
| I-TKT-2 | no ticket is counted twice on one record, and migration-split links stay possible |
| I-TKT-3 | the derived links are exactly what a fresh derivation gives (recomputed in a savepoint) |
| uniqueness | no serial (per manufacturer), inventory number, verified Insight objectId or QR code is held by two live records |

I-INS-7 and I-PORT-4 hold by construction of the checks above. The report
says which invariants they are covered by.
