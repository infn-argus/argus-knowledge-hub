"""Portability set-up registered from the web app: repositories, trusted keys, signing keys

Revision ID: e5b9c4a7d1f3
Revises: d3e8f1a6c9b2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5b9c4a7d1f3"
down_revision = "d3e8f1a6c9b2"
branch_labels = None
depends_on = None


def _approval() -> list:
    return [
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "portability_repositories",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False, server_default="other"),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("encrypted_private_key", sa.Text(), nullable=True),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=True),
        sa.Column("host_keys", postgresql.JSONB(), nullable=True),
        sa.Column("host_keys_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_approval(),
        sa.Column("last_test", postgresql.JSONB(), nullable=True),
    )
    op.create_table(
        "portability_trusted_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("principal", sa.String(), nullable=False),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        *_approval(),
    )
    op.create_table(
        "portability_signing_keys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("principal", sa.String(), nullable=False),
        sa.Column("encrypted_private_key", sa.Text(), nullable=False),
        sa.Column("public_line", sa.Text(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        *_approval(),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("portability_signing_keys")
    op.drop_table("portability_trusted_keys")
    op.drop_table("portability_repositories")
