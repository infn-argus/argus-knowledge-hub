"""What an importer last wrote on an object, so a re-import keeps manual edits.

Revision ID: b1c2d3e4f5a6
Revises: a8c3e5d7f912
Create Date: 2026-09-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a8c3e5d7f912"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_snapshots",
        sa.Column("asset_uid", sa.String(), sa.ForeignKey("assets.uid", ondelete="CASCADE"), primary_key=True),
        sa.Column("source", sa.String(), primary_key=True),
        sa.Column("values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("source_ref", sa.String(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("import_snapshots")
