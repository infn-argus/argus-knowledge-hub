"""transfer jobs

Revision ID: a3f4c8d1e2b5
Revises: f6a7b8c9d0e1
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3f4c8d1e2b5'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('transfer_jobs',
    sa.Column('uid', sa.String(), nullable=False),
    sa.Column('target_workspace_id', sa.String(), nullable=False),
    sa.Column('mode', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('progress', sa.String(), nullable=True),
    sa.Column('counts', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['target_workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('uid')
    )
    op.create_index(op.f('ix_transfer_jobs_target_workspace_id'), 'transfer_jobs', ['target_workspace_id'], unique=False)
    op.create_index(op.f('ix_transfer_jobs_workspace_id'), 'transfer_jobs', ['workspace_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_transfer_jobs_workspace_id'), table_name='transfer_jobs')
    op.drop_index(op.f('ix_transfer_jobs_target_workspace_id'), table_name='transfer_jobs')
    op.drop_table('transfer_jobs')
