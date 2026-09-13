"""links between tickets

Revision ID: f2a9d3c85e14
Revises: e8c1a4f7b923
Create Date: 2026-09-13

An epic and its stories, a parent and its sub-tasks, a fault that blocks
another: these were strings holding a key, which can only be read in one
direction and only matches if the other ticket happens to exist. They are
edges now, like the links to objects and documents.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a9d3c85e14"
down_revision: Union[str, None] = "e8c1a4f7b923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "issue_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_issue_uid", sa.String(), nullable=False),
        sa.Column("to_issue_uid", sa.String(), nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_issue_uid"], ["issues.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_issue_uid"], ["issues.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_issue_uid", "to_issue_uid", "relation_type"),
    )
    op.create_index("ix_issue_links_from_issue_uid", "issue_links", ["from_issue_uid"])
    op.create_index("ix_issue_links_to_issue_uid", "issue_links", ["to_issue_uid"])


def downgrade() -> None:
    op.drop_index("ix_issue_links_to_issue_uid", table_name="issue_links")
    op.drop_index("ix_issue_links_from_issue_uid", table_name="issue_links")
    op.drop_table("issue_links")
