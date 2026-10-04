"""Portability: local ingestion time on ledger events, the origin chain, checkpoint sequence,
download tokens, staging metadata

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None

EVENT_TABLES = ("ledger_claim_events", "ledger_revision_events", "ledger_decisions", "ledger_status_events",
                "ledger_identity_events", "ledger_record_events", "ledger_conflict_events")
NOW = sa.text("now()")


def upgrade() -> None:
    from app.ledger.audit import guard_sql
    for t in EVENT_TABLES:
        op.add_column(t, sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True, server_default=NOW))
        # The one sanctioned write to existing audit rows, in a schema migration and nowhere else: what
        # happened here was recorded here at the time it happened. Sealed digests do not change (they
        # hash `at`, and now select by `recorded_at`, which equals it for every existing row).
        op.execute(f"ALTER TABLE {t} DISABLE TRIGGER {t}_append_only")
        op.execute(f"UPDATE {t} SET recorded_at = at")
        op.execute(f"ALTER TABLE {t} ENABLE TRIGGER {t}_append_only")
        op.alter_column(t, "recorded_at", nullable=False)
        op.create_index(f"ix_{t}_recorded_at", t, ["recorded_at"])
    op.execute("CREATE SEQUENCE IF NOT EXISTS portability_checkpoint_seq")
    op.add_column("portability_chain", sa.Column("vector_sha256", sa.String(), nullable=True))
    op.add_column("portability_chain", sa.Column("manifest_sha256", sa.String(), nullable=True))
    op.add_column("portability_imports", sa.Column("staging", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.create_table(
        "portability_origin_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("import_id", sa.String(), nullable=False, index=True),
        sa.Column("origin_instance_id", sa.String(), nullable=False, index=True),
        sa.Column("origin_family", sa.String(), nullable=False),
        sa.Column("origin_sequence", sa.String(), nullable=False),
        sa.Column("origin_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("origin_event_hash", sa.String(), nullable=False),
        sa.Column("origin_checkpoint_hash", sa.String(), nullable=False),
        sa.Column("local_table", sa.String(), nullable=False),
        sa.Column("local_key", sa.String(), nullable=False),
        sa.Column("local_ingested_at", sa.DateTime(timezone=True), server_default=NOW),
        sa.Column("local_ingestion_event_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.BigInteger(), nullable=False),
    )
    op.execute(guard_sql("portability_origin_records"))
    op.create_table(
        "portability_download_tokens",
        sa.Column("token_sha256", sa.String(), primary_key=True),
        sa.Column("export_id", sa.String(), nullable=False, index=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("manifest_sha256", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("portability_download_tokens")
    op.drop_table("portability_origin_records")
    op.drop_column("portability_imports", "staging")
    op.drop_column("portability_chain", "manifest_sha256")
    op.drop_column("portability_chain", "vector_sha256")
    op.execute("DROP SEQUENCE IF EXISTS portability_checkpoint_seq")
    for t in EVENT_TABLES:
        op.drop_index(f"ix_{t}_recorded_at", table_name=t)
        op.drop_column(t, "recorded_at")
