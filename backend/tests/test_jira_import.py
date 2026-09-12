"""_author_display_name exists because production data proved the
assumption "author is always {'displayName': ...}" wrong: Jira Insight
returns a plain username string for some object types (attachments, in the
observed case) and a nested object for others (comments/history), and the
old `(x.get("author") or {}).get("displayName")` code crashed with
`AttributeError: 'str' object has no attribute 'get'` on the string form —
silently zeroing out every attachment for the whole import.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.jira_import import (
    _author_display_name,
    _resolve_reference_schema_uid,
    resolve_reference_attributes,
)


def test_dict_with_display_name():
    assert _author_display_name({"displayName": "Mario Rossi"}) == "Mario Rossi"


def test_dict_falls_back_to_name_then_key():
    assert _author_display_name({"name": "mrossi"}) == "mrossi"
    assert _author_display_name({"key": "mrossi"}) == "mrossi"
    assert _author_display_name({"displayName": None, "name": "mrossi"}) == "mrossi"


def test_plain_string_author():
    assert _author_display_name("mrossi") == "mrossi"


def test_missing_or_empty_author():
    assert _author_display_name(None) is None
    assert _author_display_name("") is None
    assert _author_display_name({}) is None


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def test_resolve_reference_attributes_finds_type_from_an_earlier_import_and_persists():
    """Reproduces the real report: a "Divisione Acceleratori" type imported
    into its own (global) workspace, later referenced by an attribute
    imported separately into "EUAPS" — the two imports never share an
    in-memory jira_id_to_uid, so resolution has to fall back to a DB-wide
    lookup by the Jira object type id stored in metadata_json.

    Also guards the persistence pitfall that shipped in the first version
    of this fix: mutating the attribute dicts in place before checking
    `db.commit()` looked like it worked (no error, no exception) but the
    JSONB column was never actually marked dirty, so nothing was written —
    verified here via a *separate* session re-reading the row.
    """
    suffix = secrets.token_hex(4)
    ws_a, ws_b = f"divacc-{suffix}", f"euaps-{suffix}"
    magnet_uid, detector_uid = f"magnet-{suffix}", f"detector-{suffix}"

    db = SessionLocal()
    db.add(Workspace(id=ws_a, name="Divisione Acceleratori", is_global=True))
    db.add(Workspace(id=ws_b, name="EUAPS"))
    db.flush()

    # "Magnet" was imported earlier, into a different workspace, in a run
    # whose jira_id_to_uid is long gone — only metadata_json survives.
    db.add(Schema(
        uid=magnet_uid, workspace_id=ws_a, name="Magnet",
        is_global=True, metadata_json={"source": "jira", "jiraObjectTypeId": 10},
    ))

    # "Detector" is from *this* run and references Jira object type 10 —
    # not yet resolved to our Schema.uid, exactly as _map_attribute leaves it.
    db.add(Schema(
        uid=detector_uid, workspace_id=ws_b, name="Detector",
        metadata_json={"source": "jira", "jiraObjectTypeId": 20},
        attributes=[{
            "id": "200", "key": "magnet", "name": "Magnet", "type": "reference",
            "referenceType": "Magnet", "_jiraReferenceObjectTypeId": 10,
        }],
    ))
    db.commit()

    # Confirms the fallback path is actually exercised: Magnet's uid is not
    # in this run's map.
    jira_id_to_uid = {20: detector_uid}
    assert _resolve_reference_schema_uid(db, 10, jira_id_to_uid) == magnet_uid

    resolve_reference_attributes(db, jira_id_to_uid)
    db.commit()
    db.close()

    reloaded = SessionLocal().get(Schema, detector_uid)
    assert reloaded.attributes[0]["referenceSchemaUid"] == magnet_uid
