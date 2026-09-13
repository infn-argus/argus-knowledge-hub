"""move tickets onto the ARGUS model

Revision ID: e8c1a4f7b923
Revises: d5f3b8c21a47
Create Date: 2026-09-13

The ticket types were Jira's: a type named "Jira Issue" with jira_* field
keys. They are the application's own types now, and Jira is one source
that maps onto them. This moves the existing types and the tickets
already imported under the old keys, so nothing has to be imported again
to become readable.

Data only — no columns change. Types and their fields live in rows, so a
release that changes them is a data migration.

The type's uid changes too (…:jira-issue -> …:argus-ticket), which can't
be done by updating a primary key that other rows point at. New rows are
inserted, the tickets are repointed, and only then are the old rows
removed — in that order, because issues.schema_uid cascades on delete and
doing it the other way round would take the tickets with it.
"""
import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8c1a4f7b923"
down_revision: Union[str, None] = "d5f3b8c21a47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_SUFFIX = ":jira-issue"


def upgrade() -> None:
    from app.services.ticket_types import (
        BASE_TYPE_NAME,
        BASE_UID_SUFFIX,
        base_attributes,
        migrate_legacy_attributes,
    )

    bind = op.get_bind()

    old_bases = bind.execute(sa.text(
        "SELECT uid, workspace_id FROM schemas WHERE uid LIKE :pattern"
    ), {"pattern": f"%{OLD_SUFFIX}"}).mappings().all()

    for base in old_bases:
        workspace_id = base["workspace_id"]
        old_base_uid = base["uid"]
        new_base_uid = f"{workspace_id}:{BASE_UID_SUFFIX}"

        bind.execute(
            sa.text(
                "INSERT INTO schemas (uid, workspace_id, name, description, is_concrete, "
                "parent_schema_uid, attributes, metadata, version, is_global, applies_to, "
                "created_at, updated_at) "
                "VALUES (:uid, :ws, :name, :description, false, NULL, "
                "CAST(:attributes AS jsonb), CAST(:metadata AS jsonb), 1, false, 'tickets', "
                "now(), now()) ON CONFLICT (uid) DO UPDATE SET "
                "name = EXCLUDED.name, attributes = EXCLUDED.attributes"
            ),
            {
                "uid": new_base_uid,
                "ws": workspace_id,
                "name": BASE_TYPE_NAME,
                "description": "Fields every ticket carries, whatever created it.",
                "attributes": json.dumps(base_attributes()),
                "metadata": json.dumps({"source": "argus"}),
            },
        )

        children = bind.execute(sa.text(
            "SELECT uid, name FROM schemas WHERE parent_schema_uid = :parent"
        ), {"parent": old_base_uid}).mappings().all()

        for child in children:
            slug = child["name"].lower().replace(" ", "-")
            new_child_uid = f"{new_base_uid}:{slug}"
            bind.execute(
                sa.text(
                    "INSERT INTO schemas (uid, workspace_id, name, description, is_concrete, "
                    "parent_schema_uid, attributes, metadata, version, is_global, applies_to, "
                    "created_at, updated_at) "
                    "VALUES (:uid, :ws, :name, NULL, true, :parent, '[]'::jsonb, "
                    "CAST(:metadata AS jsonb), 1, false, 'tickets', now(), now()) "
                    "ON CONFLICT (uid) DO NOTHING"
                ),
                {
                    "uid": new_child_uid,
                    "ws": workspace_id,
                    "name": child["name"],
                    "parent": new_base_uid,
                    "metadata": json.dumps({"source": "argus"}),
                },
            )
            # Tickets move before anything is deleted.
            bind.execute(
                sa.text("UPDATE issues SET schema_uid = :new WHERE schema_uid = :old"),
                {"new": new_child_uid, "old": child["uid"]},
            )

        bind.execute(
            sa.text("UPDATE issues SET schema_uid = :new WHERE schema_uid = :old"),
            {"new": new_base_uid, "old": old_base_uid},
        )
        for child in children:
            bind.execute(sa.text("DELETE FROM schemas WHERE uid = :uid"), {"uid": child["uid"]})
        bind.execute(sa.text("DELETE FROM schemas WHERE uid = :uid"), {"uid": old_base_uid})

    # Every ticket's attributes, from the Jira-era keys onto the ARGUS ones.
    # Row by row rather than in SQL so the mapping has one definition — the
    # same function the importer uses.
    for row in bind.execute(sa.text(
        "SELECT uid, attributes FROM issues WHERE attributes IS NOT NULL"
    )).mappings().all():
        attributes = row["attributes"]
        if isinstance(attributes, str):
            attributes = json.loads(attributes)
        if not attributes:
            continue
        migrated = migrate_legacy_attributes(attributes)
        # A ticket that came from Jira can say so, now there's a field for it.
        if migrated.get("argus_source_key") and not migrated.get("argus_source"):
            migrated["argus_source"] = "jira"
        if migrated != attributes:
            bind.execute(
                sa.text("UPDATE issues SET attributes = CAST(:a AS jsonb) WHERE uid = :uid"),
                {"uid": row["uid"], "a": json.dumps(migrated)},
            )


def downgrade() -> None:
    # The ARGUS keys carry strictly more than the Jira ones did — a source,
    # a category — so reversing would discard what the move gained. Only the
    # type name is restored.
    op.get_bind().execute(sa.text(
        "UPDATE schemas SET name = 'Jira Issue' WHERE uid LIKE '%:argus-ticket'"
    ))
