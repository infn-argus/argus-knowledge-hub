"""workspace global flag

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-09-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workspaces',
        sa.Column('is_global', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('workspaces', 'is_global', server_default=None)


def downgrade() -> None:
    op.drop_column('workspaces', 'is_global')
