"""relation registry mode per workspace (asset-model-revision §13 S7)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""
import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("registry_mode", sa.String(), nullable=False, server_default="warn"))


def downgrade() -> None:
    op.drop_column("workspaces", "registry_mode")
