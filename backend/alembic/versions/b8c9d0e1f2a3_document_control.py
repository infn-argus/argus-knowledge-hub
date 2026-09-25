"""Document retention and supersession; access reviews.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("documents", sa.Column("retention_class", sa.String(), nullable=False, server_default="5y"))
    op.add_column("documents", sa.Column("retired_at", TS, nullable=True))
    op.add_column("documents", sa.Column("superseded_by_uid", sa.String(), nullable=True))
    op.create_table(
        "access_reviews",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", TS, nullable=True),
        sa.Column("snapshot", J, nullable=False),
        sa.Column("snapshot_hash", sa.String(), nullable=False),
        sa.Column("changes", J, nullable=False, server_default="{}"),
        sa.Column("signatures", J, nullable=False, server_default="[]"),
        sa.Column("required_signers", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("completed_at", TS, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("access_reviews")
    op.drop_column("documents", "superseded_by_uid")
    op.drop_column("documents", "retired_at")
    op.drop_column("documents", "retention_class")
