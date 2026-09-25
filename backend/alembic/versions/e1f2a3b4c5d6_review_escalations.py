"""review queue escalations (asset-model-revision §18.2)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_escalations",
        sa.Column("item_key", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("queue", sa.String(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("targets", JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_table("review_escalations")
