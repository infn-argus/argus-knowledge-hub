"""AI settings: a re-ranker model for written-knowledge search

Revision ID: b7e3c1f9a2d4
Revises: a4c2e8f6b1d9
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e3c1f9a2d4"
down_revision = "a4c2e8f6b1d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_configs", sa.Column("rerank_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_configs", "rerank_model")
