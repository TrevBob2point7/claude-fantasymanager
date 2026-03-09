"""add playoff columns to matchups

Revision ID: 4d8cdff0cc10
Revises: cbf3e746c1d7
Create Date: 2026-03-09 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d8cdff0cc10"
down_revision: str | None = "cbf3e746c1d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matchups", sa.Column("playoff_round", sa.Integer(), nullable=True))
    op.add_column(
        "matchups",
        sa.Column("is_consolation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("matchups", "is_consolation")
    op.drop_column("matchups", "playoff_round")
