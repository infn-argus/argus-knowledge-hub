"""domain stewards (asset-model-revision D3, §17.4)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""
import sqlalchemy as sa
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ledger_domains", sa.Column("steward", sa.String(), nullable=True))
    op.add_column("ledger_domains", sa.Column("backup_steward", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("ledger_domains", "backup_steward")
    op.drop_column("ledger_domains", "steward")
