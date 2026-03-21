"""add guillotine to leaguetype enum

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-03-21 14:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE leaguetype ADD VALUE IF NOT EXISTS 'guillotine'")


def downgrade() -> None:
    # Postgres doesn't support removing enum values; no-op
    pass
