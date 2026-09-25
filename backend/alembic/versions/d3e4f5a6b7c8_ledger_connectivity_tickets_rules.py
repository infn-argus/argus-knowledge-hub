"""Rule versions, ticket attribution and the migration map.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("ledger_source_revisions", sa.Column("impl_version", sa.String(), nullable=True))
    op.add_column("ledger_source_revisions", sa.Column("content", sa.LargeBinary(), nullable=True))
    op.create_table(
        "ledger_rulesets",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(), nullable=False, index=True),
        sa.Column("rules", J, nullable=False),
        sa.Column("impl", J, nullable=False, server_default="{}"),
        sa.Column("activated_by", sa.String(), nullable=False),
        sa.Column("activated_at", TS, nullable=True),
    )
    op.create_table(
        "ledger_migration_map",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("legacy_uid", sa.String(), nullable=False, index=True),
        sa.Column("new_uid", sa.String(), nullable=False, index=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("plan_id", sa.String(), nullable=True),
    )
    op.create_table(
        "ledger_ticket_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("ticket_uid", sa.String(), sa.ForeignKey("issues.uid", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("asset_uid", sa.String(), sa.ForeignKey("assets.uid", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("certainty", sa.String(), nullable=False, server_default="definite"),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("derivation", sa.String(), nullable=True),
        sa.Column("detail", J, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ledger_ticket_links")
    op.drop_table("ledger_migration_map")
    op.drop_table("ledger_rulesets")
    op.drop_column("ledger_source_revisions", "content")
    op.drop_column("ledger_source_revisions", "impl_version")
