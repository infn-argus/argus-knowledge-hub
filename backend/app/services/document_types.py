"""The kinds of documentation an accelerator actually keeps.

Seeded so a workspace has somewhere to put a document on day one, and so
an import has a type to map onto rather than dropping everything into an
untyped pile.

The set is drawn from how accelerator and large-experiment documentation
is actually organised: a controlled procedure is a different object from
a shift logbook entry, and ARGUS has to tell them apart — an operator
asking "how do I recover the vacuum" wants the procedure, while "what
happened last Tuesday" wants the logbook. Same words, different
documents.

Fields are argus_* for the same reason tickets' are: this is the
application's model, and Confluence or Git is a source that maps onto it.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import Schema

BASE_UID_SUFFIX = "argus-document"
BASE_TYPE_NAME = "Document"

# (name, description). Ordered roughly by how binding the document is.
DEFAULT_DOCUMENT_TYPES = [
    ("Procedure",
     "A controlled, step-by-step operation someone is expected to follow exactly."),
    ("Work Instruction",
     "How a specific task is done on specific equipment; narrower than a procedure."),
    ("Safety Document",
     "Radiation, interlock, access and personnel safety — including risk assessments."),
    ("Specification",
     "What a system must do or be: requirements, interfaces, acceptance criteria."),
    ("Design Report",
     "Why a system is built the way it is, including calculations and trade-offs."),
    ("Drawing",
     "Mechanical, electrical, vacuum or layout drawings, and their reference numbers."),
    ("Manual",
     "Vendor or in-house documentation for a device, usually not written here."),
    ("Commissioning Record",
     "What was done and measured when a system was first brought into operation."),
    ("Test Report",
     "The result of a measurement or acceptance test, tied to equipment and a date."),
    ("Maintenance Report",
     "What was done during an intervention, and what state the equipment was left in."),
    ("Logbook Entry",
     "What happened during a shift or a run — the operational narrative."),
    ("Runbook",
     "What to do when something goes wrong, including symptoms and first actions."),
    ("Meeting Minutes",
     "Decisions taken and who took them."),
    ("Note",
     "Anything that doesn't belong to the kinds above."),
]

LIFECYCLE_OPTIONS = [
    {"id": "current", "value": "Current"},
    {"id": "under_revision", "value": "Under revision"},
    {"id": "superseded", "value": "Superseded"},
    {"id": "withdrawn", "value": "Withdrawn"},
]

SOURCE_OPTIONS = [
    {"id": "manual", "value": "Written here"},
    {"id": "confluence", "value": "Confluence"},
    {"id": "git", "value": "Git"},
    {"id": "jira", "value": "Jira"},
]

# (key, name, type, extra)
BASE_ATTRIBUTES = [
    # What the document is about operationally. These are what make a
    # document findable by someone with a problem rather than a filename.
    # The same keys tickets carry, so a system names one thing across the
    # whole hub rather than one thing per section.
    ("argus_system", "System", "string", {"indexed": True}),
    ("argus_subsystem", "Subsystem", "string", {"indexed": True}),
    # Indexed rather than a fixed list: the facilities are a closed set in
    # principle, but inventing that list here would be guessing, and the
    # vocabulary fills itself from what the records actually say.
    ("argus_facility", "Facility", "string", {"indexed": True}),
    # The field the Confluence import fills. Free text here is what turns
    # one keyword into "BTF", "btf" and "BTF " — three terms, no filter.
    ("argus_keywords", "Keywords", "string", {"multiValue": True, "indexed": True}),

    # Document control. An accelerator's documentation is only worth
    # anything if you can tell which version is in force.
    ("argus_lifecycle", "Lifecycle", "enumeration", {"options": LIFECYCLE_OPTIONS}),
    ("argus_document_number", "Document number", "string", {"indexed": True}),
    ("argus_revision_label", "Revision label", "string", {}),
    # A person, so it picks from the directory. Controlled documentation
    # that can't say who approved it isn't controlled.
    ("argus_approved_by", "Approved by", "user", {}),
    ("argus_review_interval_months", "Review interval (months)", "integer", {}),

    # Where it came from, kept rather than being the model.
    ("argus_source", "Source", "enumeration", {"options": SOURCE_OPTIONS, "readOnly": True}),
    ("argus_source_id", "Source id", "string", {"readOnly": True}),
    ("argus_source_url", "Source link", "string", {"readOnly": True}),
    ("argus_source_space", "Source space", "string", {"readOnly": True}),
    ("argus_source_version", "Version at source", "integer", {"readOnly": True}),
    ("argus_source_updated", "Updated at source", "datetime", {"readOnly": True}),
    ("argus_source_author", "Author at source", "string", {"readOnly": True}),
]


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
        # An indexed attribute is a key rather than prose: the values it
        # already holds are offered as you type, so the same term is reused
        # instead of being spelled three ways.
        "indexed": extra.get("indexed", False),
    }
    if extra.get("options"):
        out["options"] = extra["options"]
    return out


def base_attributes() -> list[dict]:
    return [_attribute(*a) for a in BASE_ATTRIBUTES]


def type_uid(workspace_id: str, name: str) -> str:
    return f"{workspace_id}:{BASE_UID_SUFFIX}:{name.lower().replace(' ', '-')}"


def ensure_document_types(
    db: Session, workspace_id: str, extra_names: set[str] | None = None
) -> dict:
    """Create (or refresh) the base document type and one child per kind.
    Returns name -> schema uid.

    Idempotent: the base type's field set is kept current so a release that
    adds a field reaches existing workspaces, while children are left alone
    once created, since a workspace may have added fields of its own.
    """
    base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"
    base = db.get(Schema, base_uid)
    if base is None:
        base = Schema(
            uid=base_uid,
            workspace_id=workspace_id,
            name=BASE_TYPE_NAME,
            description="Fields every document carries, whatever wrote it.",
            applies_to="documents",
            is_concrete=False,
            attributes=base_attributes(),
            metadata_json={"source": "argus"},
        )
        db.add(base)
    else:
        base.attributes = base_attributes()
    db.flush()

    wanted = {name: description for name, description in DEFAULT_DOCUMENT_TYPES}
    for name in sorted(extra_names or set()):
        wanted.setdefault(name, None)

    out: dict[str, str] = {}
    for name, description in wanted.items():
        child_uid = type_uid(workspace_id, name)
        child = db.get(Schema, child_uid)
        if child is None:
            child = Schema(
                uid=child_uid,
                workspace_id=workspace_id,
                name=name,
                description=description,
                applies_to="documents",
                parent_schema_uid=base.uid,
                attributes=[],
                metadata_json={"source": "argus"},
            )
            db.add(child)
        out[name] = child_uid
    db.flush()
    return out


def existing_document_type_uids(db: Session, workspace_id: str) -> list[str]:
    base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"
    return list(
        db.scalars(
            select(Schema.uid).where(
                Schema.workspace_id == workspace_id,
                Schema.parent_schema_uid == base_uid,
            )
        )
    ) + [base_uid]
