"""Portable exports and imports: lifecycles, their audit, the row map, tags seen, the chain

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB()
NOW = sa.text("now()")


def upgrade() -> None:
    from app.ledger.audit import GUARD_FUNCTION, guard_sql
    op.add_column("workspaces", sa.Column("import_state", sa.String(), nullable=True))
    op.create_table(
        "portability_exports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("workspaces", JSONB, nullable=False, server_default="[]"),
        sa.Column("base_export_id", sa.String(), nullable=True),
        sa.Column("classifications", JSONB, nullable=False, server_default="[]"),
        sa.Column("decisions", JSONB, nullable=False, server_default="{}"),
        sa.Column("destination", JSONB, nullable=False, server_default="{}"),
        sa.Column("state", sa.String(), nullable=False, index=True),
        sa.Column("risk", sa.String(), nullable=False, server_default="normal"),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("analysis", JSONB, nullable=False, server_default="{}"),
        sa.Column("watermark", JSONB, nullable=True),
        sa.Column("manifest", JSONB, nullable=True),
        sa.Column("manifest_sha256", sa.String(), nullable=True),
        sa.Column("out_dir", sa.String(), nullable=True),
        sa.Column("git", JSONB, nullable=False, server_default="{}"),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW),
    )
    op.create_table(
        "portability_imports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("source", JSONB, nullable=False, server_default="{}"),
        sa.Column("state", sa.String(), nullable=False, index=True),
        sa.Column("requested_by", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("quarantine_dir", sa.String(), nullable=True),
        sa.Column("commit", sa.String(), nullable=True),
        sa.Column("manifest", JSONB, nullable=True),
        sa.Column("verification", JSONB, nullable=False, server_default="{}"),
        sa.Column("dry_run", JSONB, nullable=False, server_default="{}"),
        sa.Column("decisions", JSONB, nullable=False, server_default="{}"),
        sa.Column("checkpoints", JSONB, nullable=False, server_default="{}"),
        sa.Column("reconciliation", JSONB, nullable=True),
        sa.Column("reconciliation_sha256", sa.String(), nullable=True),
        sa.Column("error", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW),
    )
    op.create_table(
        "portability_events",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("subject_kind", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False, index=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("from_state", sa.String(), nullable=True),
        sa.Column("to_state", sa.String(), nullable=True),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=NOW),
    )
    op.create_table(
        "portability_row_map",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("family", sa.String(), nullable=False),
        sa.Column("source_key", sa.String(), nullable=False),
        sa.Column("local_key", sa.String(), nullable=False),
        sa.Column("import_id", sa.String(), nullable=False, index=True),
        sa.Column("created", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("content_sha256", sa.String(), nullable=True),
        sa.UniqueConstraint("origin", "family", "source_key", name="uq_portability_row"),
    )
    op.create_table(
        "portability_tags_seen",
        sa.Column("repository_id", sa.String(), primary_key=True),
        sa.Column("tag", sa.String(), primary_key=True),
        sa.Column("commit", sa.String(), nullable=False),
        sa.Column("tag_object", sa.String(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=NOW),
        sa.Column("import_id", sa.String(), nullable=False),
    )
    op.create_table(
        "portability_chain",
        sa.Column("origin", sa.String(), primary_key=True),
        sa.Column("export_id", sa.String(), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("watermark_label", sa.BigInteger(), nullable=False),
        sa.Column("import_id", sa.String(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=NOW),
    )
    op.execute(GUARD_FUNCTION)
    op.execute(guard_sql("portability_events"))


def downgrade() -> None:
    for t in ("portability_chain", "portability_tags_seen", "portability_row_map", "portability_events",
              "portability_imports", "portability_exports"):
        op.drop_table(t)
    op.drop_column("workspaces", "import_state")
