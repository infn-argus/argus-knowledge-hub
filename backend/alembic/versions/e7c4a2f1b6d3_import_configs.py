"""import configs

Revision ID: e7c4a2f1b6d3
Revises: d3a1f6e9c2b4
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e7c4a2f1b6d3'
down_revision: Union[str, None] = 'd3a1f6e9c2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'import_configs',
        sa.Column('uid', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('merge_strategy', sa.String(), nullable=False),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('encrypted_secret', sa.String(), nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_import_job_uid', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
    )
    op.create_index(
        op.f('ix_import_configs_workspace_id'), 'import_configs', ['workspace_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_import_configs_workspace_id'), table_name='import_configs')
    op.drop_table('import_configs')
