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
cutover (§19 item 13); the full re-projection time of the largest workspace is
measured in-process by `app.ledger.ops.probe(..., db=, workspace_id=)`.
