"""The dependency closure of a selective export: deterministic rules, explicit outcomes.

Every reference from what is exported to something outside it becomes a *dependency*, grouped by
rule and by the workspace that holds the target. Each needs an outcome before generation:

  include_workspace    the target's workspace joins the export (and its own closure is computed)
  external_reference   the reference stays as a uid; an importer resolves it against what it holds,
                       and refuses (or defers, by its own decision) what it cannot resolve
  exclude_referrers    (restricted targets only) rows naming a restricted record left out of the
                       export are left out too, so neither the record nor its existence travels
  block                the export does not run

Rules applied automatically, and recorded as such:

  catalogue            a type used by an exported record comes with it, with its ancestors
  actor                a person named by an exported row comes as a historical identity reference
  subject decisions    a decision about an exported record comes with it, wherever it was recorded

Nothing is chosen silently: generation refuses while a dependency has no outcome or `block`.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation
from app.models.document import Document, DocumentRelation
from app.models.issue import Issue, IssueLink
from app.models.ledger import Claim, IdentityBinding, LedgerStream, TicketLink
from app.models.schema import Schema
from app.portability.families import Scope

OUTCOMES = {"include_workspace", "external_reference", "exclude_referrers", "block"}
RESTRICTED_OUTCOMES = {"exclude_referrers", "block"}
EXAMPLES = 5


def _owner(db: Session, uid: str) -> Optional[str]:
    for model in (Asset, Issue, Document):
        ws = db.scalar(select(model.workspace_id).where(model.uid == uid))
        if ws is not None:
            return ws
    return None


def analyse(db: Session, sc: Scope, decisions: dict) -> dict:
    """{"dependencies": [...], "automatic": [...], "unresolved": [ids], "blocked": [ids],
    "include": [workspaces to add]}"""
    scope = set(sc.workspaces)
    deps: dict[str, dict] = {}

    def need(rule: str, source: str, target: str, restricted: bool = False):
        if restricted:
            dep_id = "restricted_reference"
            ws = None
        else:
            ws = _owner(db, target)
            if ws in scope:
                return
            dep_id = f"{rule}:{ws or 'missing'}"
        d = deps.setdefault(dep_id, {"id": dep_id, "rule": rule if not restricted else "restricted_reference",
                                     "workspace": ws, "count": 0, "examples": [],
                                     "options": sorted(RESTRICTED_OUTCOMES if restricted else
                                                       ({"external_reference", "block"} if ws is None else
                                                        {"include_workspace", "external_reference", "block"}))})
        d["count"] += 1
        if len(d["examples"]) < EXAMPLES:
            d["examples"].append({"from": source, "to": target if not restricted else "(restricted)"})

    def check(source: str, target: Optional[str], rule: str):
        if not target:
            return
        if target in sc.excluded_uids:
            need(rule, source, target, restricted=True)
        else:
            need(rule, source, target)

    in_scope = sc.assets()
    for uid, survivor in db.execute(select(Asset.uid, Asset.merged_into_uid).where(
            Asset.workspace_id.in_(scope), Asset.merged_into_uid.isnot(None))):
        if uid not in sc.excluded_uids:
            check(uid, survivor, "merge_survivor")
    for r in db.scalars(select(Relation).where(Relation.workspace_id.in_(scope))):
        if r.from_asset_uid in sc.excluded_uids or r.to_asset_uid in sc.excluded_uids:
            need("relation_endpoint", r.from_asset_uid if r.from_asset_uid not in sc.excluded_uids
                 else r.to_asset_uid, "", restricted=True)
            continue
        rule = "relation_endpoint" if r.derivation is None else "derived_endpoint"
        check(r.from_asset_uid, r.to_asset_uid, rule)
        check(r.to_asset_uid, r.from_asset_uid, rule)
    for uid, subject in db.execute(select(Issue.uid, Issue.asset_uid).where(Issue.workspace_id.in_(scope))):
        if uid not in sc.excluded_uids:
            check(uid, subject, "ticket_subject")
    for frm, to in db.execute(select(IssueLink.from_issue_uid, IssueLink.to_issue_uid).where(
            IssueLink.from_issue_uid.in_(sc.issues()))):
        if frm not in sc.excluded_uids:
            check(frm, to, "ticket_link")
    for t, a in db.execute(select(TicketLink.ticket_uid, TicketLink.asset_uid).where(
            TicketLink.workspace_id.in_(scope))):
        if t not in sc.excluded_uids:
            check(t, a, "ticket_involves")
    for uid, a in db.execute(select(Document.uid, Document.responsible_service_asset_uid).where(
            Document.workspace_id.in_(scope))):
        check(uid, a, "document_subject")
    for frm, kind, to in db.execute(select(DocumentRelation.from_document_uid, DocumentRelation.to_type,
                                           DocumentRelation.to_uid).where(DocumentRelation.workspace_id.in_(scope))):
        if kind in ("asset", "issue", "document", "ticket"):
            check(frm, to, "document_relation")

    # The ledger: claims of exported streams about records elsewhere, and claims of other streams
    # about exported records (their projection depends on them).
    bound = {ref: uid for ref, uid in db.execute(select(IdentityBinding.source_ref, IdentityBinding.uid).where(
        IdentityBinding.source_ref.in_(select(Claim.source_ref).where(Claim.stream_id.in_(sc.streams())))))}
    for ref, uid in bound.items():
        if uid in sc.excluded_uids:
            continue
        check(ref, uid, "claim_subject")
    foreign = db.execute(select(Claim.stream_id, IdentityBinding.uid).join(
        IdentityBinding, IdentityBinding.source_ref == Claim.source_ref).where(
        IdentityBinding.uid.in_(in_scope), Claim.stream_id.not_in(sc.streams())).distinct())
    for stream_id, uid in foreign:
        ws = db.scalar(select(LedgerStream.workspace_id).where(LedgerStream.id == stream_id))
        if ws not in scope:
            dep_id = f"foreign_claims:{ws}"
            d = deps.setdefault(dep_id, {"id": dep_id, "rule": "foreign_claims", "workspace": ws, "count": 0,
                                         "examples": [], "options": ["block", "include_workspace"]})
            d["count"] += 1
            if len(d["examples"]) < EXAMPLES:
                d["examples"].append({"from": stream_id, "to": uid})

    automatic = []
    shared = sorted({s.workspace_id for s in db.scalars(
        select(Schema).where(Schema.uid.in_(select(Asset.schema_uid).where(Asset.workspace_id.in_(scope)))))} - scope)
    if shared:
        automatic.append({"rule": "catalogue", "outcome": "include", "detail": f"types owned by {', '.join(shared)}"})
    automatic.append({"rule": "actor", "outcome": "include",
                      "detail": "people named by exported rows travel as historical identity references"})
    automatic.append({"rule": "subject_decisions", "outcome": "include",
                      "detail": "decisions about exported records travel with them"})

    out = sorted(deps.values(), key=lambda d: d["id"])
    unresolved, blocked, include = [], [], []
    for d in out:
        outcome = decisions.get(d["id"])
        d["outcome"] = outcome
        if outcome is None:
            unresolved.append(d["id"])
        elif outcome not in d["options"]:
            unresolved.append(d["id"])
            d["problem"] = f"{outcome!r} is not an outcome for this dependency ({', '.join(d['options'])})"
        elif outcome == "block":
            blocked.append(d["id"])
        elif outcome == "include_workspace" and d["workspace"]:
            include.append(d["workspace"])
        elif outcome == "external_reference":
            for ex in d["examples"]:
                sc.external_refs[ex["to"]] = d["id"]
    return {"dependencies": out, "automatic": automatic, "unresolved": unresolved, "blocked": blocked,
            "include": sorted(set(include))}


def resolve(db: Session, sc: Scope, decisions: dict, limit: int = 20) -> dict:
    """Analyse, add the workspaces `include_workspace` names, and analyse again until nothing new
    joins. The returned analysis is the final one; `sc.workspaces` is updated in place."""
    for _ in range(limit):
        result = analyse(db, sc, decisions)
        new = [w for w in result["include"] if w not in sc.workspaces]
        if not new:
            result["workspaces"] = list(sc.workspaces)
            return result
        sc.workspaces = sorted(set(sc.workspaces) | set(new))
    raise ValueError("the dependency closure did not settle")

