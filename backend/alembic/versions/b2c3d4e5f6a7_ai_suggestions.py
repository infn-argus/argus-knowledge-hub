"""Proposals a model made, which nobody has accepted yet.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("target_type", sa.String(), nullable=False, index=True),
        sa.Column("target_uid", sa.String(), nullable=False, index=True),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("suggested_value", sa.String(), nullable=False),
        sa.Column("suggested_label", sa.String(), nullable=True),
        sa.Column("previous_value", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed", index=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ai_suggestions")
