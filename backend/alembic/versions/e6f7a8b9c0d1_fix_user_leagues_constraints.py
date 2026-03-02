"""fix user_leagues constraints for all-teams sync

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-03-02 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Truncate dependent tables first (data will be re-synced correctly)
    op.execute("TRUNCATE TABLE matchups CASCADE")
    op.execute("TRUNCATE TABLE rosters CASCADE")
    op.execute("TRUNCATE TABLE standings CASCADE")
    op.execute("TRUNCATE TABLE transactions CASCADE")
    op.execute("TRUNCATE TABLE user_leagues CASCADE")

    # Drop old unique constraint
    op.drop_constraint("user_leagues_user_id_league_id_key", "user_leagues", type_="unique")

    # Make user_id nullable (external teams get NULL)
    op.alter_column("user_leagues", "user_id", existing_type=sa.Uuid(), nullable=True)

    # Make platform_team_id NOT NULL
    op.alter_column(
        "user_leagues", "platform_team_id", existing_type=sa.String(100), nullable=False
    )

    # Add new unique constraint on (league_id, platform_team_id)
    op.create_unique_constraint(
        "user_leagues_league_id_platform_team_id_key",
        "user_leagues",
        ["league_id", "platform_team_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "user_leagues_league_id_platform_team_id_key", "user_leagues", type_="unique"
    )
    op.alter_column(
        "user_leagues", "platform_team_id", existing_type=sa.String(100), nullable=True
    )
    op.alter_column("user_leagues", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.create_unique_constraint(
        "user_leagues_user_id_league_id_key", "user_leagues", ["user_id", "league_id"]
    )
