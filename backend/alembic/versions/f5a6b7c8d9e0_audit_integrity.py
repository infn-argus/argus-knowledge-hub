"""Append-only audit tables, the daily digest chain, and bulk changes.

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    "ledger_claims", "ledger_claim_events", "ledger_source_revisions", "ledger_revision_events",
    "ledger_decisions", "ledger_status_events", "ledger_identity_events", "ledger_record_events",
    "ledger_conflict_events", "ledger_job_runs", "ledger_rulesets", "ledger_migration_map",
    "ledger_reconciliation_reports", "ledger_audit_digests",
)

FUNCTION = """
CREATE OR REPLACE FUNCTION ledger_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' AND coalesce(current_setting('argus.audit_purge', true), '') = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'the audit table % is append-only (% refused)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "ledger_audit_digests",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("prev_digest", sa.String(), nullable=True),
        sa.Column("digest", sa.String(), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "ledger_bulk_changes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(), nullable=False, server_default="previewed"),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("batch_id", sa.String(), nullable=True),
        sa.Column("undo_batch_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(FUNCTION)
    for table in TABLES:
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION ledger_append_only();")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table};")
    op.execute("DROP FUNCTION IF EXISTS ledger_append_only();")
    op.drop_table("ledger_bulk_changes")
    op.drop_table("ledger_audit_digests")
