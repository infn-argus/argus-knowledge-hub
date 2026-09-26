"""AI Intake model profiles and the profile of each run (asset-model-revision §23.8, §23.12)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # intake_runs is append-only: adding a nullable column rewrites no row.
    op.add_column("intake_runs", sa.Column("profile_id", sa.String(), nullable=True))
    op.create_table(
        "intake_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("vision_model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="candidate"),
        sa.Column("evaluation", postgresql.JSONB(), nullable=True),
        sa.Column("exception_reason", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("activated_by", sa.String(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_intake_profiles_workspace_id", "intake_profiles", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("intake_profiles")
    op.drop_column("intake_runs", "profile_id")
