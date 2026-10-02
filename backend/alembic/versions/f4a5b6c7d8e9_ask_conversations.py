"""Ask ARGUS conversations and their messages

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ask_conversations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ask_conversations_workspace_id", "ask_conversations", ["workspace_id"])
    op.create_index("ix_ask_conversations_owner", "ask_conversations", ["owner"])
    op.create_table(
        "ask_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("ask_conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("steps", postgresql.JSONB(), nullable=True),
        sa.Column("stopped", sa.String(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ask_messages_conversation_id", "ask_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("ask_messages")
    op.drop_table("ask_conversations")
