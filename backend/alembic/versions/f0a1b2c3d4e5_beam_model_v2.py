"""Beam model v2: stored canonical documents and asset bindings

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_model_documents",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("report", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("imported_by", sa.String(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "model_id", "revision", name="uq_beam_model_document"),
    )
    op.create_index("ix_beam_model_documents_workspace_id", "beam_model_documents", ["workspace_id"])
    op.create_index("ix_beam_model_documents_model_id", "beam_model_documents", ["model_id"])
    op.create_index("ix_beam_model_documents_current", "beam_model_documents", ["current"])
    op.create_table(
        "beam_asset_bindings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("component_id", sa.String(), nullable=False),
        sa.Column("component_uid", sa.String(), nullable=True),
        sa.Column("relation", sa.String(), nullable=False, server_default="implemented_by"),
        sa.Column("asset_uid", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("authority", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("candidates", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("method", sa.String(), nullable=False, server_default="asset_sync"),
        sa.Column("matcher", sa.String(), nullable=True),
        sa.Column("matcher_version", sa.String(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("installation_uid", sa.String(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("workspace_id", "model_id", "component_id", "relation", "asset_uid",
                            name="uq_beam_asset_binding"),
    )
    for col in ("workspace_id", "model_id", "component_id", "component_uid", "asset_uid", "status"):
        op.create_index(f"ix_beam_asset_bindings_{col}", "beam_asset_bindings", [col])


def downgrade() -> None:
    op.drop_table("beam_asset_bindings")
    op.drop_table("beam_model_documents")
