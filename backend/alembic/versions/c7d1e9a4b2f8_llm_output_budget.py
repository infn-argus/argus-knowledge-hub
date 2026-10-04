"""AI settings: the output-token budget (empty: no limit)

Revision ID: c7d1e9a4b2f8
Revises: f0a1b2c3d4e5
"""
import sqlalchemy as sa
from alembic import op

revision = "c7d1e9a4b2f8"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_configs", sa.Column("max_output_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_configs", "max_output_tokens")
