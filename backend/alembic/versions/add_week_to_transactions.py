"""add week to transactions

Revision ID: a1b2c3d4e5f6
Revises: 79e69dc8a36c
Create Date: 2026-02-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "79e69dc8a36c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("week", sa.Integer(), nullable=True))
    op.execute("UPDATE transactions SET week = 0 WHERE week IS NULL")
    op.alter_column("transactions", "week", nullable=False)


def downgrade() -> None:
    op.drop_column("transactions", "week")
