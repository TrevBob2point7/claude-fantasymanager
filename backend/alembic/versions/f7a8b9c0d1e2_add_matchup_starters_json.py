"""add matchup starters JSON columns

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-02 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matchups", sa.Column("home_starters_json", sa.JSON(), nullable=True))
    op.add_column("matchups", sa.Column("away_starters_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("matchups", "away_starters_json")
    op.drop_column("matchups", "home_starters_json")
