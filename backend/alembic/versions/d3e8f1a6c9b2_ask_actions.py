"""Ask ARGUS: changes the assistant proposes, applied only when confirmed

Revision ID: d3e8f1a6c9b2
Revises: c7d1e9a4b2f8
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d3e8f1a6c9b2"
down_revision = "c7d1e9a4b2f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ask_actions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("ask_conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("turn_seq", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="proposed"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ask_actions_conversation_id", "ask_actions", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_ask_actions_conversation_id", table_name="ask_actions")
    op.drop_table("ask_actions")
