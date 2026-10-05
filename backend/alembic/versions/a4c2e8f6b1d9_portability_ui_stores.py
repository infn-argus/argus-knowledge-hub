"""Artifact stores registered from the web app

Revision ID: a4c2e8f6b1d9
Revises: e5b9c4a7d1f3
"""
import sqlalchemy as sa
from alembic import op

revision = "a4c2e8f6b1d9"
down_revision = "e5b9c4a7d1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portability_stores",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("portability_stores")
