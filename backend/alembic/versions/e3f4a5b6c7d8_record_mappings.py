"""Record mappings: a mapping's kind, and its plan per source type

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # "catalogue": hardware models into Product Models and Vendors; "records": any records into the
    # target workspace's types, following a plan per source type.
    op.add_column("catalogue_mappings", sa.Column("kind", sa.String(), nullable=False, server_default="catalogue"))
    op.add_column("catalogue_mappings", sa.Column("plan", postgresql.JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("catalogue_mappings", "plan")
    op.drop_column("catalogue_mappings", "kind")
