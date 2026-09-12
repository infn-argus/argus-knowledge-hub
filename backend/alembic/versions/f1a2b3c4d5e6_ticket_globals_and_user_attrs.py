"""ticket status/priority globals, global-value context scoping, issue state vocabulary

Revision ID: f1a2b3c4d5e6
Revises: e7c4a2f1b6d3
Create Date: 2026-09-17 00:00:00.000000

"""
import json
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e7c4a2f1b6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PRIORITY_OPTIONS = [
    {"id": "low", "value": "Low"},
    {"id": "medium", "value": "Medium"},
    {"id": "high", "value": "High"},
    {"id": "blocker", "value": "Blocker"},
    {"id": "critical", "value": "Critical"},
]

STATUS_OPTIONS = [
    {"id": "new", "value": "New", "responsible": "Help Desk (Queue)",
     "meaning": "Created and waiting to be picked up."},
    {"id": "in_progress", "value": "In Progress", "responsible": "Assigned Technician",
     "meaning": "Actively being analyzed or fixed."},
    {"id": "pending", "value": "Pending", "responsible": "External Party (User/Vendor)",
     "meaning": "Paused, waiting for an external action."},
    {"id": "resolved", "value": "Resolved", "responsible": "User (for verification)",
     "meaning": "The solution has been applied."},
    {"id": "closed", "value": "Closed", "responsible": "None (Archived)",
     "meaning": "Successfully resolved and locked."},
]

INSERT_SQL = sa.text("""
    INSERT INTO global_values
        (uid, workspace_id, name, key, type, applies_to, options, default_value,
         required, "unique", indexed, multi_value, read_only, visible, enabled,
         is_system_default, created_at, updated_at)
    VALUES
        (:uid, :workspace_id, :name, :key, 'enumeration', :applies_to, CAST(:options AS JSONB),
         :default_value, false, false, false, false, false, true, true, true, now(), now())
""")


def upgrade() -> None:
    op.add_column(
        'global_values',
        sa.Column('applies_to', sa.String(), nullable=False, server_default='objects'),
    )
    op.alter_column('global_values', 'applies_to', server_default=None)

    conn = op.get_bind()

    workspace_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM workspaces")).fetchall()]
    existing = {
        (row[0], row[1], row[2])
        for row in conn.execute(
            sa.text("SELECT workspace_id, applies_to, key FROM global_values")
        ).fetchall()
    }
    for wid in workspace_ids:
        if (wid, "tickets", "priority") not in existing:
            conn.execute(INSERT_SQL, {
                "uid": str(uuid.uuid4()), "workspace_id": wid, "name": "Priority", "key": "priority",
                "applies_to": "tickets", "options": json.dumps(PRIORITY_OPTIONS), "default_value": None,
            })
        if (wid, "tickets", "status") not in existing:
            conn.execute(INSERT_SQL, {
                "uid": str(uuid.uuid4()), "workspace_id": wid, "name": "Status", "key": "status",
                "applies_to": "tickets", "options": json.dumps(STATUS_OPTIONS), "default_value": "new",
            })

    # Ticket lifecycle vocabulary: "open" -> "new" (closed is unchanged).
    conn.execute(sa.text("UPDATE issues SET state = 'new' WHERE state = 'open'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE issues SET state = 'open' WHERE state = 'new'"))
    op.execute(sa.text(
        "DELETE FROM global_values WHERE applies_to = 'tickets' AND key IN ('priority', 'status') "
        "AND is_system_default = true"
    ))
    op.drop_column('global_values', 'applies_to')
