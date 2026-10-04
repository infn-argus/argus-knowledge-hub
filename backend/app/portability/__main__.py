"""Operator commands for portable exports and imports (docs/operations.md, "Portable exports").

    python -m app.portability export   --mode workspace --workspace W [--workspace …] --by ACTOR
                                       [--repository NAME] [--store NAME] [--decide DEP=OUTCOME …]
    python -m app.portability approve  EXPORT_ID --by APPROVER
    python -m app.portability generate EXPORT_ID --by ACTOR
    python -m app.portability publish  EXPORT_ID --by ACTOR
    python -m app.portability import   --mode clone --repository NAME --ref TAG --by ACTOR
    python -m app.portability step     IMPORT_ID fetch|verify|dry-run|approve|execute|finalize|discard --by ACTOR
    python -m app.portability drill    --repository NAME [--prefix export/full/]
    python -m app.portability schemas  --out DIR

The same lifecycles and audit as the API; the actor is recorded as given (an operator's name,
`--by` on the command line), and separation of duties applies as there.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.portability import PortabilityExport, PortabilityImport
from app.portability import exporter, gitrepo, service

BACKEND = Path(__file__).resolve().parents[2]


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, default=str))


def latest_tag(cfg: service.Config, repository: str, prefix: str = "export/full/") -> str:
    """The newest signed export tag of a repository, by its ledger watermark."""
    url = cfg.repositories[repository]
    out = subprocess.run(["git", "ls-remote", "--tags", "--refs", url, f"refs/tags/{prefix}*"], capture_output=True,
                         text=True, env=gitrepo._env(), timeout=120, check=True).stdout
    tags = [line.split("refs/tags/", 1)[1] for line in out.splitlines() if "refs/tags/" in line]
    if not tags:
        raise SystemExit(f"no {prefix}* tag in {repository}")
    return max(tags, key=lambda t: int(re.search(r"@ledger-(\d+)$", t).group(1)) if re.search(r"@ledger-(\d+)$", t) else -1)


def restore_drill(cfg: service.Config, repository: str, database_url: str, prefix: str = "export/full/",
                  keep: bool = False) -> dict:
    """Fetch the latest signed checkpoint, import it into a scratch database at the current schema
    head, reconcile, and drop the database. The report is the drill's evidence."""
    tag = latest_tag(cfg, repository, prefix)
    name = f"argus_drill_{secrets.token_hex(4)}"
    base = database_url.rsplit("/", 1)[0]
    admin = create_engine(f"{base}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    report: dict = {"repository": repository, "tag": tag, "database": name}
    scratch = create_engine(f"{base}/{name}")
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True,
                       env={**os.environ, "DATABASE_URL": f"{base}/{name}"}, stdout=subprocess.DEVNULL)
        drill_cfg = service.Config(**{**cfg.__dict__, "root": cfg.root / "drills" / name,
                                      "attachments_dir": cfg.root / "drills" / name / "attachments"})
        with Session(scratch) as db:
            imp = service.create_import(db, "restore-drill", mode="clone",
                                        source={"repository": repository, "ref": tag}, decisions={}, cfg=drill_cfg)
            db.commit()
            service.fetch_git(db, imp, "restore-drill", drill_cfg)
            service.verify_import(db, imp, "restore-drill", drill_cfg)
            service.dry_run(db, imp, "restore-drill", drill_cfg)
            db.commit()
            if imp.state != "awaiting_approval":
                report.update({"passed": False, "stage": "dry_run", "dry_run": imp.dry_run})
                return report
            service.approve_import(db, imp, "restore-drill")   # a clone into a scratch database
            db.commit()
            service.execute(db, imp, "restore-drill", drill_cfg)
            if imp.state == "ready_to_finalize":
                service.finalize(db, imp, "restore-drill", drill_cfg)     # promotion into the scratch database
            report.update({"passed": imp.state == "finalized" and bool((imp.reconciliation or {}).get("passed")),
                           "commit": imp.commit, "export_id": imp.manifest["export_id"],
                           "checkpoint": imp.manifest["watermark"]["checkpoint_sequence"],
                           "vector_sha256": imp.manifest["watermark"]["vector_sha256"],
                           "reconciliation_sha256": imp.reconciliation_sha256,
                           "families": {k: v["ok"] for k, v in imp.reconciliation["families"].items()},
                           "projections": {k: v["ok"] for k, v in imp.reconciliation["projections"].items()}})
            return report
    finally:
        scratch.dispose()
        if not keep:
            with admin.connect() as c:
                c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def dev_setup() -> dict:
    """For a development instance only: create what the configuration names, where it is missing — a
    throwaway Ed25519 key and its allowed-signers file, the registered repositories as local bare
    repositories, and the artifact stores. Never overwrites a key. Production keys come from the
    institution's secret store (docs/operations.md, "Key management")."""
    from app.portability import signing
    done = {}
    key = os.environ.get("ARGUS_PORTABILITY_SIGNING_KEY")
    if key and not Path(key).exists():
        Path(key).parent.mkdir(parents=True, exist_ok=True)
        signer = signing.new_key(Path(key))
        done["signing_key"] = signer.key_id
        trusted = os.environ.get("ARGUS_PORTABILITY_TRUSTED_KEYS")
        if trusted:
            Path(trusted).write_text(signing.allowed_signers_line(signer))
            done["trusted_keys"] = trusted
    cfg = service.config()
    for name, url in cfg.repositories.items():
        if url.startswith("/") and not Path(url).exists():
            gitrepo.init_bare(Path(url))
            done[f"repository {name}"] = url
    for name, store in cfg.stores.items():
        store.root.mkdir(parents=True, exist_ok=True)
        done[f"store {name}"] = str(store.root)
    return done or {"note": "everything was already in place"}


def main(argv=None) -> int:
    from app.db import SessionLocal, engine
    ap = argparse.ArgumentParser(prog="python -m app.portability")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--mode", default="workspace")
    e.add_argument("--workspace", action="append", default=[])
    e.add_argument("--classification", action="append", default=[])
    e.add_argument("--repository")
    e.add_argument("--store")
    e.add_argument("--base")
    e.add_argument("--decide", action="append", default=[])
    e.add_argument("--identity-profile")
    e.add_argument("--by", required=True)
    for name in ("approve", "generate", "publish"):
        p = sub.add_parser(name)
        p.add_argument("export_id")
        p.add_argument("--by", required=True)
    i = sub.add_parser("import")
    i.add_argument("--mode", default="clone")
    i.add_argument("--repository", required=True)
    i.add_argument("--ref", required=True)
    i.add_argument("--expected-commit")
    i.add_argument("--by", required=True)
    s = sub.add_parser("step")
    s.add_argument("import_id")
    s.add_argument("step", choices=["fetch", "verify", "dry-run", "approve", "execute", "finalize", "discard"])
    s.add_argument("--by", required=True)
    s.add_argument("--reason", default="")
    d = sub.add_parser("drill")
    d.add_argument("--repository", required=True)
    d.add_argument("--prefix", default="export/full/")
    sub.add_parser("dev-setup", help="development only: a throwaway key, a local bare repository, an artifact store")
    rk = sub.add_parser("recipient-key", help="an X25519 recipient key pair: private key to a file, public line printed")
    rk.add_argument("--name", required=True)
    rk.add_argument("--out", required=True)
    sc = sub.add_parser("schemas")
    sc.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = service.config()

    if a.cmd == "schemas":
        out = Path(a.out)
        for rel, body in exporter.json_schemas().items():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
        return 0
    if a.cmd == "recipient-key":
        from app.portability import envelope
        print(envelope.new_recipient_key(Path(a.out), a.name), end="")
        return 0
    if a.cmd == "dev-setup":
        _print(dev_setup())
        return 0
    if a.cmd == "drill":
        report = restore_drill(cfg, a.repository, os.environ["DATABASE_URL"], a.prefix)
        _print(report)
        return 0 if report.get("passed") else 1
    db = SessionLocal()
    try:
        if a.cmd == "export":
            decisions = dict(x.split("=", 1) for x in a.decide)
            exp = service.create_export(db, a.by, mode=a.mode, workspaces=a.workspace,
                                        classifications=a.classification,
                                        destination={"repository": a.repository, "artifact_store": a.store},
                                        decisions=decisions, base_export_id=a.base,
                                        identity_profile=a.identity_profile, cfg=cfg)
            service.analyse_export(db, exp, a.by)
            db.commit()
            _print(service.export_view(exp))
        elif a.cmd in ("approve", "generate", "publish"):
            exp = db.get(PortabilityExport, a.export_id)
            # The operator CLI runs with host-level access to ARGUS: that is its step-up (audited as such).
            if a.cmd == "approve":
                service.approve_export(db, exp, a.by, admin=True, fresh_auth=True, cfg=cfg)
            elif a.cmd == "generate":
                service.generate_export(engine, db, exp, a.by, cfg, fresh_auth=True)
            else:
                service.publish_export(db, exp, a.by, cfg)
            db.commit()
            _print(service.export_view(db.get(PortabilityExport, a.export_id)))
        elif a.cmd == "import":
            imp = service.create_import(db, a.by, mode=a.mode, source={"repository": a.repository, "ref": a.ref,
                                        **({"expected_commit": a.expected_commit} if a.expected_commit else {})},
                                        decisions={}, cfg=cfg)
            db.commit()
            _print(service.import_view(imp))
        elif a.cmd == "step":
            imp = db.get(PortabilityImport, a.import_id)
            fn = {"fetch": lambda: service.fetch_git(db, imp, a.by, cfg),
                  "verify": lambda: service.verify_import(db, imp, a.by, cfg),
                  "dry-run": lambda: service.dry_run(db, imp, a.by, cfg),
                  "approve": lambda: service.approve_import(db, imp, a.by),
                  "execute": lambda: service.execute(db, imp, a.by, cfg),
                  "finalize": lambda: service.finalize(db, imp, a.by, cfg),
                  "discard": lambda: service.discard(db, imp, a.by, cfg, a.reason)}[a.step]
            out = fn()
            db.commit()
            _print({**service.import_view(out), "dry_run": out.dry_run})
    except service.ServiceError as err:
        db.rollback()
        _print({"error": str(err), "code": err.code, **err.detail})
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
