"""Ticket workflows, watchers, notifications and escalations.

Revision ID: a7b8c9d0e1f2
Revises: f5a6b7c8d9e0
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "ticket_workflows",
        sa.Column("uid", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("states", J, nullable=False, server_default="[]"),
        sa.Column("transitions", J, nullable=False, server_default="[]"),
        sa.Column("initial", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", J, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", TS, nullable=True),
        sa.Column("updated_at", TS, nullable=True),
    )
    op.create_table(
        "ticket_watchers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_uid", sa.String(), sa.ForeignKey("issues.uid", ondelete="CASCADE"), index=True),
        sa.Column("user", sa.String(), nullable=False, index=True),
        sa.Column("reason", sa.String(), nullable=False, server_default="manual"),
        sa.Column("created_at", TS, nullable=True),
        sa.UniqueConstraint("issue_uid", "user"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("recipient", sa.String(), nullable=False, index=True),
        sa.Column("issue_uid", sa.String(), sa.ForeignKey("issues.uid", ondelete="CASCADE"), nullable=True,
                  index=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("detail", J, nullable=False, server_default="{}"),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("created_at", TS, nullable=True),
        sa.Column("read_at", TS, nullable=True),
        sa.Column("delivered_at", TS, nullable=True),
    )
    op.create_table(
        "ticket_escalations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("issue_uid", sa.String(), sa.ForeignKey("issues.uid", ondelete="CASCADE"), index=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("entered_at", TS, nullable=False),
        sa.Column("due_at", TS, nullable=False),
        sa.Column("escalated_at", TS, nullable=True),
        sa.Column("escalated_to", J, nullable=False, server_default="[]"),
        sa.UniqueConstraint("issue_uid", "state", "entered_at"),
    )


def downgrade() -> None:
    op.drop_table("ticket_escalations")
    op.drop_table("notifications")
    op.drop_table("ticket_watchers")
    op.drop_table("ticket_workflows")
