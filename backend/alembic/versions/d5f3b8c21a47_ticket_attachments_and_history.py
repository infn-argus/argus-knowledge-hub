"""ticket attachments and history

Revision ID: d5f3b8c21a47
Revises: b7e2c93f5a18
Create Date: 2026-09-13

A ticket could carry neither a file of its own nor any record of what had
happened to it: attachments hung off assets only, so a screenshot of a
fault had to be filed against whatever object the ticket mentioned, and
history existed for objects but not for tickets.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5f3b8c21a47"
down_revision: Union[str, None] = "b7e2c93f5a18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("attachments", sa.Column("issue_uid", sa.String(), nullable=True))
    op.create_index("ix_attachments_issue_uid", "attachments", ["issue_uid"])
    op.create_foreign_key(
        "fk_attachments_issue_uid", "attachments", "issues", ["issue_uid"], ["uid"],
        ondelete="CASCADE",
    )

    op.create_table(
        "issue_history",
        sa.Column("uid", sa.String(), nullable=False),
        sa.Column("issue_uid", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=True),
        sa.Column("from_value", sa.String(), nullable=True),
        sa.Column("to_value", sa.String(), nullable=True),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backend_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["issue_uid"], ["issues.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
    )
    op.create_index("ix_issue_history_issue_uid", "issue_history", ["issue_uid"])
    op.create_index("ix_issue_history_backend_id", "issue_history", ["backend_id"])


def downgrade() -> None:
    op.drop_index("ix_issue_history_backend_id", table_name="issue_history")
    op.drop_index("ix_issue_history_issue_uid", table_name="issue_history")
    op.drop_table("issue_history")
    op.drop_constraint("fk_attachments_issue_uid", "attachments", type_="foreignkey")
    op.drop_index("ix_attachments_issue_uid", table_name="attachments")
    op.drop_column("attachments", "issue_uid")
