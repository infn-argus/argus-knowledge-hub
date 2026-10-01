"""Catalogue mappings: imported hardware models proposed as Product Models and Vendors

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalogue_mappings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("target_workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="analysing"),
        sa.Column("use_ai", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_type_uids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analysed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_catalogue_mappings_source_workspace_id", "catalogue_mappings", ["source_workspace_id"])
    op.create_index("ix_catalogue_mappings_target_workspace_id", "catalogue_mappings", ["target_workspace_id"])
    op.create_table(
        "catalogue_mapping_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mapping_id", sa.String(), sa.ForeignKey("catalogue_mappings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_uid", sa.String(), nullable=False),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("proposal", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("result_uid", sa.String(), nullable=True),
        sa.Column("created_uids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("label_uids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_catalogue_mapping_items_mapping_id", "catalogue_mapping_items", ["mapping_id"])
    op.create_index("ix_catalogue_mapping_items_source_uid", "catalogue_mapping_items", ["source_uid"])
    op.create_index("ix_catalogue_mapping_items_status", "catalogue_mapping_items", ["status"])


def downgrade() -> None:
    op.drop_table("catalogue_mapping_items")
    op.drop_table("catalogue_mappings")
