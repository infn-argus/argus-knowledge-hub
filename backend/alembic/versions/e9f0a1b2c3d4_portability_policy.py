"""Portability policy: retention and legal holds, background jobs

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for t in ("portability_exports", "portability_imports"):
        op.add_column(t, sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.add_column(t, sa.Column("legal_hold_reason", sa.String(), nullable=True))
        op.add_column(t, sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "portability_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("subject_kind", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False, index=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, index=True),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("portability_jobs")
    for t in ("portability_exports", "portability_imports"):
        for c in ("purged_at", "legal_hold_reason", "legal_hold"):
            op.drop_column(t, c)
