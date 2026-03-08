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

    # Build lookup maps for O(n) chain walking
    # (platform_type, platform_league_id) -> row (for backward walks)
    by_platform_id: dict[tuple, list] = {}
    # (platform_type, previous_league_id) -> [rows] (for forward walks)
    by_prev_id: dict[tuple, list] = {}
    for lg in leagues:
        by_platform_id.setdefault(
            (lg.platform_type, lg.platform_league_id), []
        ).append(lg)
        if lg.previous_league_id:
            by_prev_id.setdefault(
                (lg.platform_type, lg.previous_league_id), []
            ).append(lg)

    # Track which leagues have been assigned a group
    assigned: dict = {}  # league.id -> group_id (uuid.UUID)

    for lg in leagues:
        if lg.id in assigned:
            continue

        chain = [lg]

        # Walk backward via previous_league_id
        current = lg
        while current.previous_league_id:
            candidates = by_platform_id.get(
                (current.platform_type, current.previous_league_id), []
            )
            prev = next(
                (c for c in candidates if c.season < current.season),
                None,
            )
            if prev is None or prev.id in assigned:
                break
            chain.append(prev)
            current = prev

        # Walk forward: find leagues whose previous_league_id
        # points to any league in the chain
        queue = list(chain)
        seen = {lg.id for lg in chain}
        while queue:
            current = queue.pop()
            children = by_prev_id.get(
                (current.platform_type, current.platform_league_id), []
            )
            for child in children:
                if child.id not in seen and child.id not in assigned:
                    chain.append(child)
                    seen.add(child.id)
                    queue.append(child)

        # Assign a single group_id to all leagues in the chain
        group_id = uuid.uuid4()
        for member in chain:
            assigned[member.id] = group_id

    # Assign unique group_id to any unassigned leagues
    for lg in leagues:
        if lg.id not in assigned:
            assigned[lg.id] = uuid.uuid4()

    # Batch update all assignments
    if assigned:
        update_stmt = sa.text(
            "UPDATE leagues SET league_group_id = :gid WHERE id = :lid"
        )
        conn.execute(
            update_stmt,
            [{"gid": gid, "lid": lid} for lid, gid in assigned.items()],
        )


def downgrade() -> None:
    op.drop_index("ix_leagues_league_group_id", table_name="leagues")
    op.drop_column("leagues", "league_group_id")
