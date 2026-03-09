"""add bestball league type

Revision ID: cbf3e746c1d7
Revises: 01cbebd14999
Create Date: 2026-03-08 21:10:55.657730

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'cbf3e746c1d7'
down_revision: Union[str, None] = '01cbebd14999'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE leaguetype ADD VALUE IF NOT EXISTS 'bestball'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values
    pass
