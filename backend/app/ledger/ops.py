"""Backups, restore rehearsal and a performance probe (asset-model-revision
§19 items 10 and 13).

* `backup` — a `pg_dump` custom-format dump, the attachments as a tarball,
  and a manifest with their SHA-256 and the row counts the restore must
  reproduce. For point-in-time recovery run Postgres with WAL archiving
  (docs/operations.md); this dump is the base the WAL is replayed onto.
* `rehearse_restore` — restores a dump into a scratch database, checks the
  counts against the manifest and the audit digest chain, and drops the
  scratch database. §19 asks for this at least quarterly.
* `probe` — measures the §19 performance targets against a running API.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import statistics
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

COUNTED = ("assets", "issues", "relations", "attachments", "ledger_claims", "ledger_decisions",
           "ledger_record_events", "ledger_status_events", "ledger_audit_digests")
TARGETS = {"record_page_p95_ms": 500, "search_p95_ms": 1000, "own_edit_visible_ms": 1000,
           "reprojection_s": 30 * 60}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def counts(url: str) -> dict:
    engine = create_engine(url)
    try:
        with engine.connect() as c:
            return {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in COUNTED}
    finally:
        engine.dispose()


def backup(url: str, out_dir: str, attachments_dir: Optional[str] = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump = out / f"argus-{stamp}.dump"
    subprocess.run(["pg_dump", "--format=custom", "--no-owner", f"--file={dump}", url], check=True)
    manifest = {"created_at": stamp, "dump": dump.name, "dump_sha256": _sha256(str(dump)), "counts": counts(url)}
    if attachments_dir and os.path.isdir(attachments_dir):
        tar = out / f"attachments-{stamp}.tar.gz"
        with tarfile.open(tar, "w:gz") as t:
            t.add(attachments_dir, arcname="attachments")
        manifest.update({"attachments": tar.name, "attachments_sha256": _sha256(str(tar))})
    with open(out / f"argus-{stamp}.manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _with_db(url: str, name: str) -> str:
    p = urlparse(url)
    return urlunparse(p._replace(path=f"/{name}"))


def rehearse_restore(url: str, manifest_path: str) -> dict:
    """Restore the manifest's dump into a scratch database next to `url`,
    and check it: the dump's checksum, the row counts, the audit chain."""
    manifest = json.load(open(manifest_path))
    folder = os.path.dirname(os.path.abspath(manifest_path))
    dump = os.path.join(folder, manifest["dump"])
    report = {"dump": manifest["dump"], "checks": {}}
    report["checks"]["dump_checksum"] = _sha256(dump) == manifest["dump_sha256"]
    scratch = f"argus_restore_{secrets.token_hex(4)}"
    admin = create_engine(_with_db(url, "postgres"), isolation_level="AUTOCOMMIT")
    started = time.monotonic()
    try:
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{scratch}"'))
        target = _with_db(url, scratch)
        subprocess.run(["pg_restore", "--no-owner", f"--dbname={target}", dump], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        restored = counts(target)
        report["counts"] = restored
        report["checks"]["counts_match"] = restored == manifest["counts"]
        engine = create_engine(target)
        try:
            from app.ledger import audit
            with Session(engine) as db:
                chain = audit.verify(db)
            report["audit_chain"] = chain
            report["checks"]["audit_chain"] = chain["ok"]
        finally:
            engine.dispose()
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)'))
        admin.dispose()
    report["restore_seconds"] = round(time.monotonic() - started, 2)
    report["ok"] = all(report["checks"].values())
    return report


# --------------------------------------------------------------------------- performance (§19 item 13)

def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


def probe(client, headers: dict, asset_uids: list[str], queries: list[str], edit_uid: Optional[str] = None,
          db: Optional[Session] = None, workspace_id: Optional[str] = None) -> dict:
    """Time the paths people feel. `client` is anything with httpx's get/post
    (an httpx.Client on a base URL, or FastAPI's TestClient)."""
    def timed(fn) -> float:
        t = time.perf_counter()
        resp = fn()
        resp.raise_for_status()
        return (time.perf_counter() - t) * 1000
    page = [timed(lambda u=u: client.get(f"/v1/hub/assets/{u}/context", headers=headers)) for u in asset_uids]
    search = [timed(lambda q=q: client.get("/v1/hub/search", params={"q": q}, headers=headers)) for q in queries]
    out = {"record_page_p95_ms": round(_p95(page), 1), "search_p95_ms": round(_p95(search), 1),
           "samples": {"record_page": len(page), "search": len(search)},
           "record_page_median_ms": round(statistics.median(page), 1) if page else None}
    if edit_uid:
        marker = f"probe-{secrets.token_hex(3)}"
        t = time.perf_counter()
        client.post(f"/v1/ledger/records/{edit_uid}/edit", headers=headers,
                    json={"predicate": "attr:argus_probe", "value": marker}).raise_for_status()
        seen = client.get(f"/v1/assets/{edit_uid}", headers=headers).json()["attributes"].get("argus_probe")
        out["own_edit_visible_ms"] = round((time.perf_counter() - t) * 1000, 1) if seen == marker else None
    if db is not None and workspace_id:
        from app.ledger import engine
        t = time.perf_counter()
        engine.rebuild(db, workspace_id)
        db.rollback()                       # measured, not kept
        out["reprojection_s"] = round(time.perf_counter() - t, 2)
    out["targets"] = TARGETS
    out["meets"] = {k: (out.get(k) is not None and out[k] <= v) for k, v in TARGETS.items() if k in out}
    return out
