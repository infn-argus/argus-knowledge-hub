"""Migration domains, reconciliation reports, derive requests, attachment
checksums and restricted-class grants on tokens.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("attachments", sa.Column("sha256", sa.String(), nullable=True))
    op.add_column("api_tokens", sa.Column("restricted_grants", J, nullable=False, server_default="[]"))
    op.create_table(
        "ledger_domains",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("resource", sa.String(), nullable=False, server_default="objects"),
        sa.Column("stage", sa.String(), nullable=False, server_default="T0"),
        sa.Column("stream_ids", J, nullable=False, server_default="[]"),
        sa.Column("pilot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archive_url", sa.String(), nullable=True),
        sa.Column("watermark", J, nullable=True),
        sa.Column("manifest_hash", sa.String(), nullable=True),
        sa.Column("frozen_at", TS, nullable=True),
        sa.Column("exited_at", TS, nullable=True),
        sa.Column("exit_decision_id", sa.String(), nullable=True),
        sa.Column("created_at", TS, nullable=True),
    )
    op.create_table(
        "ledger_reconciliation_reports",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("domain_id", sa.String(), nullable=False, index=True),
        sa.Column("manifest_hash", sa.String(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("body", J, nullable=False),
        sa.Column("body_hash", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("created_at", TS, nullable=True),
    )
    op.create_table(
        "ledger_derive_requests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_ids", J, nullable=False),
        sa.Column("cause", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending", index=True),
        sa.Column("requested_at", TS, nullable=True),
        sa.Column("done_at", TS, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ledger_derive_requests")
    op.drop_table("ledger_reconciliation_reports")
    op.drop_table("ledger_domains")
    op.drop_column("api_tokens", "restricted_grants")
    op.drop_column("attachments", "sha256")
