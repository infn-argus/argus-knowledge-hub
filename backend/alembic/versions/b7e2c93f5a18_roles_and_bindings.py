"""roles and role bindings

Revision ID: b7e2c93f5a18
Revises: c4d7e1a9b302
Create Date: 2026-09-13

Existing Membership rows are converted only where the 13 flags they carry
mean exactly what one seeded role means. Anything else is left alone and
keeps resolving through the legacy path, because converting it would have
to round the permissions either up or down — and silently granting
someone more than they had, or less, is worse than carrying the old row
for another release.
"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e2c93f5a18"
down_revision: Union[str, None] = "c4d7e1a9b302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "role_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "subject_type", "subject_id", "role_id"),
    )
    op.create_index("ix_role_bindings_workspace_id", "role_bindings", ["workspace_id"])
    op.create_index("ix_role_bindings_subject_id", "role_bindings", ["subject_id"])

    # Seed through the same definitions the application uses, so the
    # catalogue can never drift between a fresh install and a migrated one.
    from app.services.roles import SYSTEM_ROLES, matching_system_role_id, membership_permissions

    now = datetime.now(timezone.utc)
    bind = op.get_bind()
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.String), sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("permissions", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("is_system", sa.Boolean), sa.column("rank", sa.Integer),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(roles_table, [
        {
            "id": role_id, "name": name, "description": description,
            "permissions": permissions, "is_system": True, "rank": rank,
            "created_at": now, "updated_at": now,
        }
        for role_id, name, description, permissions, rank in SYSTEM_ROLES
    ])

    memberships = bind.execute(sa.text("SELECT * FROM memberships")).mappings().all()
    if memberships:
        class _Row:
            def __init__(self, mapping):
                for key, value in mapping.items():
                    setattr(self, key, value)

        converted = []
        for mapping in memberships:
            role_id = matching_system_role_id(membership_permissions(_Row(mapping)))
            if role_id is None:
                continue
            converted.append({
                "workspace_id": mapping["workspace_id"],
                "subject_type": "user",
                "subject_id": mapping["user_id"],
                "role_id": role_id,
                "created_at": now,
                "created_by": None,
            })
        if converted:
            op.bulk_insert(
                sa.table(
                    "role_bindings",
                    sa.column("workspace_id", sa.String), sa.column("subject_type", sa.String),
                    sa.column("subject_id", sa.String), sa.column("role_id", sa.String),
                    sa.column("created_at", sa.DateTime(timezone=True)),
                    sa.column("created_by", sa.String),
                ),
                converted,
            )


def downgrade() -> None:
    op.drop_index("ix_role_bindings_subject_id", table_name="role_bindings")
    op.drop_index("ix_role_bindings_workspace_id", table_name="role_bindings")
    op.drop_table("role_bindings")
    op.drop_table("roles")
