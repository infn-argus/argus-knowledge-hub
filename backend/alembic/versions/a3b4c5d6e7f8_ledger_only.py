"""ledger-only workspaces (asset-model-revision §13 S5)

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
"""
import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("ledger_only", sa.Boolean(), nullable=False, server_default="false"))
    from app.ledger.writer import install_guard
    install_guard(op.get_bind())


def downgrade() -> None:
    for table in ("assets", "relations"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_ledger_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS ledger_only_guard()")
    op.drop_column("workspaces", "ledger_only")
