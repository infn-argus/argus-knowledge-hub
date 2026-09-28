"""Field-client device registry (asset-model-revision §24.3)

Revision ID: a9b0c1d2e3f4
Revises: f7a8b9c0d1e2
"""
import sqlalchemy as sa
from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("principal", sa.String(), nullable=False),
        sa.Column("installation_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("app_version", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(), nullable=True),
        sa.Column("revoke_reason", sa.String(), nullable=True),
    )
    op.create_index("ix_devices_principal", "devices", ["principal"])


def downgrade() -> None:
    op.drop_table("devices")
