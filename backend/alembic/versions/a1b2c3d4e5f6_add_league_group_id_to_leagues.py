"""add league_group_id to leagues

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-03-08 12:00:00.000000

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add column
    op.add_column("leagues", sa.Column("league_group_id", sa.Uuid(), nullable=True))
    op.create_index("ix_leagues_league_group_id", "leagues", ["league_group_id"])

    # 2. Backfill
    conn = op.get_bind()

    # Fetch all leagues
    leagues = conn.execute(
        sa.text(
            "SELECT id, platform_type, platform_league_id, season, previous_league_id "
            "FROM leagues ORDER BY season ASC"
        )
    ).fetchall()

    # Track which leagues have been assigned a group
    assigned: dict[str, str] = {}  # league.id -> group_id

    for lg in leagues:
        if lg.id in assigned:
            continue

        # Walk the chain forward and backward to find all members
        chain = [lg]

        # Walk backward via previous_league_id
        current = lg
        while current.previous_league_id:
            # Find the previous league
            prev = None
            for candidate in leagues:
                if (
                    candidate.platform_type == current.platform_type
                    and candidate.platform_league_id == current.previous_league_id
                    and candidate.season < current.season
                ):
                    prev = candidate
                    break
            if prev is None or prev.id in assigned:
                break
            chain.append(prev)
            current = prev

        # Walk forward: find leagues whose previous_league_id points to any league in chain
        changed = True
        while changed:
            changed = False
            chain_ids = {c.platform_league_id for c in chain}
            for candidate in leagues:
                if candidate.id in assigned or candidate in chain:
                    continue
                if (
                    candidate.platform_type == chain[0].platform_type
                    and candidate.previous_league_id in chain_ids
                    and candidate not in chain
                ):
                    chain.append(candidate)
                    changed = True

        # Assign a single group_id to all leagues in the chain
        group_id = str(uuid.uuid4())
        for member in chain:
            assigned[member.id] = group_id
            conn.execute(
                sa.text("UPDATE leagues SET league_group_id = :gid WHERE id = :lid"),
                {"gid": group_id, "lid": member.id},
            )

    # Assign unique group_id to any unassigned leagues
    for lg in leagues:
        if lg.id not in assigned:
            group_id = str(uuid.uuid4())
            conn.execute(
                sa.text("UPDATE leagues SET league_group_id = :gid WHERE id = :lid"),
                {"gid": group_id, "lid": lg.id},
            )


def downgrade() -> None:
    op.drop_index("ix_leagues_league_group_id", table_name="leagues")
    op.drop_column("leagues", "league_group_id")
