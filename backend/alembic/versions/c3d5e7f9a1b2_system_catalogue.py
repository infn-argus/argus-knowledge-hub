"""The system catalogue: one workspace marked as the installation's catalogue (docs/system-catalogue.md).

The workspace marked is the one found today as the catalogue — it holds the global Asset type — and, when
several do, the one holding the most shared Product Models. With none, none is marked: an administrator
designates it, or the first workspace given the object catalogue as the one others hang from becomes it.

Revision ID: c3d5e7f9a1b2
Revises: e8c1a4f7b2d9
"""
import sqlalchemy as sa

from alembic import op

revision = "c3d5e7f9a1b2"
down_revision = "e8c1a4f7b2d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("role", sa.String(), nullable=True))
    op.create_index("uq_workspaces_catalogue", "workspaces", ["role"], unique=True,
                    postgresql_where=sa.text("role = 'catalogue'"))
    op.execute("""
        UPDATE workspaces SET role = 'catalogue' WHERE id = (
            SELECT s.workspace_id FROM schemas s
            WHERE s.name = 'Asset' AND s.applies_to = 'objects' AND s.is_global
            ORDER BY (SELECT count(*) FROM assets a
                      WHERE a.workspace_id = s.workspace_id AND a.type = 'Product Model' AND a.is_global) DESC,
                     s.workspace_id
            LIMIT 1)
    """)


def downgrade() -> None:
    op.drop_index("uq_workspaces_catalogue", table_name="workspaces")
    op.drop_column("workspaces", "role")
