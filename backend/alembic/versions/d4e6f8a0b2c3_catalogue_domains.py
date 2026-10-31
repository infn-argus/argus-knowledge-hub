"""A collection's domains, kept with each installation of it: which workspaces its models are offered to
(docs/system-catalogue.md, C4). Null for installations made before: offered everywhere, as before.

Revision ID: d4e6f8a0b2c3
Revises: c3d5e7f9a1b2
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d4e6f8a0b2c3"
down_revision = "c3d5e7f9a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalogue_installations", sa.Column("domains", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalogue_installations", "domains")
