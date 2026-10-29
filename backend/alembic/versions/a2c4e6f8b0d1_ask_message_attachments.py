"""Ask: the files a question came with (their name, format and text as read).

Revision ID: a2c4e6f8b0d1
Revises: f1c3e5a7b9d2
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a2c4e6f8b0d1"
down_revision = "f1c3e5a7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ask_messages", sa.Column("attachments", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("ask_messages", "attachments")
