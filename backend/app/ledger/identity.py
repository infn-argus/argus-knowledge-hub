"""Identity reconciliation (asset-model-revision §10, D4).

* **Automatic binding on immutable identifiers.** An Insight object is bound
  by its objectId; when Insight re-keys it, the ARGUS record takes the new
  key and the old one becomes a `former_key` alias. No candidate is raised.
* **No automatic merging.** Different source objects sharing a strong
  identifier (serial per manufacturer, inventory number, MAC) become an
  `identity_candidate` review item. The steward merges, rejects the
  candidate, or confirms both as distinct.
* **Uniqueness at creation, after cutover.** Once ARGUS is the system of
  record for a scope, creating a record with a strong identifier an active
  record already holds is refused, pointing to that record (I-ID-1).
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Iterable, Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.ledger import engine
from app.ledger.engine import InvariantError, LedgerError, canonical, now
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetComment, AssetLabel, AssetTicket
from app.models.attachment import Attachment
from app.models.document import DocumentRelation
from app.models.issue import Issue
from app.models.ledger import (Conflict, ConflictEvent, Decision, IdentityBinding, LedgerStream, RecordEvent,
                               TicketLink)

IMMUTABLE_ID_KINDS = {"insight", "jira"}
INACTIVE = ("Merged", "Retired")
CANDIDATE = "identity_candidate"


def strong_identifiers(attributes: dict) -> list[tuple[str, str]]:
    """(name, normalized value) of a record's strong identifiers (§10)."""
    a = attributes or {}
    out = []
    # A serial is unique only per manufacturer; without one it is not strong.
    if a.get("serial") and a.get("manufacturer"):
        out.append(("serial", f"{str(a.get('manufacturer') or '').strip().lower()}|{str(a['serial']).strip()}"))
    if a.get("inventory_number"):
        out.append(("inventory_number", str(a["inventory_number"]).strip()))
    if a.get("mac"):
        out.append(("mac", str(a["mac"]).strip().lower().replace("-", ":")))
    return out


def _holders(db: Session, name: str, value: str, exclude: Optional[str] = None) -> list[Asset]:
    col = Asset.attributes
    if name == "serial":
        manufacturer, serial = value.split("|", 1)
        q = select(Asset).where(col["serial"].astext == serial)
        rows = [a for a in db.scalars(q)
                if str((a.attributes or {}).get("manufacturer") or "").strip().lower() == manufacturer]
    else:
        rows = list(db.scalars(select(Asset).where(col[name].astext.isnot(None))))
        rows = [a for a in rows if dict(strong_identifiers(a.attributes)).get(name) == value]
    return [a for a in rows if a.uid != exclude and a.record_status not in INACTIVE]


# --------------------------------------------------------------------------- re-keying (A34)

def maybe_rekey(db: Session, stream: LedgerStream, uid: str, exists_value, cause: str) -> None:
    """The source re-keyed an object it identifies immutably: follow it, and
    keep the old key as an alias so every old reference still resolves."""
    if stream.kind not in IMMUTABLE_ID_KINDS or not isinstance(exists_value, dict):
        return
    new_key = exists_value.get("key")
    record = db.get(Asset, uid)
    if record is None or not new_key or record.key == new_key:
        return
    clash = db.scalar(select(Asset).where(Asset.key == new_key, Asset.uid != uid).limit(1))
    if clash is not None:
        raise LedgerError(f"the source re-keyed {record.key} to {new_key}, which {clash.uid} already holds")
    add_label(db, uid, "former_key", record.key, stream.kind)
    db.add(RecordEvent(uid=uid, kind="rekeyed", before={"key": record.key}, after={"key": new_key}, cause=cause,
                       at=now()))
    record.key = new_key
    db.flush()


def add_label(db: Session, uid: str, label_type: str, value: str, namespace: str) -> None:
    exists = db.scalar(select(AssetLabel).where(AssetLabel.asset_uid == uid, AssetLabel.type == label_type,
                                                AssetLabel.value == value).limit(1))
    if exists is None:
        db.add(AssetLabel(uid=str(uuid.uuid4()), asset_uid=uid, type=label_type, value=value, namespace=namespace,
                          issuer="ledger", verified=True, created_at=now(), updated_at=now()))


# --------------------------------------------------------------------------- candidates (A35)

def _pair_id(pair: tuple, identifier: tuple) -> str:
    return hashlib.sha256(canonical([CANDIDATE, sorted(pair), list(identifier)]).encode()).hexdigest()[:24]


def _dismissed(db: Session, workspace_ids: Iterable[str]) -> set[frozenset]:
    out = set()
    for d in db.scalars(select(Decision).where(Decision.kind.in_(("reject_candidate", "confirm_new")),
                                               Decision.workspace_id.in_(list(workspace_ids)))):
        out.add(frozenset((d.target or {}).get("records") or []))
    return out


def detect_candidates(db: Session, uids: Iterable[str], cause: str) -> None:
    """Open (or close) identity candidates for these records. Never merges."""
    uids = [u for u in set(uids) if u]
    for uid in uids:
        record = db.get(Asset, uid)
        if record is None:
            continue
        wanted: dict[str, tuple] = {}
        if record.record_status not in INACTIVE:
            for ident in strong_identifiers(record.attributes):
                for other in _holders(db, *ident, exclude=uid):
                    pair = tuple(sorted((uid, other.uid)))
                    if frozenset(pair) in _dismissed(db, {record.workspace_id, other.workspace_id}):
                        continue
                    wanted[_pair_id(pair, ident)] = (pair, ident)
        existing = {c.conflict_id: c for c in db.scalars(select(Conflict).where(
            Conflict.conflict_type == CANDIDATE, Conflict.detail["records"].contains([uid])))}
        for cid, (pair, (name, value)) in wanted.items():
            if cid in existing or db.get(Conflict, cid) is not None:
                continue
            owner = db.get(Asset, pair[0])
            detail = {"records": list(pair), "identifier": name, "value": value.split("|")[-1],
                      "score": 0.9 if name != "mac" else 0.95,
                      "evidence": f"both records hold {name} {value.split('|')[-1]}"}
            ev = ConflictEvent(conflict_id=cid, kind="opened", conflict_type=CANDIDATE, subject_uid=owner.uid,
                               predicate=f"attr:{name}", detail=detail, cause=cause, at=now())
            db.add(ev)
            db.flush()
            db.add(Conflict(conflict_id=cid, conflict_type=CANDIDATE, severity="non-blocking",
                            workspace_id=owner.workspace_id, subject_uid=owner.uid, predicate=f"attr:{name}",
                            detail=detail, opened_seq=ev.seq))
            db.flush()
        for cid, row in existing.items():
            if cid not in wanted:
                others = [u for u in row.detail["records"] if u != uid]
                still = others and all((db.get(Asset, u) is not None
                                        and db.get(Asset, u).record_status not in INACTIVE) for u in others) \
                    and record.record_status not in INACTIVE \
                    and frozenset(row.detail["records"]) not in _dismissed(db, {record.workspace_id}) \
                    and any(i[0] == row.detail["identifier"] for i in strong_identifiers(record.attributes))
                if not still:
                    db.add(ConflictEvent(conflict_id=cid, kind="resolved", conflict_type=CANDIDATE,
                                         subject_uid=row.subject_uid, detail=row.detail, cause=cause, at=now()))
                    db.delete(row)
    db.flush()


def dismiss_candidate(db: Session, workspace_id: str, actor: str, records: list[str], kind: str,
                      reason: Optional[str] = None) -> Decision:
    """`reject_candidate` (not the same thing) or `confirm_new` (both are real)."""
    if kind not in ("reject_candidate", "confirm_new") or len(set(records)) != 2:
        raise LedgerError("name the two records of the candidate")
    d = engine._record_decision(db, kind, actor, workspace_id, target={"records": sorted(records)}, reason=reason)
    detect_candidates(db, records, f"decision:{d.decision_id}")
    return d


def merge(db: Session, workspace_id: str, actor: str, survivor_uid: str, loser_uid: str,
          reason: Optional[str] = None) -> Decision:
    """A steward's merge (§10): the survivor keeps its uid; everything that
    pointed at the loser points at the survivor; the loser's source refs are
    rebound, so its claims now compete on the survivor under the policy; the
    loser stays as a `Merged` tombstone."""
    survivor, loser = db.get(Asset, survivor_uid), db.get(Asset, loser_uid)
    if survivor is None or loser is None or survivor_uid == loser_uid:
        raise LedgerError("name two different records")
    if workspace_id not in (survivor.workspace_id, loser.workspace_id):
        raise LedgerError("a merge is decided in the workspace of one of its records")
    if loser.record_status == "Merged" or survivor.record_status == "Merged":
        raise LedgerError("a merged record cannot be merged again")
    decision = engine._record_decision(db, "merge", actor, workspace_id, subject_uid=survivor_uid,
                                       target={"survivor": survivor_uid, "loser": loser_uid}, reason=reason)
    cause = f"merge:{decision.decision_id}"
    # Derived and ledger edges are recomputed; asserted ones move.
    db.execute(delete(Relation).where(Relation.from_asset_uid == loser_uid, Relation.derivation.isnot(None)))
    db.execute(delete(Relation).where(Relation.to_asset_uid == loser_uid, Relation.derivation == "derived"))
    for r in db.scalars(select(Relation).where(or_(Relation.from_asset_uid == loser_uid,
                                                   Relation.to_asset_uid == loser_uid))):
        if r.from_asset_uid == loser_uid:
            r.from_asset_uid = survivor_uid
        if r.to_asset_uid == loser_uid:
            r.to_asset_uid = survivor_uid
    for model, col in ((Issue, Issue.asset_uid), (AssetTicket, AssetTicket.asset_uid),
                       (AssetLabel, AssetLabel.asset_uid), (AssetComment, AssetComment.asset_uid),
                       (Attachment, Attachment.asset_uid)):
        for row in db.scalars(select(model).where(col == loser_uid)):
            setattr(row, col.key, survivor_uid)
    for rel in db.scalars(select(DocumentRelation).where(DocumentRelation.to_type == "asset",
                                                         DocumentRelation.to_uid == loser_uid)):
        rel.to_uid = survivor_uid
    db.execute(delete(TicketLink).where(TicketLink.asset_uid == loser_uid))
    for b in list(db.scalars(select(IdentityBinding).where(IdentityBinding.uid == loser_uid))):
        if not b.source_ref.startswith("uid:"):
            engine.bind(db, b.source_ref, survivor_uid, f"rebound: {cause}")
    add_label(db, survivor_uid, "former_key", loser.key, "merge")
    add_label(db, survivor_uid, "former_uid", loser.uid, "merge")
    db.add(RecordEvent(uid=loser_uid, kind="status", before=loser.record_status, after="Merged", cause=cause,
                       at=now()))
    loser.record_status, loser.merged_into_uid = "Merged", survivor_uid
    db.flush()
    engine.project_subject(db, survivor_uid, cause)
    try:
        engine.validate_installations(db, [survivor_uid], strict=True)
    except InvariantError as exc:
        raise InvariantError(exc.code, f"the merged units were installed at overlapping times: {exc}")
    detect_candidates(db, [survivor_uid, loser_uid], cause)
    engine.derive_all(db, {survivor.workspace_id, loser.workspace_id})
    from app.ledger.tickets import derive_ticket_links
    derive_ticket_links(db, ticket_uids=[i.uid for i in db.scalars(select(Issue).where(
        Issue.asset_uid == survivor_uid))])
    return decision


# --------------------------------------------------------------------------- creation (I-ID-1)

def assert_unique_at_creation(db: Session, workspace_id: str, attributes: dict, exclude: Optional[str] = None) -> None:
    """After cutover, a new record may not take a strong identifier an active
    record holds. The error names the existing record."""
    from app.ledger.cutover import authoritative
    if not authoritative(db, workspace_id, "objects"):
        return
    for name, value in strong_identifiers(attributes):
        holders = _holders(db, name, value, exclude=exclude)
        if holders:
            h = holders[0]
            raise DuplicateIdentifier(name, value.split("|")[-1], h)


class DuplicateIdentifier(InvariantError):
    def __init__(self, name: str, value: str, existing: Asset):
        super().__init__("I-ID-1", f"{name} {value} is already held by {existing.key} ({existing.name})")
        self.existing = {"uid": existing.uid, "key": existing.key, "name": existing.name,
                         "workspace_id": existing.workspace_id, "path": f"/assets/{existing.uid}"}
