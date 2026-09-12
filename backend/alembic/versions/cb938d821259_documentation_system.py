"""documentation system

Revision ID: cb938d821259
Revises: ba68d84816b8
Create Date: 2026-09-10 16:35:47.599085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'cb938d821259'
down_revision: Union[str, None] = 'ba68d84816b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `documents` and `document_revisions` reference each other
    # (documents.current_revision_uid <-> document_revisions.document_uid),
    # so `documents` is created first WITHOUT that one FK, then
    # `document_revisions` (whose FK to documents.uid now resolves), then the
    # circular FK is added once both tables exist.
    op.create_table('documents',
    sa.Column('uid', sa.String(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('document_type_uid', sa.String(), nullable=True),
    sa.Column('owner_user_id', sa.String(), nullable=True),
    sa.Column('responsible_service_asset_uid', sa.String(), nullable=True),
    sa.Column('authority_level', sa.String(), nullable=False),
    sa.Column('confidentiality', sa.String(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('current_revision_uid', sa.String(), nullable=True),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_type_uid'], ['schemas.uid'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['responsible_service_asset_uid'], ['assets.uid'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('uid')
    )
    op.create_index(op.f('ix_documents_code'), 'documents', ['code'], unique=True)
    op.create_index(op.f('ix_documents_document_type_uid'), 'documents', ['document_type_uid'], unique=False)
    op.create_index(op.f('ix_documents_workspace_id'), 'documents', ['workspace_id'], unique=False)

    op.create_table('document_revisions',
    sa.Column('uid', sa.String(), nullable=False),
    sa.Column('document_uid', sa.String(), nullable=False),
    sa.Column('revision_number', sa.Integer(), nullable=False),
    sa.Column('state', sa.String(), nullable=False),
    sa.Column('body_markdown', sa.String(), nullable=True),
    sa.Column('steps', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('valid_from', sa.Date(), nullable=True),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('next_review_due', sa.Date(), nullable=True),
    sa.Column('authored_by', sa.String(), nullable=True),
    sa.Column('approved_by', sa.String(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_comment', sa.String(), nullable=True),
    sa.Column('superseded_by_uid', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['authored_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['document_uid'], ['documents.uid'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['superseded_by_uid'], ['document_revisions.uid'], ),
    sa.PrimaryKeyConstraint('uid')
    )
    op.create_index(op.f('ix_document_revisions_document_uid'), 'document_revisions', ['document_uid'], unique=False)

    op.create_foreign_key(
        'documents_current_revision_uid_fkey', 'documents', 'document_revisions',
        ['current_revision_uid'], ['uid'], ondelete='SET NULL',
    )

    op.create_table('document_relations',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('from_document_uid', sa.String(), nullable=False),
    sa.Column('to_type', sa.String(), nullable=False),
    sa.Column('to_uid', sa.String(), nullable=False),
    sa.Column('relation_type', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['from_document_uid'], ['documents.uid'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_relations_from_document_uid'), 'document_relations', ['from_document_uid'], unique=False)
    op.create_index(op.f('ix_document_relations_to_uid'), 'document_relations', ['to_uid'], unique=False)
    op.create_index(op.f('ix_document_relations_workspace_id'), 'document_relations', ['workspace_id'], unique=False)

    op.add_column('attachments', sa.Column('document_revision_uid', sa.String(), nullable=True))
    op.create_index(op.f('ix_attachments_document_revision_uid'), 'attachments', ['document_revision_uid'], unique=False)
    op.create_foreign_key(
        'attachments_document_revision_uid_fkey', 'attachments', 'document_revisions',
        ['document_revision_uid'], ['uid'], ondelete='CASCADE',
    )

    op.add_column('memberships', sa.Column('can_read_documents', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('memberships', sa.Column('can_create_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('memberships', sa.Column('can_modify_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('memberships', sa.Column('can_delete_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('memberships', sa.Column('can_approve_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('workspaces', sa.Column('default_can_read_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('workspaces', sa.Column('default_can_create_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('workspaces', sa.Column('default_can_modify_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('workspaces', sa.Column('default_can_delete_documents', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('workspaces', sa.Column('default_can_approve_documents', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('workspaces', 'default_can_approve_documents')
    op.drop_column('workspaces', 'default_can_delete_documents')
    op.drop_column('workspaces', 'default_can_modify_documents')
    op.drop_column('workspaces', 'default_can_create_documents')
    op.drop_column('workspaces', 'default_can_read_documents')
    op.drop_column('memberships', 'can_approve_documents')
    op.drop_column('memberships', 'can_delete_documents')
    op.drop_column('memberships', 'can_modify_documents')
    op.drop_column('memberships', 'can_create_documents')
    op.drop_column('memberships', 'can_read_documents')

    op.drop_constraint('attachments_document_revision_uid_fkey', 'attachments', type_='foreignkey')
    op.drop_index(op.f('ix_attachments_document_revision_uid'), table_name='attachments')
    op.drop_column('attachments', 'document_revision_uid')

    op.drop_index(op.f('ix_document_relations_workspace_id'), table_name='document_relations')
    op.drop_index(op.f('ix_document_relations_to_uid'), table_name='document_relations')
    op.drop_index(op.f('ix_document_relations_from_document_uid'), table_name='document_relations')
    op.drop_table('document_relations')

    op.drop_constraint('documents_current_revision_uid_fkey', 'documents', type_='foreignkey')

    op.drop_index(op.f('ix_document_revisions_document_uid'), table_name='document_revisions')
    op.drop_table('document_revisions')

    op.drop_index(op.f('ix_documents_workspace_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_document_type_uid'), table_name='documents')
    op.drop_index(op.f('ix_documents_code'), table_name='documents')
    op.drop_table('documents')
