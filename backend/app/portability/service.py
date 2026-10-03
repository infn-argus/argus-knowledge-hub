"""Exports and imports as lifecycles: what the API and the CLI call.

Configuration (environment; docs/operations.md):

  ARGUS_PORTABILITY_ROOT              working area: checkpoints, quarantine, evidence, clones
  ARGUS_PORTABILITY_REPOSITORIES      name=url,…  the only repositories ARGUS publishes to or fetches
                                      from (an API caller names one; it never passes a URL)
  ARGUS_PORTABILITY_ARTIFACT_STORES   name=/path,…  content-addressed artifact stores
  ARGUS_PORTABILITY_SIGNING_KEY       the Ed25519 signing key (a mounted secret, never in a repository)
  ARGUS_PORTABILITY_TRUSTED_KEYS      allowed-signers file of the keys an import trusts
  ATTACHMENTS_DIR                     where imported files land
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import shutil
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models.portability import PortabilityEvent, PortabilityExport, PortabilityImport, PortabilityTagSeen
from app.portability import artifacts, chunks, closure, exporter, gitrepo, importer, signing, verify as verifier
from app.portability.families import Scope
from app.portability.lifecycle import TransitionError, audit, expect, labels, move

HIGH_RISK_MODES = ("full", "evidence-only")


@dataclass
class Config:
    root: Path
    attachments_dir: Path
    stores: dict = field(default_factory=dict)
    signer: Optional[signing.Signer] = None
    trusted: Optional[Path] = None
    repositories: dict = field(default_factory=dict)
    limits: chunks.Limits = chunks.LIMITS
    publish_reconciliation: bool = False

    def export_dir(self, export_id: str) -> Path:
        return self.root / "exports" / export_id

    def quarantine(self, import_id: str) -> Path:
        return self.root / "quarantine" / import_id

    def evidence(self, import_id: str) -> Path:
        return self.root / "evidence" / import_id

    def work(self, repository: str) -> Path:
        return self.root / "work" / hashlib.sha256(repository.encode()).hexdigest()[:16]


def config() -> Config:
    repos = {}
    for item in filter(None, (os.environ.get("ARGUS_PORTABILITY_REPOSITORIES") or "").split(",")):
        name, _, url = item.partition("=")
        repos[name.strip()] = url.strip()
    trusted = os.environ.get("ARGUS_PORTABILITY_TRUSTED_KEYS")
    return Config(root=Path(os.environ.get("ARGUS_PORTABILITY_ROOT", "/data/portability")),
                  attachments_dir=Path(os.environ.get("ATTACHMENTS_DIR", "/data/attachments")),
                  stores=artifacts.configured_stores(), signer=signing.configured_signer(),
                  trusted=Path(trusted) if trusted else None, repositories=repos,
                  publish_reconciliation=os.environ.get("ARGUS_PORTABILITY_PUBLISH_RECONCILIATION") == "1")


class ServiceError(ValueError):
    def __init__(self, message: str, code: str = "refused", status: int = 409, detail: Optional[dict] = None):
        super().__init__(message)
        self.code, self.status, self.detail = code, status, detail or {}


def _fail(db: Session, subject, actor: str, exc: Exception, to: str = "failed") -> None:
    db.rollback()
    subject = db.get(type(subject), subject.id)
    detail = {"error": str(exc), "code": getattr(exc, "code", "error"), **(getattr(exc, "detail", None) or {})}
    subject.error = detail
    try:
        move(db, subject, to, actor, "fail", {"code": detail["code"]})
    except TransitionError:
        audit(db, subject, "error", actor, {"code": detail["code"]})
    db.commit()


# =========================================================================== exports

def create_export(db: Session, actor: str, *, mode: str, workspaces: list[str], classifications: list[str],
                  destination: dict, decisions: Optional[dict] = None, base_export_id: Optional[str] = None,
                  cfg: Config) -> PortabilityExport:
    if mode not in exporter.MODES:
        raise ServiceError(f"unknown mode {mode!r}", "invalid", 422)
    if destination.get("repository") and destination["repository"] not in cfg.repositories:
        raise ServiceError(f"repository {destination['repository']!r} is not registered", "invalid", 422)
    if destination.get("artifact_store") and destination["artifact_store"] not in cfg.stores:
        raise ServiceError(f"artifact store {destination['artifact_store']!r} is not configured", "invalid", 422)
    if mode == "incremental":
        base = db.get(PortabilityExport, base_export_id or "")
        if base is None or base.state != "published":
            raise ServiceError("an incremental export needs a published base export", "invalid", 422)
        workspaces = list(base.workspaces)
        classifications = list(base.classifications)
    if mode not in ("full", "incremental") and not workspaces:
        raise ServiceError("choose at least one workspace", "invalid", 422)
    risk = "high" if mode in HIGH_RISK_MODES or classifications else "normal"
    exp = PortabilityExport(id=f"exp-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}", mode=mode,
                            workspaces=sorted(workspaces), classifications=sorted(classifications),
                            decisions=decisions or {}, destination=destination, state="requested", risk=risk,
                            requested_by=actor, base_export_id=base_export_id)
    db.add(exp)
    db.flush()
    audit(db, exp, "request", actor, {"mode": mode, "workspaces": exp.workspaces, "risk": risk,
                                      "classifications": exp.classifications}, None, "requested")
    return exp


def analyse_export(db: Session, exp: PortabilityExport, actor: str) -> PortabilityExport:
    from app.models.workspace import Workspace
    move(db, exp, "analysing", actor, "analyse")
    ws = exp.workspaces
    if exp.mode == "full" or (exp.mode == "incremental" and db.get(PortabilityExport, exp.base_export_id).mode == "full"):
        ws = sorted(db.scalars(select(Workspace.id).where(Workspace.import_state.is_(None))))
    sc = Scope(workspaces=list(ws), watermark={})
    restriction = exporter.restrict(db, sc, exp.classifications)
    analysis = closure.resolve(db, sc, exp.decisions or {})
    estimate = _estimate(db, sc)
    exp.analysis = {"closure": analysis, "restriction": restriction, "estimate": estimate,
                    "ready": not analysis["unresolved"] and not analysis["blocked"],
                    "warnings": _warnings(exp, restriction, analysis)}
    move(db, exp, "awaiting_approval", actor, "analysed", {"ready": exp.analysis["ready"]})
    return exp


def _estimate(db: Session, sc: Scope) -> dict:
    from sqlalchemy import func

    from app.models.asset import Asset
    from app.models.attachment import Attachment
    from app.models.issue import Issue
    from app.models.ledger import ClaimEvent
    return {"records": db.scalar(select(func.count()).select_from(Asset).where(Asset.workspace_id.in_(sc.workspaces))),
            "tickets": db.scalar(select(func.count()).select_from(Issue).where(Issue.workspace_id.in_(sc.workspaces))),
            "claim_events": db.scalar(select(func.count()).select_from(ClaimEvent).where(
                ClaimEvent.stream_id.in_(sc.streams()))),
            "attachments": db.scalar(select(func.count()).select_from(Attachment).where(
                Attachment.workspace_id.in_(sc.workspaces))),
            "attachment_bytes": int(db.scalar(select(func.coalesce(func.sum(Attachment.file_size), 0)).where(
                Attachment.workspace_id.in_(sc.workspaces))) or 0)}


def _warnings(exp: PortabilityExport, restriction: dict, analysis: dict) -> list[str]:
    out = []
    if restriction["excluded_classes"]:
        out.append(f"restricted classes left out: {', '.join(restriction['excluded_classes'])} — the archive is "
                   "not complete")
    if restriction["fields_hidden"]:
        out.append("restricted fields are hidden on some records — the archive is not complete")
    if exp.classifications:
        out.append(f"restricted classes included: {', '.join(exp.classifications)} — every reader of the "
                   "destination repository must hold them")
    if analysis["unresolved"]:
        out.append(f"{len(analysis['unresolved'])} dependencies need an outcome")
    if analysis.get("workspaces") and sorted(analysis["workspaces"]) != sorted(exp.workspaces) and exp.mode != "full":
        out.append(f"the closure adds workspaces: {', '.join(sorted(set(analysis['workspaces']) - set(exp.workspaces)))}")
    return out


def set_export_decisions(db: Session, exp: PortabilityExport, decisions: dict, actor: str) -> PortabilityExport:
    expect(exp, "awaiting_approval", "failed")
    bad = {k: v for k, v in decisions.items() if v not in closure.OUTCOMES}
    if bad:
        raise ServiceError(f"unknown outcomes {bad}", "invalid", 422)
    exp.decisions = {**(exp.decisions or {}), **decisions}
    audit(db, exp, "decide", actor, {"decisions": decisions})
    return analyse_export(db, exp, actor)


def approve_export(db: Session, exp: PortabilityExport, actor: str, *, admin: bool) -> PortabilityExport:
    if exp.state == "approved":
        return exp
    expect(exp, "awaiting_approval")
    if not admin:
        raise ServiceError("approving an export needs an instance administrator", "forbidden", 403)
    if exp.risk == "high" and actor == exp.requested_by:
        raise ServiceError("a high-risk export needs an approver other than its requester", "separation", 403)
    if not (exp.analysis or {}).get("ready"):
        raise ServiceError("dependencies still need an outcome", "closure", 409,
                           {"unresolved": exp.analysis.get("closure", {}).get("unresolved")})
    exp.approved_by = actor
    move(db, exp, "approved", actor, "approve", {"risk": exp.risk})
    return exp


def generate_export(engine: Engine, db: Session, exp: PortabilityExport, actor: str, cfg: Config) -> PortabilityExport:
    if exp.state in ("ready_to_publish", "published"):
        return exp
    expect(exp, "approved")
    if cfg.signer is None:
        raise ServiceError("no signing key is configured (ARGUS_PORTABILITY_SIGNING_KEY)", "no_signing_key", 409)
    move(db, exp, "generating", actor, "generate")
    db.commit()
    out = cfg.export_dir(exp.id)
    store = cfg.stores.get((exp.destination or {}).get("artifact_store") or "")
    base = None
    if exp.mode == "incremental":
        b = db.get(PortabilityExport, exp.base_export_id)
        base = {**b.manifest, "_sha256": b.manifest_sha256}
    try:
        if out.exists():
            shutil.rmtree(out)
        manifest = exporter.generate(engine, export_id=exp.id, mode=exp.mode, workspaces=exp.workspaces, out_dir=out,
                                     store=store, signer=cfg.signer, requested_by=exp.requested_by,
                                     approved_by=exp.approved_by, classifications=exp.classifications,
                                     decisions=exp.decisions, base_manifest=base,
                                     repository={"name": (exp.destination or {}).get("repository")})
        exp = db.get(PortabilityExport, exp.id)
        move(db, exp, "verifying", actor, "generated", {"watermark": manifest["watermark"]["label"]})
        blob_dir = cfg.root / "verify" / exp.id
        checked = verifier.verify(out, trusted=cfg.trusted, stores=cfg.stores, blob_dir=blob_dir,
                                  limits=cfg.limits)
        shutil.rmtree(blob_dir, ignore_errors=True)
        exp.manifest = {k: v for k, v in manifest.items() if k != "_sha256"}
        exp.manifest_sha256 = manifest["_sha256"]
        exp.watermark = manifest["watermark"]
        exp.out_dir = str(out)
        move(db, exp, "ready_to_publish", actor, "verified", {"report": checked["report"]})
        db.commit()
    except Exception as e:  # noqa: BLE001 — every failure is recorded on the export
        shutil.rmtree(out, ignore_errors=True)
        _fail(db, exp, actor, e)
        raise ServiceError(str(e), getattr(e, "code", "export_failed"), 409, getattr(e, "detail", None)) from e
    return exp


def publish_export(db: Session, exp: PortabilityExport, actor: str, cfg: Config) -> PortabilityExport:
    if exp.state == "published":
        return exp
    expect(exp, "ready_to_publish")
    repo = (exp.destination or {}).get("repository")
    if repo not in cfg.repositories:
        raise ServiceError("this export has no registered destination repository", "invalid", 422)
    move(db, exp, "publishing", actor, "publish", {"repository": repo})
    db.commit()
    previous = None
    if exp.mode == "incremental":
        previous = (db.get(PortabilityExport, exp.base_export_id).git or {}).get("tag")
    manifest = {**exp.manifest, "_sha256": exp.manifest_sha256}
    try:
        pub = gitrepo.publish(Path(exp.out_dir), manifest, remote=cfg.repositories[repo], work=cfg.work(repo),
                              signer=cfg.signer, schemas=exporter.json_schemas(), previous_tag=previous)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        exp = db.get(PortabilityExport, exp.id)
        exp.error = {"error": str(e), "code": getattr(e, "code", "publish_failed"), **(getattr(e, "detail", None) or {})}
        move(db, exp, "ready_to_publish", actor, "publish_failed", {"code": exp.error["code"]})
        db.commit()
        raise ServiceError(str(e), getattr(e, "code", "publish_failed"), 409, getattr(e, "detail", None)) from e
    exp = db.get(PortabilityExport, exp.id)
    exp.git = {"repository": repo, "repository_id": pub.repository_id, "root_commit": pub.root_commit,
               "commit": pub.commit, "parent": pub.parent, "tag": pub.tag, "tag_object": pub.tag_object,
               "previous_tag": pub.previous_tag}
    move(db, exp, "published", actor, "published", exp.git)
    return exp


def _token_key() -> bytes:
    return (os.environ.get("TOKEN_PEPPER") or "argus-dev-pepper").encode()


def download_token(db: Session, exp: PortabilityExport, actor: str, ttl: int = 600) -> dict:
    expect(exp, "ready_to_publish", "published")
    expires = int(time.time()) + ttl
    msg = f"{exp.id}:{expires}:{actor}"
    sig = base64.urlsafe_b64encode(hmac.new(_token_key(), msg.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    token = base64.urlsafe_b64encode(msg.encode()).decode().rstrip("=") + "." + sig
    audit(db, exp, "download_token", actor, {"expires": expires})
    return {"token": token, "expires": expires}


def check_download_token(exp_id: str, token: str) -> str:
    try:
        body, sig = token.split(".", 1)
        msg = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
        export_id, expires, actor = msg.split(":", 2)
    except Exception as e:  # noqa: BLE001
        raise ServiceError("malformed download token", "forbidden", 403) from e
    want = base64.urlsafe_b64encode(hmac.new(_token_key(), msg.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    if not hmac.compare_digest(want, sig) or export_id != exp_id or int(expires) < time.time():
        raise ServiceError("the download token is not valid for this export, or has expired", "forbidden", 403)
    return actor


def archive_tar(exp: PortabilityExport) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for p in sorted(Path(exp.out_dir).iterdir()):
            tar.add(p, arcname=p.name, recursive=False)
    return buf.getvalue()


def revoke_export(db: Session, exp: PortabilityExport, actor: str, reason: str) -> PortabilityExport:
    move(db, exp, "revoked", actor, "revoke", {"reason": reason})
    return exp


def export_view(exp: PortabilityExport) -> dict:
    return {"id": exp.id, "mode": exp.mode, "state": exp.state, "risk": exp.risk, "workspaces": exp.workspaces,
            "classifications": exp.classifications, "base_export_id": exp.base_export_id,
            "destination": exp.destination, "decisions": exp.decisions, "requested_by": exp.requested_by,
            "approved_by": exp.approved_by, "analysis": exp.analysis, "watermark": exp.watermark,
            "manifest_sha256": exp.manifest_sha256, "git": exp.git, "error": exp.error,
            "labels": labels(exp.manifest, {"git_published": exp.state == "published",
                                            "verified": exp.state in ("ready_to_publish", "publishing", "published")}),
            "created_at": exp.created_at.isoformat() if exp.created_at else None}


# =========================================================================== imports

IMPORT_MODES = ("restore", "clone", "merge", "selective", "evidence")


def create_import(db: Session, actor: str, *, mode: str, source: dict, decisions: Optional[dict],
                  cfg: Config) -> PortabilityImport:
    if mode not in IMPORT_MODES:
        raise ServiceError(f"unknown mode {mode!r}", "invalid", 422)
    if source.get("repository") and source["repository"] not in cfg.repositories:
        raise ServiceError(f"repository {source['repository']!r} is not registered", "invalid", 422)
    imp = PortabilityImport(id=f"imp-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}", mode=mode,
                            source=source, state="created", requested_by=actor, decisions=decisions or {})
    db.add(imp)
    db.flush()
    imp.quarantine_dir = str(cfg.quarantine(imp.id))
    audit(db, imp, "request", actor, {"mode": mode, "source": source}, None, "created")
    return imp


def fetch_git(db: Session, imp: PortabilityImport, actor: str, cfg: Config) -> PortabilityImport:
    if imp.state == "quarantined":
        return imp
    expect(imp, "created")
    src = imp.source or {}
    url = cfg.repositories.get(src.get("repository") or "")
    if not url or not src.get("ref"):
        raise ServiceError("name a registered repository and a signed tag or commit", "invalid", 422)
    move(db, imp, "fetching", actor, "fetch", {"repository": src["repository"], "ref": src["ref"]})
    db.commit()
    try:
        if cfg.trusted is None:
            raise ServiceError("no trusted keys are configured (ARGUS_PORTABILITY_TRUSTED_KEYS)", "no_trusted_keys")
        got = gitrepo.fetch_into_quarantine(url, src["ref"], Path(imp.quarantine_dir), cfg.trusted, limits=cfg.limits)
        if src.get("expected_commit") and src["expected_commit"] != got.commit:
            raise ServiceError(f"{src['ref']} names {got.commit[:12]}, not the expected {src['expected_commit'][:12]}",
                               "unexpected_commit")
        if src.get("repository_id") and src["repository_id"] != got.repository_id:
            raise ServiceError("this is not the registered repository (its identity differs)", "repository_identity")
        if got.tag:
            seen = db.get(PortabilityTagSeen, (got.repository_id, got.tag))
            if seen is not None and (seen.commit != got.commit or seen.tag_object != got.tag_object):
                raise ServiceError(f"tag {got.tag} has moved since it was first imported here "
                                   f"(it named {seen.commit[:12]})", "moved_tag")
        if got.previous_tag and not gitrepo.has_commit(Path(imp.quarantine_dir), url, _tag_commit(
                Path(imp.quarantine_dir), url, got.previous_tag), got.commit):
            raise ServiceError(f"the previous export {got.previous_tag} is not in this repository's history",
                               "missing_commit")
    except Exception as e:  # noqa: BLE001
        _fail(db, imp, actor, e, to="invalid")
        raise ServiceError(str(e), getattr(e, "code", "fetch_failed"), 409, getattr(e, "detail", None)) from e
    imp = db.get(PortabilityImport, imp.id)
    imp.commit = got.commit
    imp.verification = {"git": {"repository_id": got.repository_id, "root_commit": got.root_commit,
                                "commit": got.commit, "tag": got.tag, "tag_object": got.tag_object,
                                "signed_by": got.signer, "export_id": got.export_id,
                                "previous_tag": got.previous_tag, "lfs_pointers": got.lfs}}
    move(db, imp, "quarantined", actor, "fetched", imp.verification["git"])
    return imp


def _tag_commit(qdir: Path, url: str, tag: str) -> str:
    repo = qdir / "repo.git"
    gitrepo.git(["fetch", "-q", "--no-tags", "--no-recurse-submodules", url, f"+refs/tags/{tag}:refs/tags/{tag}"],
                cwd=repo, check=False)
    r = gitrepo.git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"], cwd=repo, check=False)
    return r.stdout.strip() or "0" * 40


def upload(db: Session, imp: PortabilityImport, actor: str, data: bytes, cfg: Config) -> PortabilityImport:
    """A checkpoint as a tar of its files (no directories, no links): for archives that do not come
    from Git — an escrow copy. Signature verification still applies."""
    expect(imp, "created")
    out = Path(imp.quarantine_dir) / "checkpoint"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        for m in tar.getmembers():
            if not m.isfile() or "/" in m.name or not gitrepo.SAFE_NAME.match(m.name):
                raise ServiceError(f"the upload holds {m.name!r}, which is not a plain checkpoint file", "unsafe_upload")
            total += m.size
            if m.size > cfg.limits.max_file_bytes or total > cfg.limits.max_chunk_bytes * 8:
                raise ServiceError("the upload is too large", "too_large", 413)
            (out / m.name).write_bytes(tar.extractfile(m).read())
    imp.verification = {"upload": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}
    move(db, imp, "quarantined", actor, "uploaded", imp.verification["upload"])
    return imp


def verify_import(db: Session, imp: PortabilityImport, actor: str, cfg: Config) -> PortabilityImport:
    if imp.state in ("dry_run_ready", "awaiting_mapping"):
        return imp
    expect(imp, "quarantined")
    move(db, imp, "verifying", actor, "verify")
    db.commit()
    q = Path(imp.quarantine_dir)
    try:
        lfs = (imp.verification.get("git") or {}).get("lfs_pointers") or []
        checked = verifier.verify(q / "checkpoint", trusted=cfg.trusted, stores=cfg.stores, blob_dir=q / "blobs",
                                  lfs=lfs, limits=cfg.limits)
        _columns_known(q / "checkpoint", checked["manifest"], cfg.limits)
        git = imp.verification.get("git") or {}
        if git and git.get("export_id") != checked["manifest"]["export_id"]:
            raise ServiceError("the tag names another export than the manifest", "mismatch")
    except Exception as e:  # noqa: BLE001
        _fail(db, imp, actor, e, to="invalid")
        raise ServiceError(str(e), getattr(e, "code", "invalid"), 409, getattr(e, "detail", None)) from e
    imp = db.get(PortabilityImport, imp.id)
    imp.manifest = checked["manifest"]
    imp.verification = {**imp.verification, "checkpoint": checked["report"]}
    move(db, imp, "dry_run_ready", actor, "verified", {"report": checked["report"]})
    return imp


def _columns_known(checkpoint: Path, manifest: dict, limits: chunks.Limits) -> None:
    """Every column in the archive is one this importer knows: nothing is dropped silently."""
    from app.portability.families import BY_NAME
    for name, fam in manifest["families"].items():
        known = set(BY_NAME[name].columns)
        for c in fam["chunks"][:1]:
            for _, row in chunks.read_chunk(checkpoint / c["file"], name, limits):
                extra = set(row) - known
                if extra:
                    raise ServiceError(f"{name} carries columns this importer does not know: {sorted(extra)}",
                                       "incompatible")
                break


def _plan(db: Session, imp: PortabilityImport, cfg: Config) -> importer.Plan:
    q = Path(imp.quarantine_dir)
    return importer.Plan(import_id=imp.id, origin=imp.manifest["argus"]["instance_id"], mode=imp.mode,
                         checkpoint=q / "checkpoint", manifest=imp.manifest, blob_dir=q / "blobs",
                         attachments_dir=cfg.attachments_dir, decisions=imp.decisions or {})


def dry_run(db: Session, imp: PortabilityImport, actor: str, cfg: Config,
            decisions: Optional[dict] = None) -> PortabilityImport:
    expect(imp, "dry_run_ready", "awaiting_approval")
    if decisions:
        imp.decisions = {**(imp.decisions or {}), **decisions}
    plan = _plan(db, imp, cfg)
    report = {"mode": imp.mode, "export_id": imp.manifest["export_id"], "labels": imp.manifest["labels"]} \
        if imp.mode == "evidence" else importer.dry_run(db, plan)
    if imp.mode == "evidence":
        report["ready"] = True
        report["note"] = "evidence-only: kept read-only, nothing loaded into active state"
    if imp.mode == "restore":
        from app.models.workspace import Workspace
        others = [w for w in db.scalars(select(Workspace.id).where(Workspace.import_state.is_(None)))
                  if w not in plan.workspaces]
        if others:
            report.setdefault("blocking", []).append({"family": "instance", "key": "-", "reason":
                                                      "restore needs an empty instance; use clone or merge"})
            report["ready"] = False
    if imp.manifest["labels"].get("incremental") and imp.mode == "evidence":
        report["note"] += "; an increment as evidence is read alone"
    imp.dry_run = report
    imp.state = "dry_run_ready" if imp.state == "awaiting_approval" else imp.state
    audit(db, imp, "dry_run", actor, {"ready": report.get("ready"), "blocking": len(report.get("blocking", []))})
    if report.get("ready"):
        move(db, imp, "awaiting_approval", actor, "dry_run_ready")
    return imp


def approve_import(db: Session, imp: PortabilityImport, actor: str) -> PortabilityImport:
    if imp.state == "approved":
        return imp
    expect(imp, "awaiting_approval")
    restricted = bool((imp.manifest.get("classifications") or {}).get("included"))
    if (imp.mode in ("merge", "restore") or restricted) and actor == imp.requested_by:
        raise ServiceError("this import needs an approver other than its requester", "separation", 403)
    imp.approved_by = actor
    move(db, imp, "approved", actor, "approve")
    return imp


def execute(db: Session, imp: PortabilityImport, actor: str, cfg: Config,
            stop_after: Optional[int] = None) -> PortabilityImport:
    if imp.state in ("ready_to_finalize", "finalized"):
        return imp
    expect(imp, "approved", "importing", "failed")
    if imp.state != "importing":
        move(db, imp, "importing", actor, "execute" if imp.state == "approved" else "resume")
        db.commit()
    if imp.mode == "evidence":
        dest = cfg.evidence(imp.id)
        if not dest.exists():
            shutil.copytree(Path(imp.quarantine_dir), dest, ignore=shutil.ignore_patterns("repo.git"))
        move(db, imp, "rebuilding", actor, "evidence_stored", {"path": dest.name})
        move(db, imp, "reconciling", actor, "no_projection")
        imp.reconciliation = {"passed": True, "evidence_only": True, "export_id": imp.manifest["export_id"]}
        _sign_report(imp, cfg)
        move(db, imp, "ready_to_finalize", actor, "reconciled", {"passed": True})
        db.commit()
        return imp
    plan = _plan(db, imp, cfg)
    if importer.chain_status(db, plan).get("status") == "already_applied":
        imp.reconciliation = {"passed": True, "already_applied": True, "export_id": imp.manifest["export_id"]}
        _sign_report(imp, cfg)
        move(db, imp, "rebuilding", actor, "already_applied")
        move(db, imp, "reconciling", actor, "already_applied")
        move(db, imp, "ready_to_finalize", actor, "reconciled", {"passed": True, "identical_history": True})
        db.commit()
        return imp
    done = set((imp.checkpoints or {}).get("done") or [])
    deferred = list((imp.checkpoints or {}).get("deferred") or [])

    def save(steps: set):
        row = db.get(PortabilityImport, imp.id)
        row.checkpoints = {"done": sorted(steps), "deferred": deferred}
        db.commit()

    try:
        report = importer.execute(db, plan, done, save, stop_after=stop_after)
        deferred += report["deferred"]
        save(done)
    except InterruptedError as e:
        db.rollback()
        row = db.get(PortabilityImport, imp.id)
        row.error = {"error": str(e), "code": "interrupted"}
        audit(db, row, "interrupted", actor, {"done": len(done)})
        db.commit()
        raise ServiceError(str(e), "interrupted", 409) from e
    except Exception as e:  # noqa: BLE001
        _fail(db, imp, actor, e)
        raise ServiceError(str(e), getattr(e, "code", "import_failed"), 409, getattr(e, "detail", None)) from e
    imp = db.get(PortabilityImport, imp.id)
    move(db, imp, "rebuilding", actor, "loaded", {"steps": len(done)})
    try:
        rebuilt = importer.rebuild(db, plan)
        imp = db.get(PortabilityImport, imp.id)
        move(db, imp, "reconciling", actor, "rebuilt", rebuilt)
        rec = importer.reconcile(db, plan, deferred)
        rec["rebuild"] = rebuilt
        rec["git"] = (imp.verification or {}).get("git")
        imp.reconciliation = rec
        _sign_report(imp, cfg)
        move(db, imp, "ready_to_finalize" if rec["passed"] else "failed", actor, "reconciled",
             {"passed": rec["passed"], "sha256": imp.reconciliation_sha256})
        db.commit()
    except Exception as e:  # noqa: BLE001
        _fail(db, imp, actor, e)
        raise ServiceError(str(e), getattr(e, "code", "import_failed"), 409, getattr(e, "detail", None)) from e
    return imp


def _sign_report(imp: PortabilityImport, cfg: Config) -> None:
    body = json.dumps({k: v for k, v in imp.reconciliation.items() if k != "signature"}, sort_keys=True, default=str)
    imp.reconciliation_sha256 = hashlib.sha256(body.encode()).hexdigest()
    if cfg.signer is not None:
        manifest_sha = ((imp.verification or {}).get("checkpoint") or {}).get("manifest_sha256", "")
        imp.reconciliation = {**imp.reconciliation, "signature": signing.sign_checkpoint(
            cfg.signer, imp.reconciliation_sha256, manifest_sha)}


def finalize(db: Session, imp: PortabilityImport, actor: str, cfg: Config) -> PortabilityImport:
    if imp.state == "finalized":
        return imp
    expect(imp, "ready_to_finalize")
    if not (imp.reconciliation or {}).get("passed"):
        raise ServiceError("the reconciliation did not pass", "reconciliation_failed")
    if imp.mode != "evidence" and not imp.reconciliation.get("already_applied"):
        plan = _plan(db, imp, cfg)
        importer.finalize(db, plan)
        if imp.mode == "restore":
            from app.models.app_setting import AppSetting
            row = db.get(AppSetting, exporter.INSTANCE_KEY)
            value = {"id": imp.manifest["argus"]["instance_id"], "name": imp.manifest["argus"].get("instance_name"),
                     "restored_from": imp.manifest["export_id"]}
            if row is None:
                db.add(AppSetting(key=exporter.INSTANCE_KEY, value=value))
            else:
                row.value = value
    git = (imp.verification or {}).get("git") or {}
    if git.get("tag") and db.get(PortabilityTagSeen, (git["repository_id"], git["tag"])) is None:
        db.add(PortabilityTagSeen(repository_id=git["repository_id"], tag=git["tag"], commit=git["commit"],
                                  tag_object=git["tag_object"], import_id=imp.id))
    move(db, imp, "finalized", actor, "finalize", {"reconciliation_sha256": imp.reconciliation_sha256})
    if imp.mode != "evidence":
        shutil.rmtree(Path(imp.quarantine_dir), ignore_errors=True)
    return imp


def discard(db: Session, imp: PortabilityImport, actor: str, cfg: Config) -> PortabilityImport:
    if imp.state == "discarded":
        return imp
    if imp.state == "finalized":
        raise ServiceError("a finalized import is history: correct it with ledger decisions", "finalized")
    origin = (imp.manifest or {}).get("argus", {}).get("instance_id", "")
    result = importer.discard(db, origin, imp.id)
    move(db, imp, "discarded", actor, "discard", result)
    shutil.rmtree(Path(imp.quarantine_dir), ignore_errors=True)
    return imp


def import_view(imp: PortabilityImport) -> dict:
    m = imp.manifest or {}
    git = (imp.verification or {}).get("git") or {}
    return {"id": imp.id, "mode": imp.mode, "state": imp.state, "source": imp.source, "commit": imp.commit,
            "requested_by": imp.requested_by, "approved_by": imp.approved_by, "decisions": imp.decisions,
            "manifest": {k: m.get(k) for k in ("export_id", "mode", "workspaces", "watermark", "argus", "labels",
                                                 "classifications", "base", "blobs")} if m else None,
            "verification": imp.verification, "dry_run": imp.dry_run,
            "checkpoints": {"done": len((imp.checkpoints or {}).get("done") or [])},
            "reconciliation_passed": (imp.reconciliation or {}).get("passed"),
            "reconciliation_sha256": imp.reconciliation_sha256, "error": imp.error,
            "labels": labels(m, {"git_published": bool(git.get("tag")),
                                 "verified": imp.state not in ("created", "fetching", "quarantined", "verifying",
                                                               "invalid")}),
            "created_at": imp.created_at.isoformat() if imp.created_at else None}


def provenance(db: Session, imp: PortabilityImport) -> dict:
    events = db.scalars(select(PortabilityEvent).where(PortabilityEvent.subject_kind == "import",
                                                       PortabilityEvent.subject_id == imp.id)
                        .order_by(PortabilityEvent.seq))
    return {"import": import_view(imp), "git": (imp.verification or {}).get("git"),
            "origin": (imp.manifest or {}).get("argus"), "watermark": (imp.manifest or {}).get("watermark"),
            "reconciliation_sha256": imp.reconciliation_sha256,
            "events": [{"seq": e.seq, "kind": e.kind, "from": e.from_state, "to": e.to_state, "actor": e.actor,
                        "at": e.at.isoformat(), "detail": e.detail} for e in events]}


def evidence_rows(imp: PortabilityImport, cfg: Config, family: str, offset: int, limit: int) -> dict:
    expect(imp, "finalized")
    if imp.mode != "evidence":
        raise ServiceError("only an evidence import is browsed from its archive", "invalid", 422)
    fam = (imp.manifest or {}).get("families", {}).get(family)
    if fam is None:
        raise ServiceError(f"no family {family!r} in this archive", "not_found", 404)
    rows, i = [], 0
    for c in fam["chunks"]:
        for key, row in chunks.read_chunk(cfg.evidence(imp.id) / "checkpoint" / c["file"], family, cfg.limits):
            if i >= offset and len(rows) < limit:
                rows.append({"key": key, "row": row})
            i += 1
    return {"family": family, "total": fam["rows"], "offset": offset, "rows": rows}
