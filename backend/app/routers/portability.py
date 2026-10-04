"""Portable exports and imports (docs/export-import-design.md §12).

Mounted under /v1/portability/: /v1/imports already belongs to the Jira, Insight and Git import jobs.

People only: an API token cannot request, approve, generate, publish or import an archive. Creating
a workspace export needs the `approve` right on every workspace in it; a full export, approving,
generating, publishing, every import step and finalizing need an instance administrator; a
high-risk export (full, evidence-only, or with restricted classes) and a merge or restore import
need an approver other than the requester. Every step is a state transition, audited in
`portability_events`, and idempotent: a retried step returns the current state (and the
`Idempotency-Key` middleware replays the stored answer).
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import OidcIdentity, get_identity
from app.db import engine as db_engine
from app.db import get_db
from app.models.portability import PortabilityExport, PortabilityImport
from app.portability import service
from app.portability.lifecycle import TransitionError
from app.routers.ledger import actor_of
from app.services.permissions import resolve_permission

exports_router = APIRouter(prefix="/v1/portability/exports", tags=["portability"])
imports_router = APIRouter(prefix="/v1/portability/imports", tags=["portability"])


def _person(identity) -> OidcIdentity:
    if not isinstance(identity, OidcIdentity):
        raise HTTPException(status_code=403, detail={"error": "portable exports and imports are for people, not API "
                                                              "tokens", "code": "forbidden"})
    return identity


def _admin(identity) -> OidcIdentity:
    person = _person(identity)
    if not person.user.is_admin:
        raise HTTPException(status_code=403, detail={"error": "this needs an instance administrator",
                                                      "code": "forbidden"})
    return person


def _guard(fn):
    try:
        return fn()
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status, detail={"error": str(e), "code": e.code, **e.detail}) from e
    except TransitionError as e:
        raise HTTPException(status_code=e.status, detail={"error": str(e), "code": e.code}) from e


def _export(db: Session, export_id: str, identity) -> PortabilityExport:
    exp = db.get(PortabilityExport, export_id)
    person = _person(identity)
    if exp is None or not (person.user.is_admin or exp.requested_by == actor_of(person)):
        raise HTTPException(status_code=404, detail="Export not found")
    return exp


def _import(db: Session, import_id: str, identity) -> PortabilityImport:
    imp = db.get(PortabilityImport, import_id)
    _admin(identity)
    if imp is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return imp


def _commit(db: Session, view: dict) -> dict:
    db.commit()
    return view


config_router = APIRouter(prefix="/v1/portability", tags=["portability"])


@config_router.get("/config")
def portability_config(identity=Depends(get_identity)):
    """What a person can choose from: registered repositories and artifact stores (names only, never
    URLs or paths), whether signing and verification are set up, restricted classes, modes, outcomes."""
    _person(identity)
    from app.portability import closure, exporter, identity_policy
    from app.portability.blob_scan import DECISIONS as BLOB_OUTCOMES
    from app.services.visibility import RESTRICTED_CLASSES
    cfg = service.config()
    return {"repositories": sorted(cfg.repositories), "artifact_stores": sorted(cfg.stores),
            "signing": {"configured": cfg.signer is not None and cfg.signer.key_path.exists(),
                        "key_id": cfg.signer.key_id if cfg.signer is not None and cfg.signer.key_path.exists() else None,
                        "principal": cfg.signer.principal if cfg.signer is not None else None},
            "trusted_keys": cfg.trusted is not None and cfg.trusted.exists(),
            "restricted_classes": list(RESTRICTED_CLASSES),
            "restricted_destinations": {k: sorted(v) for k, v in cfg.restricted_destinations.items()
                                        if k in cfg.repositories},
            "encryption_recipients": sorted(k for k, v in cfg.recipients.items() if v.exists()),
            "identity_profiles": list(identity_policy.PROFILES), "default_identity_profile": identity_policy.DEFAULT,
            "blob_outcomes": list(BLOB_OUTCOMES), "step_up_seconds": cfg.step_up_seconds,
            "export_modes": [m for m in exporter.MODES if m != "backup-reference"],
            "import_modes": list(service.IMPORT_MODES), "outcomes": sorted(closure.OUTCOMES),
            "is_admin": bool(identity.user.is_admin)}


# --------------------------------------------------------------------------- exports

class ExportIn(BaseModel):
    mode: str = "workspace"
    workspaces: list[str] = Field(default_factory=list)
    classifications: list[str] = Field(default_factory=list)
    repository: Optional[str] = None
    artifact_store: Optional[str] = None
    decisions: dict = Field(default_factory=dict)
    base_export_id: Optional[str] = None
    identity_profile: Optional[str] = None


def _fresh(identity) -> bool:
    return isinstance(identity, OidcIdentity) and service.fresh(identity.claims, service.config())


NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff"}


@exports_router.post("", status_code=201)
def create_export(body: ExportIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    person = _person(identity)
    if body.mode in ("full",) or body.classifications or body.identity_profile == "full_identity":
        _admin(identity)
    for ws in body.workspaces:
        if not resolve_permission(db, person.user, ws, "approve", "objects"):
            raise HTTPException(status_code=403, detail={"error": f"exporting {ws} needs its approve right",
                                                          "code": "forbidden"})
    cfg = service.config()
    exp = _guard(lambda: service.create_export(
        db, actor_of(person), mode=body.mode, workspaces=body.workspaces, classifications=body.classifications,
        destination={"repository": body.repository, "artifact_store": body.artifact_store},
        decisions=body.decisions, base_export_id=body.base_export_id, identity_profile=body.identity_profile,
        cfg=cfg))
    _guard(lambda: service.analyse_export(db, exp, actor_of(person)))
    return _commit(db, service.export_view(exp))


@exports_router.get("")
def list_exports(identity=Depends(get_identity), db: Session = Depends(get_db)):
    person = _person(identity)
    q = select(PortabilityExport).order_by(PortabilityExport.created_at.desc()).limit(200)
    if not person.user.is_admin:
        q = q.where(PortabilityExport.requested_by == actor_of(person))
    return [service.export_view(e) for e in db.scalars(q)]


@exports_router.get("/{export_id}")
def get_export(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    return service.export_view(_export(db, export_id, identity))


class DecisionsIn(BaseModel):
    decisions: dict


@exports_router.post("/{export_id}/decisions")
def decide_export(export_id: str, body: DecisionsIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    exp = _export(db, export_id, identity)
    _guard(lambda: service.set_export_decisions(db, exp, body.decisions, actor_of(identity)))
    return _commit(db, service.export_view(exp))


@exports_router.post("/{export_id}/approve")
def approve_export(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    exp = _export(db, export_id, identity)
    _guard(lambda: service.approve_export(db, exp, actor_of(identity), admin=_person(identity).user.is_admin,
                                          fresh_auth=_fresh(identity), cfg=service.config()))
    return _commit(db, service.export_view(exp))


@exports_router.post("/{export_id}/generate")
def generate_export(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    _admin(identity)
    exp = _export(db, export_id, identity)
    exp = _guard(lambda: service.generate_export(db_engine, db, exp, actor_of(identity), service.config(),
                                                 fresh_auth=_fresh(identity)))
    return _commit(db, service.export_view(exp))


@exports_router.post("/{export_id}/publish-git")
def publish_export(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    _admin(identity)
    exp = _export(db, export_id, identity)
    exp = _guard(lambda: service.publish_export(db, exp, actor_of(identity), service.config()))
    return _commit(db, service.export_view(exp))


@exports_router.get("/{export_id}/manifest")
def export_manifest(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    exp = _export(db, export_id, identity)
    if exp.manifest is None:
        raise HTTPException(status_code=409, detail={"error": "not generated yet", "code": "not_ready"})
    return {"manifest": exp.manifest, "sha256": exp.manifest_sha256}


@exports_router.post("/{export_id}/download-token")
def download_token(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """A single-use, five-minute token for an out-of-band download (an operator's tool). Prefer
    `GET /archive` with your own credentials."""
    _admin(identity)
    exp = _export(db, export_id, identity)
    return _commit(db, _guard(lambda: service.download_token(db, exp, actor_of(identity))))


@exports_router.get("/{export_id}/archive")
def archive(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """The checkpoint's files as a tar, for the signed-in administrator: no capability in a URL."""
    from app.portability.lifecycle import audit
    _admin(identity)
    exp = _export(db, export_id, identity)
    if not exp.out_dir or exp.state not in ("ready_to_publish", "publishing", "published"):
        raise HTTPException(status_code=409, detail={"error": "not generated", "code": "not_ready"})
    audit(db, exp, "download", actor_of(identity), {"via": "session"})
    db.commit()
    return Response(service.archive_tar(exp), media_type="application/x-tar",
                    headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{exp.id}.tar"'})


@exports_router.get("/{export_id}/download")
def download(export_id: str, token: Optional[str] = Query(None), x_download_token: Optional[str] = Header(None),
             db: Session = Depends(get_db)):
    """The checkpoint as a tar, for a single-use token — preferably in the `X-Download-Token` header;
    in the query it is redacted from access logs. Used once, then refused."""
    exp = db.get(PortabilityExport, export_id)
    if exp is None or not exp.out_dir:
        raise HTTPException(status_code=404, detail="Export not found")
    _guard(lambda: service.consume_download_token(db, exp, x_download_token or token or ""))
    return Response(service.archive_tar(exp), media_type="application/x-tar",
                    headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{exp.id}.tar"'})


@exports_router.post("/{export_id}/download-tokens/revoke")
def revoke_tokens(export_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    _admin(identity)
    exp = _export(db, export_id, identity)
    n = service.revoke_download_tokens(db, exp, actor_of(identity))
    return _commit(db, {"revoked": n})


class RevokeIn(BaseModel):
    reason: str


@exports_router.post("/{export_id}/revoke")
def revoke_export(export_id: str, body: RevokeIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    _admin(identity)
    exp = _export(db, export_id, identity)
    _guard(lambda: service.revoke_export(db, exp, actor_of(identity), body.reason))
    return _commit(db, service.export_view(exp))


# --------------------------------------------------------------------------- imports

class ImportIn(BaseModel):
    mode: str = "clone"
    repository: Optional[str] = None
    ref: Optional[str] = None
    expected_commit: Optional[str] = None
    repository_id: Optional[str] = None
    decisions: dict = Field(default_factory=dict)


@imports_router.post("", status_code=201)
def create_import(body: ImportIn, identity=Depends(get_identity), db: Session = Depends(get_db)):
    person = _admin(identity)
    source = {k: v for k, v in {"repository": body.repository, "ref": body.ref, "expected_commit": body.expected_commit,
                                "repository_id": body.repository_id}.items() if v}
    imp = _guard(lambda: service.create_import(db, actor_of(person), mode=body.mode, source=source,
                                               decisions=body.decisions, cfg=service.config()))
    return _commit(db, service.import_view(imp))


@imports_router.get("")
def list_imports(identity=Depends(get_identity), db: Session = Depends(get_db)):
    _admin(identity)
    return [service.import_view(i) for i in db.scalars(
        select(PortabilityImport).order_by(PortabilityImport.created_at.desc()).limit(200))]


@imports_router.get("/{import_id}")
def get_import(import_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    return service.import_view(_import(db, import_id, identity))


def _step(name: str):
    def endpoint(import_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
        imp = _import(db, import_id, identity)
        cfg = service.config()
        actor = actor_of(identity)
        fn = {"fetch-git": lambda: service.fetch_git(db, imp, actor, cfg),
              "verify": lambda: service.verify_import(db, imp, actor, cfg),
              "approve": lambda: service.approve_import(db, imp, actor),
              "execute": lambda: service.execute(db, imp, actor, cfg),
              "resume": lambda: service.execute(db, imp, actor, cfg),
              "finalize": lambda: service.finalize(db, imp, actor, cfg)}[name]
        out = _guard(fn)
        return _commit(db, service.import_view(out))
    endpoint.__name__ = f"import_{name.replace('-', '_')}"
    return endpoint


for _name in ("fetch-git", "verify", "approve", "execute", "resume", "finalize"):
    imports_router.add_api_route(f"/{{import_id}}/{_name}", _step(_name), methods=["POST"])


class DiscardIn(BaseModel):
    reason: str = ""


@imports_router.post("/{import_id}/discard")
def discard(import_id: str, body: Optional[DiscardIn] = None, identity=Depends(get_identity),
            db: Session = Depends(get_db)):
    """Abandon an import: its staging database and quarantine go; its audit trail stays."""
    imp = _import(db, import_id, identity)
    out = _guard(lambda: service.discard(db, imp, actor_of(identity), service.config(), body.reason if body else ""))
    return _commit(db, service.import_view(out))


@imports_router.get("/{import_id}/origin-chain")
def origin_chain(import_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    """Recompute the origin chain of a finalized import from the rows here."""
    from app.portability import importer
    _import(db, import_id, identity)
    return importer.verify_chain(db, import_id)


class DryRunIn(BaseModel):
    decisions: dict = Field(default_factory=dict)


@imports_router.post("/{import_id}/dry-run")
def dry_run(import_id: str, body: Optional[DryRunIn] = None, identity=Depends(get_identity),
            db: Session = Depends(get_db)):
    imp = _import(db, import_id, identity)
    out = _guard(lambda: service.dry_run(db, imp, actor_of(identity), service.config(),
                                         (body.decisions if body else None)))
    return _commit(db, {**service.import_view(out), "dry_run": out.dry_run})


@imports_router.post("/{import_id}/upload")
async def upload(import_id: str, file: UploadFile = File(...), identity=Depends(get_identity),
                 db: Session = Depends(get_db)):
    imp = _import(db, import_id, identity)
    cfg = service.config()
    data = await file.read(cfg.limits.max_chunk_bytes * 8 + 1)
    out = _guard(lambda: service.upload(db, imp, actor_of(identity), data, cfg))
    return _commit(db, service.import_view(out))


@imports_router.get("/{import_id}/reconciliation")
def reconciliation(import_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    imp = _import(db, import_id, identity)
    if imp.reconciliation is None:
        raise HTTPException(status_code=409, detail={"error": "not reconciled yet", "code": "not_ready"})
    return {"report": imp.reconciliation, "sha256": imp.reconciliation_sha256}


@imports_router.get("/{import_id}/provenance")
def provenance(import_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    return service.provenance(db, _import(db, import_id, identity))


@imports_router.get("/{import_id}/evidence")
def evidence_families(import_id: str, identity=Depends(get_identity), db: Session = Depends(get_db)):
    imp = _import(db, import_id, identity)
    out = _guard(lambda: service.evidence_families(db, imp, service.config(), identity.user, actor_of(identity)))
    return _commit(db, out)


@imports_router.get("/{import_id}/evidence/{family}")
def evidence(import_id: str, family: str, offset: int = 0, limit: int = Query(50, le=500),
             identity=Depends(get_identity), db: Session = Depends(get_db)):
    imp = _import(db, import_id, identity)
    out = _guard(lambda: service.evidence_rows(db, imp, service.config(), family, offset, limit,
                                               viewer=identity.user, actor=actor_of(identity)))
    return _commit(db, out)


ROUTERS = (config_router, exports_router, imports_router)
