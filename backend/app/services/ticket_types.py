"""The application's own ticket types.

These are ARGUS types, not Jira ones. Jira is a source that maps onto
them, the same way a second tracker or an alarm system would — so the
field keys are argus_*, and what Jira happened to call a field is kept as
provenance rather than being the model.

One base type carries the fields every ticket has, with a child per kind
of work (Epic, Story, Task, Bug, Sub-task) inheriting them, so a project
can add a field to Bugs alone.

What a ticket is *about* is deliberately not an attribute. Objects and
documents are linked through their own tables — asset_tickets and
document_relations — because those are edges the knowledge graph has to
traverse from either end: "what broke this magnet" matters as much as
"what does this ticket affect", and an attribute holding a uid answers
only the second.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import Schema

BASE_UID_SUFFIX = "argus-ticket"
BASE_TYPE_NAME = "Ticket"

# The kinds of work a ticket can be. Close to what trackers use, so an
# import needs no mapping for the common case.
DEFAULT_ISSUE_TYPES = ("Epic", "Story", "Task", "Bug", "Sub-task")

# Operational classification — what makes a ticket useful to ARGUS. A fault
# that stopped the beam and one that didn't are different facts.
CATEGORY_OPTIONS = [
    {"id": "fault", "value": "Fault"},
    {"id": "maintenance", "value": "Maintenance"},
    {"id": "upgrade", "value": "Upgrade"},
    {"id": "request", "value": "Request"},
    {"id": "investigation", "value": "Investigation"},
    {"id": "other", "value": "Other"},
]

IMPACT_OPTIONS = [
    {"id": "beam_down", "value": "Beam down"},
    {"id": "beam_degraded", "value": "Beam degraded"},
    {"id": "no_beam_impact", "value": "No beam impact"},
    {"id": "safety", "value": "Safety"},
    {"id": "unknown", "value": "Unknown"},
]

DETECTED_BY_OPTIONS = [
    {"id": "operator", "value": "Operator"},
    {"id": "alarm", "value": "Alarm"},
    {"id": "monitoring", "value": "Monitoring"},
    {"id": "inspection", "value": "Inspection"},
    {"id": "user_report", "value": "User report"},
]

SOURCE_OPTIONS = [
    {"id": "manual", "value": "Created here"},
    {"id": "jira", "value": "Jira"},
]

# (key, name, type, extra), ordered as they should read on a ticket.
BASE_ATTRIBUTES = [
    # The fields ARGUS reasons over; the rest is description.
    ("argus_category", "Category", "enumeration", {"options": CATEGORY_OPTIONS}),
    ("argus_impact", "Operational impact", "enumeration", {"options": IMPACT_OPTIONS}),
    ("argus_detected_by", "Detected by", "enumeration", {"options": DETECTED_BY_OPTIONS}),
    ("argus_system", "System", "string", {}),
    ("argus_subsystem", "Subsystem", "string", {}),

    # Cause and cure, in the operators' own words. Free text on purpose:
    # forcing a taxonomy here yields "other" for everything interesting,
    # and retrieval reads prose perfectly well.
    ("argus_root_cause", "Root cause", "text", {}),
    ("argus_corrective_action", "Corrective action", "text", {}),
    ("argus_resolution", "Resolution", "string", {}),

    # Downtime — the number anyone asks for first.
    ("argus_downtime_start", "Downtime start", "datetime", {}),
    ("argus_downtime_end", "Downtime end", "datetime", {}),
    ("argus_downtime_minutes", "Downtime (minutes)", "integer", {}),

    # Planning.
    ("argus_epic", "Epic", "string", {}),
    ("argus_epic_name", "Epic name", "string", {}),
    ("argus_sprint", "Sprint", "string", {"multiValue": True}),
    ("argus_story_points", "Story points", "float", {}),
    ("argus_components", "Components", "string", {"multiValue": True}),
    ("argus_fix_versions", "Fix version/s", "string", {"multiValue": True}),
    ("argus_affects_versions", "Affects version/s", "string", {"multiValue": True}),
    ("argus_environment", "Environment", "text", {}),
    ("argus_parent", "Parent ticket", "string", {}),
    ("argus_time_spent", "Time spent (s)", "integer", {}),
    ("argus_time_estimate", "Original estimate (s)", "integer", {}),
    ("argus_reporter", "Reporter", "string", {}),
    ("argus_votes", "Votes", "integer", {}),
    ("argus_watchers", "Watchers", "integer", {}),

    # Where it came from. Read-only: a re-import overwrites these, so an
    # edit here would only be undone.
    ("argus_source", "Source", "enumeration", {"options": SOURCE_OPTIONS, "readOnly": True}),
    ("argus_project", "Project at source", "string", {"readOnly": True}),
    ("argus_source_key", "Source key", "string", {"readOnly": True}),
    ("argus_source_url", "Source link", "string", {"readOnly": True}),
    ("argus_source_status", "Status at source", "string", {"readOnly": True}),
    ("argus_source_type", "Type at source", "string", {"readOnly": True}),
    ("argus_source_created", "Created at source", "datetime", {"readOnly": True}),
    ("argus_source_updated", "Updated at source", "datetime", {"readOnly": True}),
]

# Keys written while the model was still Jira's. Mapped rather than
# dropped: the tickets already imported hold real values under them.
LEGACY_KEY_MAP = {
    # The first importer's spelling.
    "jiraKey": "argus_source_key",
    "jiraUrl": "argus_source_url",
    "jiraProject": "argus_project",
    "jiraStatus": "argus_source_status",
    "jiraIssueType": "argus_source_type",
    "jiraComponents": "argus_components",
    # The Jira-shaped ticket type that replaced it.
    "jira_key": "argus_source_key",
    "jira_url": "argus_source_url",
    "jira_project": "argus_project",
    "jira_status": "argus_source_status",
    "jira_issue_type": "argus_source_type",
    "jira_resolution": "argus_resolution",
    "jira_components": "argus_components",
    "jira_fix_versions": "argus_fix_versions",
    "jira_affects_versions": "argus_affects_versions",
    "jira_reporter": "argus_reporter",
    "jira_votes": "argus_votes",
    "jira_watchers": "argus_watchers",
    "jira_created": "argus_source_created",
    "jira_updated": "argus_source_updated",
    "jira_environment": "argus_environment",
    "jira_parent": "argus_parent",
    "jira_time_spent": "argus_time_spent",
    "jira_time_estimate": "argus_time_estimate",
    "jira_epic": "argus_epic",
    "jira_epic_name": "argus_epic_name",
    "jira_sprint": "argus_sprint",
    "jira_story_points": "argus_story_points",
}


def _attribute(key: str, name: str, type_: str, extra: dict) -> dict:
    out = {
        "id": key,
        "key": key,
        "name": name,
        "type": type_,
        "required": False,
        "multiValue": extra.get("multiValue", False),
        "unique": extra.get("unique", False),
        "readOnly": extra.get("readOnly", False),
    }
    if extra.get("options"):
        out["options"] = extra["options"]
    return out


def base_attributes() -> list[dict]:
    return [_attribute(*a) for a in BASE_ATTRIBUTES]


def ensure_ticket_types(db: Session, workspace_id: str, issue_type_names: set[str]) -> dict:
    """Create (or refresh) the base ticket type and a child per kind of
    work. Returns name -> schema uid.

    Idempotent and safe on every import: the base type's field set is kept
    current so a release that adds a field reaches existing workspaces,
    while children are left alone once created, since a workspace may have
    added fields of its own to them.
    """
    base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"
    base = db.get(Schema, base_uid)
    if base is None:
        base = Schema(
            uid=base_uid,
            workspace_id=workspace_id,
            name=BASE_TYPE_NAME,
            description="Fields every ticket carries, whatever created it.",
            applies_to="tickets",
            is_concrete=False,
            attributes=base_attributes(),
            metadata_json={"source": "argus"},
        )
        db.add(base)
    else:
        base.attributes = base_attributes()
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
                attributes=[],
                metadata_json={"source": "argus"},
            )
            db.add(child)
        out[name] = child_uid
    db.flush()
    return out


def migrate_legacy_attributes(attributes: dict) -> dict:
    """Rewrite a ticket's attributes from the Jira-shaped keys onto the
    ARGUS ones, leaving anything else untouched. A value already under the
    ARGUS key wins, so this is safe to run twice."""
    out = dict(attributes or {})
    for legacy, current in LEGACY_KEY_MAP.items():
        if legacy not in out:
            continue
        value = out.pop(legacy)
        out.setdefault(current, value)
    return out


def existing_ticket_type_uids(db: Session, workspace_id: str) -> list[str]:
    base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"
    return list(
        db.scalars(
            select(Schema.uid).where(
                Schema.workspace_id == workspace_id,
                Schema.parent_schema_uid == base_uid,
            )
        )
    ) + [base_uid]
