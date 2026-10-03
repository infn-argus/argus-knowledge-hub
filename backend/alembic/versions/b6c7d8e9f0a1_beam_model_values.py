"""Beam model: the values that depend on a model dataset

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beam_model_values",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_uid", sa.String(), sa.ForeignKey("assets.uid", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_uid", sa.String(), sa.ForeignKey("assets.uid", ondelete="CASCADE"), nullable=False),
        sa.Column("path_uid", sa.String(), sa.ForeignKey("assets.uid", ondelete="CASCADE"), nullable=True),
        *[sa.Column(c, sa.Float(), nullable=True) for c in ("s", "x", "y", "z", "yaw", "pitch", "roll")],
        sa.Column("physics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("optics", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("native", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("dataset_uid", "subject_uid", "path_uid", name="uq_beam_model_value"),
    )
    for col in ("workspace_id", "dataset_uid", "subject_uid", "path_uid"):
        op.create_index(f"ix_beam_model_values_{col}", "beam_model_values", [col])


def downgrade() -> None:
    op.drop_table("beam_model_values")
