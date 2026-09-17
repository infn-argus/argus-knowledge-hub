"""backfill global icons

Icons migrated from schema-icon attachments (see b6d9e3f1a8c2) were all
stamped is_global=false regardless of their owning workspace — unlike
schemas, which already got is_global cascaded from a globally-shared
workspace at creation time. That mismatch is what let a type's icon
silently drop out the first time the type was copied to another workspace.

Revision ID: d7f2a9c4e1b6
Revises: b6d9e3f1a8c2
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd7f2a9c4e1b6'
down_revision: Union[str, None] = 'b6d9e3f1a8c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE icons SET is_global = true
        WHERE is_global = false
          AND workspace_id IN (SELECT id FROM workspaces WHERE is_global = true)
    """)


def downgrade() -> None:
    # Not reversible without knowing which rows this touched versus were
    # already true beforehand — same shape as every other is_global cascade
    # in this codebase (none of them ship a downgrade either).
    pass
