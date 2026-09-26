"""AI Intake audit: intake runs and outcomes (asset-model-revision §23.8)

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.ledger.audit import GUARD_FUNCTION, guard_sql
    op.create_table(
        "intake_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("input_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("input_hashes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("redactions", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("validations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "intake_outcomes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("record_kind", sa.String(), nullable=False),
        sa.Column("record_uid", sa.String(), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("decided_by", sa.String(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_intake_runs_workspace_id", "intake_runs", ["workspace_id"])
    op.create_index("ix_intake_outcomes_run_id", "intake_outcomes", ["run_id"])
    op.create_index("ix_intake_outcomes_workspace_id", "intake_outcomes", ["workspace_id"])
    op.create_index("ix_intake_outcomes_record_uid", "intake_outcomes", ["record_uid"])
    op.execute(GUARD_FUNCTION)
    for table in ("intake_runs", "intake_outcomes"):
        op.execute(guard_sql(table))


def downgrade() -> None:
    op.drop_table("intake_outcomes")
    op.drop_table("intake_runs")
