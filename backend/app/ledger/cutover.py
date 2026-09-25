"""Moving a domain from Jira or Insight to ARGUS (asset-model-revision §16, §17).

A **domain** is one scope (a workspace's objects, or its tickets) and its
source streams. It moves through the stages

    T0 Prepare → T1 Import and reconcile → T2 Shadow validation
    → T3 Cutover (streams frozen at the watermark W) → exit signed
    → T4 Archive → T5 Retire

No dual write: from T1 until the exit is signed ARGUS holds the scope
read-only, and only migration decisions are recorded. After the freeze a
stream accepts no revision (I-SOR-1). The exit is signed only when the
final reconciliation report shows no unexplained difference and every
criterion of §17.5 holds; it is an `approve_cutover` decision.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.ledger.engine import LedgerError, canonical, now
from app.models.asset import Asset
from app.models.attachment import Attachment
from app.models.issue import Issue, IssueComment, IssueHistory, IssueLink
from app.models.ledger import (Conflict, Decision, LedgerDomain, LedgerStream, ReconciliationReport,
                               RevisionEvent, SourceRevision, StreamHead)
from app.models.user import User

STAGES = ("T0", "T1", "T2", "T3", "T4", "T5")
STAGE_NAMES = {"T0": "Prepare", "T1": "Import and reconcile", "T2": "Shadow validation", "T3": "Cutover",
               "T4": "Archive", "T5": "Retire Jira"}
# What a person must attest at exit: things ARGUS cannot observe itself (§17.5).
ATTESTATIONS = {
    "jira_write_refused": "A write attempt against the Jira or Insight scope fails",
    "smoke_tests": "Create, edit, search, link (and a complete ticket workflow) pass in ARGUS",
    "export_verified": "The immutable export has been taken and its checksums verified",
}


class ReadOnlyScope(LedgerError):
    code = "I-SOR-1"


# --------------------------------------------------------------------------- domains and stages

def create_domain(db: Session, workspace_id: str, domain_id: str, name: str, *, resource: str = "objects",
                  stream_ids: Optional[list] = None, pilot: bool = False,
                  archive_url: Optional[str] = None) -> LedgerDomain:
    if db.get(LedgerDomain, domain_id) is not None:
        raise LedgerError(f"domain {domain_id} exists")
    for sid in stream_ids or []:
        stream = db.get(LedgerStream, sid)
        if stream is None or stream.workspace_id != workspace_id:
            raise LedgerError(f"stream {sid} is not a stream of this workspace")
    d = LedgerDomain(id=domain_id, workspace_id=workspace_id, name=name, resource=resource, stage="T0",
                     stream_ids=list(stream_ids or []), pilot=pilot, archive_url=archive_url, created_at=now())
    db.add(d)
    db.flush()
    return d


def advance(db: Session, domain_id: str, stage: str, actor: str) -> LedgerDomain:
    """Move a domain one stage on. T3 is entered only by freezing, T4 only
    after the exit is signed; going back is an abort (before the exit)."""
    d = _domain(db, domain_id)
    if stage not in STAGES:
        raise LedgerError(f"unknown stage {stage}")
    current, target = STAGES.index(d.stage), STAGES.index(stage)
    if target == current:
        return d
    if target < current:
        if d.exited_at is not None:
            raise LedgerError("after the exit there is no rollback to Jira; correct errors with ledger decisions")
        if target < STAGES.index("T1"):
            raise LedgerError("an aborted cutover returns to T1 or T2")
        for sid in d.stream_ids:
            db.get(LedgerStream, sid).frozen_at = None
        d.frozen_at = None
        engine._record_decision(db, "abort_cutover", actor, d.workspace_id,
                                target={"domain": d.id, "from": d.stage, "to": stage})
    else:
        if target != current + 1:
            raise LedgerError(f"{d.stage} can only move to {STAGES[current + 1]}")
        if stage == "T3":
            raise LedgerError("T3 starts by freezing the streams at the watermark")
        if stage in ("T4", "T5") and d.exited_at is None:
            raise LedgerError("the cutover exit must be signed first")
        engine._record_decision(db, "advance_domain", actor, d.workspace_id,
                                target={"domain": d.id, "from": d.stage, "to": stage})
    d.stage = stage
    db.flush()
    return d


def _domain(db: Session, domain_id: str) -> LedgerDomain:
    d = db.get(LedgerDomain, domain_id)
    if d is None:
        raise LedgerError(f"unknown domain {domain_id}")
    return d


def domains_of(db: Session, workspace_id: str, resource: Optional[str] = None) -> list[LedgerDomain]:
    q = select(LedgerDomain).where(LedgerDomain.workspace_id == workspace_id)
    if resource:
        q = q.where(LedgerDomain.resource == resource)
    return list(db.scalars(q))


def authoritative(db: Session, workspace_id: str, resource: str = "objects") -> bool:
    """ARGUS is the system of record for this scope: its exit is signed."""
    return any(d.exited_at is not None for d in domains_of(db, workspace_id, resource))


def assert_writable(db: Session, workspace_id: str, resource: str = "objects") -> None:
    """No dual write (§17.2): between import and the signed exit, ARGUS holds
    the scope read-only; only migration decisions are recorded."""
    for d in domains_of(db, workspace_id, resource):
        if d.exited_at is None and d.stage in ("T1", "T2", "T3"):
            raise ReadOnlyScope(f"{d.name} is a read-only mirror of its source until its cutover exit is signed "
                                f"(stage {d.stage} {STAGE_NAMES[d.stage]})")


# --------------------------------------------------------------------------- freeze (§17.3)

def freeze(db: Session, domain_id: str, actor: str, watermark: dict, manifest: dict) -> LedgerDomain:
    """Record W and the export manifest's hash on each stream's final
    revision, then freeze the streams (I-SOR-1)."""
    d = _domain(db, domain_id)
    if d.stage not in ("T1", "T2"):
        raise LedgerError("a domain is frozen from T1 or T2")
    if not watermark:
        raise LedgerError("the watermark W is required")
    manifest_hash = hash_manifest(manifest)
    for sid in d.stream_ids:
        head = db.get(StreamHead, sid)
        held = [r.id for r in db.scalars(select(SourceRevision).where(SourceRevision.stream_id == sid))
                if engine.revision_state(db, r.id) == "held"]
        if held:
            raise LedgerError(f"{sid} has held revisions; the final delta must be decided before the freeze")
        if head is None or head.published_head is None:
            raise LedgerError(f"{sid} has published nothing")
        db.add(RevisionEvent(revision_id=head.published_head, stream_id=sid, kind="frozen", cause=f"cutover {d.id}",
                             detail={"watermark": watermark, "manifest_hash": manifest_hash}, at=now()))
        db.get(LedgerStream, sid).frozen_at = now()
    d.watermark, d.manifest_hash, d.frozen_at, d.stage = watermark, manifest_hash, now(), "T3"
    engine._record_decision(db, "freeze", actor, d.workspace_id, target={"domain": d.id, "streams": d.stream_ids},
                            value={"watermark": watermark, "manifest_hash": manifest_hash})
    db.flush()
    return d


def hash_manifest(manifest: dict) -> str:
    return hashlib.sha256(canonical(manifest).encode()).hexdigest()


# --------------------------------------------------------------------------- reconciliation (§17.6)

def _diff_id(section: str, item: str, message: str) -> str:
    return hashlib.sha256(canonical([section, item, message]).encode()).hexdigest()[:16]


def _explanations(db: Session, domain: LedgerDomain) -> dict[str, str]:
    ended = engine._ended(db, domain.workspace_id)
    out = {}
    for d in db.scalars(select(Decision).where(Decision.workspace_id == domain.workspace_id,
                                               Decision.kind == "explain_difference")):
        t = d.target or {}
        if d.decision_id not in ended and t.get("domain") == domain.id:
            out[t.get("difference")] = d.decision_id
    return out


def reconcile(db: Session, domain_id: str, manifest: dict, actor: str) -> ReconciliationReport:
    """Compare a source export manifest with ARGUS, per record type:

    * objects: every objectId and key resolves to an ARGUS record;
    * issues: every key resolves; comment, history and link counts match;
    * attachments: name, size and SHA-256 all match;
    * workflow states: every source status is mapped, and applied;
    * users: every referenced user resolves to an account.

    Each difference is unexplained (blocks the cutover) or explained by an
    `explain_difference` decision. The report is stored once, immutably."""
    from app.ledger import lookup
    d = _domain(db, domain_id)
    explained = _explanations(db, d)
    differences: list[dict] = []
    sections: dict[str, dict] = {}

    def diff(section: str, item: str, message: str, **detail):
        did = _diff_id(section, item, message)
        differences.append({"id": did, "section": section, "item": item, "message": message, **detail,
                            "explained_by": explained.get(did)})

    objects = manifest.get("objects") or []
    resolved = 0
    for o in objects:
        hit = lookup.resolve(db, str(o.get("objectId") or o.get("key")), [d.workspace_id], by_object_id=True)
        if hit is None:
            diff("objects", o.get("key") or str(o.get("objectId")), "unresolved identifier",
                 object_id=o.get("objectId"))
            continue
        resolved += 1
        if o.get("key") and lookup.resolve(db, o["key"], [d.workspace_id]) is None:
            diff("objects", o["key"], "the key does not look up", object_id=o.get("objectId"))
    sections["objects"] = {"source": len(objects), "argus": resolved}

    issues = manifest.get("issues") or []
    status_map = manifest.get("status_map") or {}
    counts = {"issues": 0, "comments": [0, 0], "history": [0, 0], "links": [0, 0], "attachments": [0, 0]}
    for i in issues:
        key = i["key"]
        issue = db.scalar(select(Issue).where(Issue.workspace_id == d.workspace_id,
                                              Issue.attributes["argus_source_key"].astext == key))
        if issue is None:
            diff("issues", key, "unresolved identifier")
            continue
        counts["issues"] += 1
        for field, n in (("comments", db.scalar(select(func.count()).select_from(IssueComment)
                                                .where(IssueComment.issue_uid == issue.uid))),
                         ("history", db.scalar(select(func.count()).select_from(IssueHistory)
                                               .where(IssueHistory.issue_uid == issue.uid,
                                                      IssueHistory.backend_id.isnot(None)))),
                         ("links", db.scalar(select(func.count()).select_from(IssueLink).where(
                             (IssueLink.from_issue_uid == issue.uid) | (IssueLink.to_issue_uid == issue.uid))))):
            if field in i:
                counts[field][0] += i[field]
                counts[field][1] += n or 0
                if (n or 0) != i[field]:
                    diff(field, key, f"{i[field]} in the source, {n or 0} in ARGUS")
        stored = list(db.scalars(select(Attachment).where(Attachment.issue_uid == issue.uid)))
        for a in i.get("attachments") or []:
            counts["attachments"][0] += 1
            match = [s for s in stored if s.filename == a["name"] and s.sha256 == a.get("sha256")
                     and (a.get("size") is None or s.file_size == a["size"])]
            if match:
                counts["attachments"][1] += 1
            else:
                diff("attachments", f"{key}/{a['name']}", "missing or different in ARGUS",
                     sha256=a.get("sha256"), size=a.get("size"))
        if i.get("status") is not None:
            mapped = status_map.get(i["status"])
            if mapped is None:
                diff("statuses", key, f"source status {i['status']!r} is not mapped")
            elif issue.state != mapped:
                diff("statuses", key, f"state {issue.state!r}, expected {mapped!r} for {i['status']!r}")
    sections["issues"] = {"source": len(issues), "argus": counts["issues"]}
    for field in ("comments", "history", "links", "attachments"):
        sections[field] = {"source": counts[field][0], "argus": counts[field][1]}

    users = manifest.get("users") or []
    found = 0
    for u in users:
        if db.scalar(select(User.id).where((User.email == u) | (User.id == u)).limit(1)):
            found += 1
        else:
            diff("users", u, "not resolved to an account or a restricted placeholder")
    sections["users"] = {"source": len(users), "argus": found}

    unexplained = [x for x in differences if not x["explained_by"]]
    body = {"domain": d.id, "workspace_id": d.workspace_id, "manifest_hash": hash_manifest(manifest),
            "watermark": manifest.get("watermark"), "sections": sections, "differences": differences,
            "unexplained": len(unexplained), "passed": not unexplained, "at": now().isoformat()}
    report = ReconciliationReport(id=str(uuid.uuid4()), domain_id=d.id, manifest_hash=body["manifest_hash"],
                                  passed=body["passed"], body=body,
                                  body_hash=hashlib.sha256(canonical(body).encode()).hexdigest(), actor=actor,
                                  created_at=now())
    db.add(report)
    db.flush()
    return report


def latest_report(db: Session, domain_id: str) -> Optional[ReconciliationReport]:
    return db.scalar(select(ReconciliationReport).where(ReconciliationReport.domain_id == domain_id)
                     .order_by(ReconciliationReport.created_at.desc()).limit(1))


# --------------------------------------------------------------------------- exit (§17.5)

def exit_criteria(db: Session, domain_id: str, attestations: Optional[dict] = None) -> list[dict]:
    d = _domain(db, domain_id)
    attestations = attestations or {}
    report = latest_report(db, domain_id)
    streams = [db.get(LedgerStream, sid) for sid in d.stream_ids]
    blocking = db.scalar(select(func.count()).select_from(Conflict).where(
        Conflict.workspace_id == d.workspace_id, Conflict.severity == "blocking")) or 0
    held = sum(1 for s in streams for r in db.scalars(select(SourceRevision).where(SourceRevision.stream_id == s.id))
               if engine.revision_state(db, r.id) == "held")
    unresolved = [x for x in (report.body["differences"] if report else [])
                  if x["message"] == "unresolved identifier" and not x["explained_by"]]
    out = [
        {"id": "frozen", "text": "W is recorded, the final delta consumed and the streams frozen",
         "ok": bool(d.watermark) and bool(streams) and all(s.frozen_at for s in streams)},
        {"id": "report", "text": "The final reconciliation report shows zero unexplained differences",
         "ok": bool(report and report.passed and report.manifest_hash == d.manifest_hash),
         "detail": {"report_id": report.id if report else None,
                    "unexplained": report.body["unexplained"] if report else None,
                    "same_manifest": bool(report and report.manifest_hash == d.manifest_hash)}},
        {"id": "identifiers", "text": "Every identifier in scope resolves to an ARGUS record",
         "ok": bool(report) and not unresolved, "detail": {"unresolved": len(unresolved)}},
        {"id": "queues", "text": "No blocking conflict or held revision is open",
         "ok": blocking == 0 and held == 0, "detail": {"blocking": blocking, "held": held}},
    ]
    for key, text in ATTESTATIONS.items():
        out.append({"id": key, "text": text, "ok": bool(attestations.get(key)), "attested": True})
    return out


def sign_exit(db: Session, domain_id: str, actor: str, attestations: dict) -> LedgerDomain:
    """The domain owner and the platform lead sign; ARGUS becomes the system
    of record for the scope and editing opens."""
    d = _domain(db, domain_id)
    if d.stage != "T3" or d.exited_at is not None:
        raise LedgerError("only a frozen domain awaiting its exit can be signed")
    unmet = [c for c in exit_criteria(db, domain_id, attestations) if not c["ok"]]
    if unmet:
        raise LedgerError("exit criteria not met: " + "; ".join(c["text"] for c in unmet))
    report = latest_report(db, domain_id)
    decision = engine._record_decision(db, "approve_cutover", actor, d.workspace_id,
                                       target={"domain": d.id, "report": report.id},
                                       value={"attestations": attestations})
    d.exited_at, d.exit_decision_id = now(), decision.decision_id
    db.flush()
    return d


def domain_view(db: Session, d: LedgerDomain) -> dict:
    report = latest_report(db, d.id)
    return {"id": d.id, "workspace_id": d.workspace_id, "name": d.name, "resource": d.resource, "stage": d.stage,
            "stage_name": STAGE_NAMES[d.stage], "stream_ids": d.stream_ids, "pilot": d.pilot,
            "archive_url": d.archive_url, "watermark": d.watermark, "manifest_hash": d.manifest_hash,
            "frozen_at": d.frozen_at, "exited_at": d.exited_at, "authoritative": d.exited_at is not None,
            "latest_report": {"id": report.id, "passed": report.passed, "created_at": report.created_at,
                              "unexplained": report.body["unexplained"], "body_hash": report.body_hash}
            if report else None,
            "streams": [{"id": s.id, "kind": s.kind, "frozen_at": s.frozen_at}
                        for s in (db.get(LedgerStream, sid) for sid in d.stream_ids) if s]}

