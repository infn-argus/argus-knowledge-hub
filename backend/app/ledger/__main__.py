"""Ledger maintenance from the command line.

    python -m app.ledger derive-worker [--once] [--interval 5]
        run queued derive requests (what user edits leave `deriving`)
    python -m app.ledger backfill-checksums
        record SHA-256 for attachments stored before checksums existed
    python -m app.ledger audit-digest [--day YYYY-MM-DD]
        print (and store) the chained digest of the audit log for a day
    python -m app.ledger verify-audit
        recompute the digest chain and report the first break, if any
    python -m app.ledger escalate
        escalate tickets that have outstayed their state's SLA, and send
        pending notifications by e-mail when SMTP_HOST is set
    python -m app.ledger export --workspace WS --out DIR
        a complete JSON-lines bundle of a workspace (every grant)
    python -m app.ledger load --dir DIR [--attachments DIR] [--workspace WS]
        load a bundle into this (empty) instance
    python -m app.ledger backup --out DIR [--attachments DIR]
        pg_dump + attachments + a manifest with checksums and row counts
    python -m app.ledger rehearse-restore MANIFEST
        restore into a scratch database, check it, drop it
    python -m app.ledger probe --base-url URL --token TOKEN --asset UID [...] [--edit UID]
        measure the §19 performance targets against a running API; --edit
        writes an `argus_probe` value on that (dedicated) record
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date

from app.db import SessionLocal


def _keep_evidence(stage: str, report: dict, ok: bool) -> None:
    """Operations runs are evidence for the Jira retirement (§19 item 14)."""
    from app.services import retirement
    db = SessionLocal()
    try:
        retirement.record_job(db, stage, json.loads(json.dumps(report, default=str)), ok)
        db.commit()
    finally:
        db.close()


def derive_worker(once: bool, interval: float) -> None:
    from app.ledger.engine import process_derive_requests
    while True:
        db = SessionLocal()
        try:
            n = process_derive_requests(db)
            db.commit()
        finally:
            db.close()
        if n:
            print(f"derived {n} request(s)", flush=True)
        if once:
            return
        time.sleep(interval)


def backfill_checksums() -> int:
    from sqlalchemy import select
    from app.models.attachment import Attachment, file_sha256
    db = SessionLocal()
    n = 0
    try:
        for att in db.scalars(select(Attachment).where(Attachment.sha256.is_(None))):
            digest = file_sha256(att.storage_path)
            if digest:
                att.sha256 = digest
                n += 1
        db.commit()
    finally:
        db.close()
    return n


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ledger")
    sub = parser.add_subparsers(dest="command", required=True)
    w = sub.add_parser("derive-worker")
    w.add_argument("--once", action="store_true")
    w.add_argument("--interval", type=float, default=5.0)
    sub.add_parser("backfill-checksums")
    a = sub.add_parser("audit-digest")
    a.add_argument("--day", type=date.fromisoformat, default=None)
    sub.add_parser("verify-audit")
    sub.add_parser("escalate")
    sub.add_parser("catalogue-report", help="§5.5: the monthly equipment class report, reviews and alert")
    e = sub.add_parser("export")
    e.add_argument("--workspace", required=True)
    e.add_argument("--out", required=True)
    ld = sub.add_parser("load")
    ld.add_argument("--dir", required=True)
    ld.add_argument("--attachments", default=None)
    ld.add_argument("--workspace", default=None)
    b = sub.add_parser("backup")
    b.add_argument("--out", required=True)
    b.add_argument("--attachments", default=os.environ.get("ATTACHMENTS_DIR"))
    r = sub.add_parser("rehearse-restore")
    r.add_argument("manifest")
    pr = sub.add_parser("probe")
    pr.add_argument("--base-url", required=True)
    pr.add_argument("--token", required=True)
    pr.add_argument("--asset", action="append", default=[])
    pr.add_argument("--query", action="append", default=[])
    pr.add_argument("--edit", default=None)
    pr.add_argument("--reproject", default=None, metavar="WORKSPACE",
                    help="also time a full re-projection of this workspace (rolled back)")
    args = parser.parse_args(argv)
    if args.command == "derive-worker":
        derive_worker(args.once, args.interval)
    elif args.command == "backfill-checksums":
        print(f"recorded {backfill_checksums()} checksum(s)")
    elif args.command == "audit-digest":
        from app.ledger import audit
        db = SessionLocal()
        try:
            row = audit.seal_day(db, args.day)
            db.commit()
            print(row.digest)
        finally:
            db.close()
    elif args.command == "export":
        from app.ledger import portability
        db = SessionLocal()
        try:
            portability.everything()
            print(json.dumps(portability.write_bundle(db, args.workspace, args.out)))
        finally:
            db.close()
    elif args.command == "load":
        from app.ledger import portability
        bundle = portability.read_bundle(args.dir)
        if args.attachments:
            problems = portability.verify_files(bundle, args.attachments)
            if problems:
                print("attachments do not match their checksums:", *problems, sep="\n  ")
                return 1
        db = SessionLocal()
        try:
            print(json.dumps(portability.load_bundle(db, bundle, args.attachments, args.workspace)))
            db.commit()
        finally:
            db.close()
    elif args.command == "backup":
        from app.ledger import ops
        print(json.dumps(ops.backup(os.environ["DATABASE_URL"], args.out, args.attachments), indent=2))
    elif args.command == "rehearse-restore":
        from app.ledger import ops
        report = ops.rehearse_restore(os.environ["DATABASE_URL"], args.manifest)
        print(json.dumps(report, indent=2, default=str))
        _keep_evidence("restore-rehearsal", report, report["ok"])
        return 0 if report["ok"] else 1
    elif args.command == "probe":
        import httpx
        from app.ledger import ops
        db = SessionLocal() if args.reproject else None
        try:
            with httpx.Client(base_url=args.base_url, timeout=60) as client:
                result = ops.probe(client, {"Authorization": f"Bearer {args.token}"}, args.asset,
                                   args.query or ["pump", "SIP", "rack"], args.edit, db=db,
                                   workspace_id=args.reproject)
        finally:
            if db is not None:
                db.close()
        print(json.dumps(result, indent=2))
        # Evidence for the retirement only when every target was measured and met.
        _keep_evidence("probe", result, set(result["meets"]) == set(ops.TARGETS) and all(result["meets"].values()))
        return 0 if all(result["meets"].values()) else 1
    elif args.command == "catalogue-report":
        from app.services import equipment_classes
        db = SessionLocal()
        try:
            out = equipment_classes.monthly(db)
            db.commit()
            print(json.dumps(out, indent=2, default=str))
        finally:
            db.close()
    elif args.command == "escalate":
        from app.services import notify
        db = SessionLocal()
        try:
            n = notify.escalate_overdue(db)
            from app.ledger import queues
            review = queues.escalate(db)
            print(f"review items escalated: {review['backup']} to backup stewards, "
                  f"{review['governance']} to the governance group")
            sent = notify.deliver_pending(db)
            db.commit()
        finally:
            db.close()
        print(f"escalated {n} ticket(s); e-mailed {sent} notification(s)")
    elif args.command == "verify-audit":
        from app.ledger import audit
        db = SessionLocal()
        try:
            result = audit.verify(db)
        finally:
            db.close()
        print(result)
        return 0 if result["ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
