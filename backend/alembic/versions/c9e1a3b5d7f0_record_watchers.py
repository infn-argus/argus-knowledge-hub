"""People following equipment and documents.

Revision ID: c9e1a3b5d7f0
Revises: b8d0f2a4c6e9
"""
import sqlalchemy as sa
from alembic import op

revision = "c9e1a3b5d7f0"
down_revision = "b8d0f2a4c6e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "record_watchers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("subject_uid", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("subject", "subject_uid", "user_id"),
    )
    op.create_index("ix_record_watchers_subject_uid", "record_watchers", ["subject_uid"])
    op.create_index("ix_record_watchers_user_id", "record_watchers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_record_watchers_user_id", table_name="record_watchers")
    op.drop_index("ix_record_watchers_subject_uid", table_name="record_watchers")
    op.drop_table("record_watchers")
