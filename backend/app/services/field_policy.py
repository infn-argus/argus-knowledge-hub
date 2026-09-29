"""What the field client may not do (revision §24.8, flutter-app-design §9).

These are decided at a desk, on the web, with the full record in front of the person, and never by
the field client or a model:
- confirming a root cause, or the corrective action it implies;
- closing a safety-related ticket. From the field client it arrives as a proposed transition,
  which a person confirms online (A70);
- retiring or deleting Equipment.

The field client is recognized by its `X-ARGUS-Client: flutter/...` header. This is a policy on
the channel, not an access control: the same person can do these things on the web, where the
workflow and their role decide.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

DESK_ONLY_TICKET_FIELDS = ("argus_root_cause", "argus_corrective_action")
PROPOSED = "argus_proposed_transition"


def is_field_client(client_header: Optional[str]) -> bool:
    return bool(client_header) and client_header.strip().lower().startswith("flutter/")


def check_ticket_fields(client_header: Optional[str], before: dict, after: dict) -> None:
    if not is_field_client(client_header):
        return
    changed = [f for f in DESK_ONLY_TICKET_FIELDS if (before or {}).get(f) != (after or {}).get(f)]
    if changed:
        raise HTTPException(status_code=403, detail={
            "error": "The root cause and the corrective action are confirmed on the web, not from the field. "
                     "Add what you found as a comment.",
            "code": "forbidden", "field": f"attributes.{changed[0]}"})


def is_safety_ticket(db, issue) -> bool:
    from app.models.schema import Schema
    attrs = issue.attributes or {}
    if str(attrs.get("argus_impact") or "").lower() == "safety":
        return True
    schema = db.get(Schema, issue.schema_uid) if issue.schema_uid else None
    return schema is not None and "safety" in schema.name.lower()


def closes(wf: dict, target: str) -> bool:
    from app.services import workflows
    return (workflows.state_of(wf, target) or {}).get("category") == "done"


def propose_transition(db, issue, actor: Optional[str], target: str, comment: Optional[str],
                       resolution: Optional[str]) -> dict:
    """Record a closure from the field as a proposal on the ticket; the state does not change."""
    import uuid
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.issue import IssueHistory
    proposal = {"to": target, "by": actor or "api", "at": datetime.now(timezone.utc).isoformat(),
                "comment": comment, "resolution": resolution}
    attrs = dict(issue.attributes or {})
    attrs[PROPOSED] = proposal
    issue.attributes = attrs
    flag_modified(issue, "attributes")
    db.add(IssueHistory(uid=str(uuid.uuid4()), issue_uid=issue.uid, type="updated", author=actor or "api",
                        field="Proposed transition", from_value=issue.state, to_value=target,
                        details="Proposed from the field client; a person confirms it on the web.",
                        timestamp=datetime.now(timezone.utc)))
    return proposal


def clear_proposal(issue) -> None:
    from sqlalchemy.orm.attributes import flag_modified
    if PROPOSED in (issue.attributes or {}):
        attrs = dict(issue.attributes)
        attrs.pop(PROPOSED, None)
        issue.attributes = attrs
        flag_modified(issue, "attributes")


def refuse_retirement(client_header: Optional[str]) -> None:
    if is_field_client(client_header):
        raise HTTPException(status_code=403, detail={
            "error": "Equipment is retired or deleted on the web, not from the field.", "code": "forbidden"})
