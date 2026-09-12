"""attachment backend link

Revision ID: d3a1f6e9c2b4
Revises: cb938d821259
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3a1f6e9c2b4'
down_revision: Union[str, None] = 'cb938d821259'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attachments', sa.Column('backend_id', sa.String(), nullable=True))
    op.add_column('attachments', sa.Column('backend_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('attachments', 'backend_url')
    op.drop_column('attachments', 'backend_id')
