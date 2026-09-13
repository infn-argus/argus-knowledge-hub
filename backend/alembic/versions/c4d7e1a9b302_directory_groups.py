"""directory: groups, group members, and user identity columns

Revision ID: c4d7e1a9b302
Revises: a9b8c7d6e5f4
Create Date: 2026-09-13

The users table gains `oidc_sub` so a person's internal id stops being the
identity provider's subject. That separation is what lets the directory
create someone before they ever sign in, and lets INFN move from Firebase
to Keycloak without rewriting every "user"-type attribute value — those
store User.id, so existing ids must not change. Hence the backfill:
today's id *is* the subject, so it is copied across rather than replaced.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d7e1a9b302"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oidc_sub", sa.String(), nullable=True))
    op.add_column("users", sa.Column("dn", sa.String(), nullable=True))
    op.add_column("users", sa.Column("username", sa.String(), nullable=True))
    op.add_column("users", sa.Column("source", sa.String(), nullable=False, server_default="oidc"))
    op.add_column("users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True))

    # Every existing row was created by an OIDC sign-in with id = sub.
    op.execute("UPDATE users SET oidc_sub = id WHERE oidc_sub IS NULL")

    op.create_index("ix_users_oidc_sub", "users", ["oidc_sub"], unique=True)
    op.create_index("ix_users_dn", "users", ["dn"], unique=True)

    op.create_table(
        "groups",
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("dn", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="local"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("uid"),
    )
    op.create_index("ix_groups_dn", "groups", ["dn"], unique=True)
    op.create_index("ix_groups_name", "groups", ["name"], unique=False)

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_uid", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="local"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_uid"], ["groups.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_uid", "user_id"),
    )
    op.create_index("ix_group_members_group_uid", "group_members", ["group_uid"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_group_members_user_id", table_name="group_members")
    op.drop_index("ix_group_members_group_uid", table_name="group_members")
    op.drop_table("group_members")
    op.drop_index("ix_groups_name", table_name="groups")
    op.drop_index("ix_groups_dn", table_name="groups")
    op.drop_table("groups")
    op.drop_index("ix_users_dn", table_name="users")
    op.drop_index("ix_users_oidc_sub", table_name="users")
    op.drop_column("users", "synced_at")
    op.drop_column("users", "active")
    op.drop_column("users", "source")
    op.drop_column("users", "username")
    op.drop_column("users", "dn")
    op.drop_column("users", "oidc_sub")
