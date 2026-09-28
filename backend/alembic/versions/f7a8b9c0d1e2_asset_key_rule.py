"""Generated asset keys: a pattern per workspace and its counters

Revision ID: f7a8b9c0d1e2
Revises: e7f8a9b0c1d2
"""
import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Null means the default pattern (app/services/asset_keys.py).
    op.add_column("workspaces", sa.Column("asset_key_pattern", sa.String(), nullable=True))
    op.create_table(
        "asset_key_counters",
        sa.Column("workspace_id", sa.String(), primary_key=True),
        # The pattern rendered around {SEQ}, e.g. "SPARC-IP-#": one sequence each.
        sa.Column("scope", sa.String(), primary_key=True),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("asset_key_counters")
    op.drop_column("workspaces", "asset_key_pattern")
