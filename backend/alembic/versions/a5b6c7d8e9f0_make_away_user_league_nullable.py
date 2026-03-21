"""make away_user_league_id nullable for bye matchups

Revision ID: a5b6c7d8e9f0
Revises: 4d8cdff0cc10
Create Date: 2026-03-21 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "4d8cdff0cc10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("matchups", "away_user_league_id", nullable=True)


def downgrade() -> None:
    op.alter_column("matchups", "away_user_league_id", nullable=False)
