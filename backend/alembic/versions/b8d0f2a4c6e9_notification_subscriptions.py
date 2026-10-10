"""Notifications: what a person wants to hear about in each workspace

New tickets, new or newly published documents and new equipment, per person and workspace; off unless chosen.

Revision ID: b8d0f2a4c6e9
Revises: a7c9e1f3b5d8
"""
import sqlalchemy as sa
from alembic import op

revision = "b8d0f2a4c6e9"
down_revision = "a7c9e1f3b5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("tickets", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("documents", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("assets", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_subscriptions")
