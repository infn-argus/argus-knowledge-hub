"""Catalogue collections: the link from a catalogue id to its record, and the releases installed.

Revision ID: e8c1a4f7b2d9
Revises: a2c4e6f8b0d1
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e8c1a4f7b2d9"
down_revision = "a2c4e6f8b0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalogue_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("catalogue_id", sa.String(), nullable=False),
        sa.Column("record_uid", sa.String(), sa.ForeignKey("assets.uid", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("collection_id", sa.String(), nullable=False),
        sa.Column("collection_version", sa.String(), nullable=False),
        sa.Column("collection_checksum", sa.String(), nullable=False),
        sa.Column("stated", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("managed_fields", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("corrections", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("conflicts", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("retired", postgresql.JSONB(), nullable=True),
        sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("adopted_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("record_uid", name="uq_catalogue_entries_record_uid"),
        sa.UniqueConstraint("workspace_id", "catalogue_id", name="uq_catalogue_entries_id"),
    )
    op.create_index("ix_catalogue_entries_workspace_id", "catalogue_entries", ["workspace_id"])
    op.create_index("ix_catalogue_entries_collection_id", "catalogue_entries", ["collection_id"])
    op.create_table(
        "catalogue_installations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_id", sa.String(), nullable=False),
        sa.Column("from_version", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("checksum", sa.String(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("installed_by", sa.String(), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_catalogue_installations_workspace_id", "catalogue_installations", ["workspace_id"])
    op.create_index("ix_catalogue_installations_collection_id", "catalogue_installations", ["collection_id"])


def downgrade() -> None:
    op.drop_table("catalogue_installations")
    op.drop_table("catalogue_entries")
