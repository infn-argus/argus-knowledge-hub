"""API tokens: personal access tokens and robot tokens, with scopes and expiry

Revision ID: e2f4a8c6d1b3
Revises: b7e3c1f9a2d4
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2f4a8c6d1b3"
down_revision = "b7e3c1f9a2d4"
branch_labels = None
depends_on = None

ALL = '["read", "create", "modify", "delete", "approve", "admin"]'


def upgrade() -> None:
    # Existing tokens could do everything in their workspace: they become robot tokens with every scope.
    op.add_column("api_tokens", sa.Column("kind", sa.String(), nullable=False, server_default="robot"))
    op.add_column("api_tokens", sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                                          nullable=True))
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])
    op.add_column("api_tokens", sa.Column("prefix", sa.String(), nullable=True))
    op.add_column("api_tokens", sa.Column("scopes", postgresql.JSONB(), nullable=False,
                                          server_default=sa.text(f"'{ALL}'::jsonb")))
    op.add_column("api_tokens", sa.Column("resources", postgresql.JSONB(), nullable=False,
                                          server_default=sa.text("'[]'::jsonb")))
    op.add_column("api_tokens", sa.Column("created_by", sa.String(), nullable=True))
    op.add_column("api_tokens", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("api_tokens", sa.Column("revoked_by", sa.String(), nullable=True))
    op.alter_column("api_tokens", "workspace_id", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM api_tokens WHERE workspace_id IS NULL")
    op.alter_column("api_tokens", "workspace_id", nullable=False)
    for c in ("revoked_by", "expires_at", "created_by", "resources", "scopes", "prefix"):
        op.drop_column("api_tokens", c)
    op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
    op.drop_column("api_tokens", "user_id")
    op.drop_column("api_tokens", "kind")
