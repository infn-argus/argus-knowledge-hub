"""equipment_class vocabulary and governance (asset-model-revision §5.5)

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment_classes",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("promoted_type", sa.String(), nullable=True),
        sa.Column("added_by", sa.String(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
    )
    op.create_table(
        "equipment_class_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("class_name", sa.String(), nullable=False, index=True),
        sa.Column("attribute", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "equipment_class_reviews",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("class_name", sa.String(), nullable=False, index=True),
        sa.Column("triggers", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("equipment_class_reviews")
    op.drop_table("equipment_class_requests")
    op.drop_table("equipment_classes")
