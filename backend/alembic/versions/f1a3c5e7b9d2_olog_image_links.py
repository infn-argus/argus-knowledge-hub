"""Olog entries: their images point at the files kept here

Entries imported before this kept Olog's own references (`![](attachment/<id>){width=…}`), which point
nowhere in ARGUS. Their files are here: the references are pointed at them, as new entries now are.

Revision ID: f1a3c5e7b9d2
Revises: e2f4a8c6d1b3
"""
import re

import sqlalchemy as sa
from alembic import op

revision = "f1a3c5e7b9d2"
down_revision = "e2f4a8c6d1b3"
branch_labels = None
depends_on = None

LINK = re.compile(r"\]\(attachment/([^)\s]+)\)(\{[^}]*\})?")


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT uid, body_markdown FROM document_revisions "
        "WHERE attributes->>'argus_source' = 'olog' AND body_markdown LIKE '%](attachment/%'")).all()
    for uid, body in rows:
        files = {backend_id.rsplit(":", 1)[-1]: att_uid for att_uid, backend_id in conn.execute(sa.text(
            "SELECT uid, backend_id FROM attachments WHERE document_revision_uid = :r AND backend_id LIKE 'olog:%'"),
            {"r": uid})}
        linked = LINK.sub(lambda m: f"](/v1/attachments/{files[m.group(1)]})" if m.group(1) in files else m.group(0),
                          body)
        if linked != body:
            conn.execute(sa.text("UPDATE document_revisions SET body_markdown = :b WHERE uid = :r"),
                         {"b": linked, "r": uid})


def downgrade() -> None:
    pass        # the links point at files that exist; nothing to undo
