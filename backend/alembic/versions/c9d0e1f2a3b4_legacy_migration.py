"""legacy migration plans and items (asset-model-revision §12)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_migration_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("inventory_workspace_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="planned"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("report_hash", sa.String(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invariants", JSONB(), nullable=True),
    )
    op.create_table(
        "legacy_migration_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("legacy_migration_plans.id", ondelete="CASCADE"),
                  index=True),
        sa.Column("legacy_uid", sa.String(), nullable=False, index=True),
        sa.Column("legacy_key", sa.String(), nullable=False),
        sa.Column("legacy_type", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("actions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("warnings", JSONB(), nullable=False, server_default="[]"),
        sa.Column("override", JSONB(), nullable=True),
        sa.Column("pre_image", JSONB(), nullable=False, server_default="{}"),
        sa.Column("pre_image_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="planned"),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("applied", JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("legacy_migration_items")
    op.drop_table("legacy_migration_plans")
