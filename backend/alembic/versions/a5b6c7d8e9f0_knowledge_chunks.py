"""The written knowledge, indexed for Ask ARGUS (pgvector)

Only where the database has the pgvector extension: a Postgres without it keeps working, and the index
is created later, when it has it (the first indexing run creates it). See services/knowledge_index.py.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
"""
import sqlalchemy as sa
from alembic import op

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.services.knowledge_index import DDL
    bind = op.get_bind()
    if not bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).scalar():
        print("knowledge_chunks: this Postgres has no pgvector extension; Ask ARGUS works without the "
              "written-knowledge search until it does.")
        return
    for statement in DDL:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_index_runs")
    op.execute("DROP TABLE IF EXISTS knowledge_chunks")
