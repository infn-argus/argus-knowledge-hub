"""An import may have no credential: a public repository needs none.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("import_configs", "encrypted_secret", existing_type=sa.String(),
                    nullable=True)


def downgrade() -> None:
    # Anything saved without a credential has to gain one before the column
    # can be required again; an empty string is not a credential, but it is
    # reversible and a lost token is not.
    op.execute("UPDATE import_configs SET encrypted_secret = '' WHERE encrypted_secret IS NULL")
    op.alter_column("import_configs", "encrypted_secret", existing_type=sa.String(),
                    nullable=False)
