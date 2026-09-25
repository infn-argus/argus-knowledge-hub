"""golden incidents for I-MIG-7 (asset-model-revision §12.6)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "golden_incidents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("symptoms", JSONB(), nullable=False, server_default="[]"),
        sa.Column("symptom_kind", JSONB(), nullable=False, server_default="{}"),
        sa.Column("healthy", JSONB(), nullable=False, server_default="[]"),
        sa.Column("expected_causes", JSONB(), nullable=False, server_default="[]"),
        sa.Column("ticket_uid", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("golden_incidents")
