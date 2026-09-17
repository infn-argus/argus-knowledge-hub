"""icon library

Revision ID: b6d9e3f1a8c2
Revises: a3f4c8d1e2b5
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b6d9e3f1a8c2'
down_revision: Union[str, None] = 'a3f4c8d1e2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('icons',
    sa.Column('uid', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('filename', sa.String(), nullable=False),
    sa.Column('mime_type', sa.String(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('storage_path', sa.String(), nullable=False),
    sa.Column('is_global', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('uid')
    )
    op.create_index(op.f('ix_icons_workspace_id'), 'icons', ['workspace_id'], unique=False)

    op.add_column('schemas', sa.Column('icon_uid', sa.String(), nullable=True))
    op.create_foreign_key('schemas_icon_uid_fkey', 'schemas', 'icons', ['icon_uid'], ['uid'])

    # A schema icon was, until now, just an Attachment row with no owning
    # asset/revision/issue. Reuse the attachment's own uid as the new Icon's
    # uid — the file at storage_path doesn't move, so this is a metadata-only
    # migration — then point each schema at it and drop the old attachment.
    op.execute("""
        INSERT INTO icons (uid, workspace_id, name, filename, mime_type, file_size, storage_path, is_global, created_at, updated_at)
        SELECT a.uid, a.workspace_id, s.name, a.filename, a.mime_type, a.file_size, a.storage_path, false, a.created_at, a.updated_at
        FROM attachments a
        JOIN schemas s ON s.icon_attachment_uid = a.uid
    """)
    op.execute("UPDATE schemas SET icon_uid = icon_attachment_uid WHERE icon_attachment_uid IS NOT NULL")
    op.execute("DELETE FROM attachments WHERE uid IN (SELECT uid FROM icons)")

    op.drop_column('schemas', 'icon_attachment_uid')


def downgrade() -> None:
    op.add_column('schemas', sa.Column('icon_attachment_uid', sa.String(), nullable=True))
    op.execute("""
        INSERT INTO attachments (uid, workspace_id, asset_uid, filename, mime_type, file_size, storage_path, created_at, updated_at)
        SELECT uid, workspace_id, NULL, filename, mime_type, file_size, storage_path, created_at, updated_at
        FROM icons
    """)
    op.execute("UPDATE schemas SET icon_attachment_uid = icon_uid WHERE icon_uid IS NOT NULL")

    op.drop_constraint('schemas_icon_uid_fkey', 'schemas', type_='foreignkey')
    op.drop_column('schemas', 'icon_uid')
    op.drop_index(op.f('ix_icons_workspace_id'), table_name='icons')
    op.drop_table('icons')
