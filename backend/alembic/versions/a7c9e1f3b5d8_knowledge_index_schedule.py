"""Ask ARGUS: when the written knowledge is indexed without anyone asking

Two settings beside the AI endpoint: whether publishing or retiring a document brings the index up to
date, and how often the whole index is refreshed on a timer (0: never). On by default, every 12 hours.

Revision ID: a7c9e1f3b5d8
Revises: f1a3c5e7b9d2
"""
import sqlalchemy as sa
from alembic import op

revision = "a7c9e1f3b5d8"
down_revision = "f1a3c5e7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_configs", sa.Column("index_on_publish", sa.Boolean(), nullable=False,
                                           server_default=sa.true()))
    op.add_column("llm_configs", sa.Column("index_interval_hours", sa.Integer(), nullable=False,
                                           server_default="12"))


def downgrade() -> None:
    op.drop_column("llm_configs", "index_interval_hours")
    op.drop_column("llm_configs", "index_on_publish")
