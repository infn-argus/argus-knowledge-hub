"""Objects are shared only when flagged, not because their type is.

Revision ID: a8c3e5d7f912
Revises: d7f2a9c4e1b6
Create Date: 2026-09-23

An object of a global type used to be visible in every workspace. That is now
true only of an object flagged global (services/visibility). What lived in a
global workspace was meant to be shared, and is now flagged, as anything created
there is from here on; everything else stays with the workspace that owns it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a8c3e5d7f912"
down_revision: Union[str, None] = "d7f2a9c4e1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE assets SET is_global = true "
        "WHERE workspace_id IN (SELECT id FROM workspaces WHERE is_global)"
    )


def downgrade() -> None:
    # The flag cannot be told apart from one set by hand, so nothing is undone.
    pass
