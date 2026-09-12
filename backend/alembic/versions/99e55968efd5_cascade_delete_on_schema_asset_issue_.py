"""cascade delete on schema/asset/issue type links

Revision ID: 99e55968efd5
Revises: 6f00386a82e4
Create Date: 2026-09-10 10:51:50.313785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '99e55968efd5'
down_revision: Union[str, None] = '6f00386a82e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('assets_schema_uid_fkey', 'assets', type_='foreignkey')
    op.create_foreign_key(
        'assets_schema_uid_fkey', 'assets', 'schemas', ['schema_uid'], ['uid'], ondelete='CASCADE'
    )
    op.drop_constraint('issues_schema_uid_fkey', 'issues', type_='foreignkey')
    op.drop_constraint('issues_asset_uid_fkey', 'issues', type_='foreignkey')
    op.create_foreign_key(
        'issues_asset_uid_fkey', 'issues', 'assets', ['asset_uid'], ['uid'], ondelete='SET NULL'
    )
    op.create_foreign_key(
        'issues_schema_uid_fkey', 'issues', 'schemas', ['schema_uid'], ['uid'], ondelete='CASCADE'
    )
    op.drop_constraint('schemas_parent_schema_uid_fkey', 'schemas', type_='foreignkey')
    op.create_foreign_key(
        'schemas_parent_schema_uid_fkey',
        'schemas',
        'schemas',
        ['parent_schema_uid'],
        ['uid'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('schemas_parent_schema_uid_fkey', 'schemas', type_='foreignkey')
    op.create_foreign_key(
        'schemas_parent_schema_uid_fkey', 'schemas', 'schemas', ['parent_schema_uid'], ['uid']
    )
    op.drop_constraint('issues_schema_uid_fkey', 'issues', type_='foreignkey')
    op.drop_constraint('issues_asset_uid_fkey', 'issues', type_='foreignkey')
    op.create_foreign_key('issues_asset_uid_fkey', 'issues', 'assets', ['asset_uid'], ['uid'])
    op.create_foreign_key('issues_schema_uid_fkey', 'issues', 'schemas', ['schema_uid'], ['uid'])
    op.drop_constraint('assets_schema_uid_fkey', 'assets', type_='foreignkey')
    op.create_foreign_key('assets_schema_uid_fkey', 'assets', 'schemas', ['schema_uid'], ['uid'])
