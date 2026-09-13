"""The ticket types a Jira import needs.

Rather than inventing a parallel rendering path for imported issues, the
standard Jira field set is expressed as a *ticket type* — a Schema with
applies_to="tickets" — so the attribute machinery that already exists
(rendering, validation, configurable columns, search) applies to them
unchanged.

The shape mirrors Jira's own: one base type carrying the fields every
issue has, and a child type per issue type (Task, Bug, Story…) that
inherits them. A project that adds its own fields to Bugs can then do
that on the child without disturbing anything else.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import Schema

BASE_UID_SUFFIX = "jira-issue"

# (key, name, type, extra)
BASE_ATTRIBUTES = [
    ("jira_key", "Key", "string", {"unique": True}),
    ("jira_url", "Jira link", "string", {}),
    ("jira_project", "Project", "string", {}),
    ("jira_status", "Jira status", "string", {}),
    ("jira_issue_type", "Type", "string", {}),
    ("jira_resolution", "Resolution", "string", {}),
    ("jira_components", "Component/s", "string", {"multiValue": True}),
    ("jira_fix_versions", "Fix Version/s", "string", {"multiValue": True}),
    ("jira_affects_versions", "Affects Version/s", "string", {"multiValue": True}),
    ("jira_reporter", "Reporter", "string", {}),
    ("jira_votes", "Votes", "integer", {}),
    ("jira_watchers", "Watchers", "integer", {}),
    ("jira_created", "Created in Jira", "datetime", {}),
    ("jira_updated", "Updated in Jira", "datetime", {}),
    ("jira_environment", "Environment", "text", {}),
    ("jira_parent", "Parent", "string", {}),
    ("jira_time_spent", "Time spent (s)", "integer", {}),
    ("jira_time_estimate", "Original estimate (s)", "integer", {}),
    # Agile fields. Jira keeps these in per-instance custom fields rather
    # than a fixed schema, so the importer discovers their ids by name.
    ("jira_epic", "Epic", "string", {}),
    ("jira_epic_name", "Epic name", "string", {}),
    ("jira_sprint", "Sprint", "string", {"multiValue": True}),
    ("jira_story_points", "Story points", "float", {}),
]

# The types Jira ships with, so a workspace can raise an Epic or a Story by
# hand before anything has been imported.
DEFAULT_ISSUE_TYPES = ("Epic", "Story", "Task", "Bug", "Sub-task")


def _attribute(key: str, name: str, type_: str, extra: dict) -> dict:
    return {
        "id": key,
        "key": key,
        "name": name,
        "type": type_,
        "required": False,
        "multiValue": extra.get("multiValue", False),
        "unique": extra.get("unique", False),
        # Imported values are a record of what the source system said; editing
        # them here would only be overwritten by the next import.
        "readOnly": True,
        **{k: v for k, v in extra.items() if k not in ("multiValue", "unique")},
    }


def ensure_jira_ticket_types(db: Session, workspace_id: str, issue_type_names: set[str]) -> dict:
    """Create (or update) the base Jira ticket type and a child per issue
    type. Returns issue type name -> schema uid.

    Idempotent, and safe to call on every import: existing types are left in
    place, so a type someone renamed or extended survives.
    """
    base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"
    base = db.get(Schema, base_uid)
    attributes = [_attribute(*a) for a in BASE_ATTRIBUTES]
    if base is None:
        base = Schema(
            uid=base_uid,
            workspace_id=workspace_id,
            name="Jira Issue",
            description="Fields every imported Jira issue carries.",
            applies_to="tickets",
            is_concrete=False,
            attributes=attributes,
            metadata_json={"source": "jira-issues"},
        )
        db.add(base)
    else:
        # Keep the field set current when this list grows in a later release.
        base.attributes = attributes
    db.flush()

    out: dict[str, str] = {}
    for name in sorted(n for n in issue_type_names if n):
        child_uid = f"{base_uid}:{name.lower().replace(' ', '-')}"
        child = db.get(Schema, child_uid)
        if child is None:
            child = Schema(
                uid=child_uid,
                workspace_id=workspace_id,
                name=name,
                applies_to="tickets",
                parent_schema_uid=base.uid,
                # Fields come from the parent; a project that wants more on
                # one issue type adds them here.
                attributes=[],
                metadata_json={"source": "jira-issues", "jiraIssueType": name},
            )
            db.add(child)
        out[name] = child_uid
    db.flush()
    return out


def existing_jira_type_uids(db: Session, workspace_id: str) -> list[str]:
    base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"
    return list(
        db.scalars(
            select(Schema.uid).where(
                Schema.workspace_id == workspace_id,
                Schema.parent_schema_uid == base_uid,
            )
        )
    ) + [base_uid]
