"""Documents readable across workspaces, and speech models on an endpoint.

Two unrelated columns in one revision because they ship together: a global
workspace holding shared models and procedures is only useful if documents
can cross the boundary the way schemas and assets already do.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("llm_configs", sa.Column("asr_model", sa.String(), nullable=True))
    op.add_column("llm_configs", sa.Column("tts_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("llm_configs", "tts_model")
    op.drop_column("llm_configs", "asr_model")
    op.drop_column("documents", "is_global")
