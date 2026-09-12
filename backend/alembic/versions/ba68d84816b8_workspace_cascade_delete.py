"""workspace cascade delete

Revision ID: ba68d84816b8
Revises: 3556590ec176
Create Date: 2026-09-10 16:20:32.907005

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ba68d84816b8'
down_revision: Union[str, None] = '3556590ec176'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = [
    "api_tokens", "assets", "attachments", "global_values",
    "import_jobs", "issues", "relations", "schemas",
]


def upgrade() -> None:
    for table in _TABLES:
        fk = f"{table}_workspace_id_fkey"
        op.drop_constraint(fk, table, type_='foreignkey')
        op.create_foreign_key(fk, table, 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')

    op.drop_constraint('memberships_user_id_fkey', 'memberships', type_='foreignkey')
    op.drop_constraint('memberships_workspace_id_fkey', 'memberships', type_='foreignkey')
    op.create_foreign_key(
        'memberships_user_id_fkey', 'memberships', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'memberships_workspace_id_fkey', 'memberships', 'workspaces', ['workspace_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('memberships_workspace_id_fkey', 'memberships', type_='foreignkey')
    op.drop_constraint('memberships_user_id_fkey', 'memberships', type_='foreignkey')
    op.create_foreign_key(
        'memberships_workspace_id_fkey', 'memberships', 'workspaces', ['workspace_id'], ['id']
    )
    op.create_foreign_key('memberships_user_id_fkey', 'memberships', 'users', ['user_id'], ['id'])

    for table in reversed(_TABLES):
        fk = f"{table}_workspace_id_fkey"
        op.drop_constraint(fk, table, type_='foreignkey')
        op.create_foreign_key(fk, table, 'workspaces', ['workspace_id'], ['id'])
