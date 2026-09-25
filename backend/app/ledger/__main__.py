"""Ledger maintenance from the command line.

    python -m app.ledger derive-worker [--once] [--interval 5]
        run queued derive requests (what user edits leave `deriving`)
    python -m app.ledger backfill-checksums
        record SHA-256 for attachments stored before checksums existed
    python -m app.ledger audit-digest [--day YYYY-MM-DD]
        print (and store) the chained digest of the audit log for a day
    python -m app.ledger verify-audit
        recompute the digest chain and report the first break, if any
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from app.db import SessionLocal


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
