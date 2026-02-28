import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Position
from app.models.player import Player

logger = logging.getLogger(__name__)

VALID_POSITIONS = {p.value for p in Position}


async def get_or_create_player_by_sleeper_id(
    db: AsyncSession,
    sleeper_id: str,
    full_name: str = "Unknown Player",
    position: str | None = None,
    team: str | None = None,
) -> Player:
    """Get a player by sleeper_id, creating or updating the record."""
    pos_enum = None
    if position and position in VALID_POSITIONS:
        pos_enum = Position(position)

    result = await db.execute(select(Player).where(Player.sleeper_id == sleeper_id))
    player = result.scalar_one_or_none()
    if player is not None:
        # Update if we have better data than the stub
        if full_name != "Unknown Player" and player.full_name == "Unknown Player":
            player.full_name = full_name
            player.position = pos_enum
            player.team = team
            await db.flush()
        return player

    stmt = (
        pg_insert(Player)
        .values(
            sleeper_id=sleeper_id,
            full_name=full_name,
            position=pos_enum,
            team=team,
        )
        .on_conflict_do_update(
            index_elements=[Player.sleeper_id],
            set_={
                "full_name": full_name,
                "position": pos_enum,
                "team": team,
            },
        )
        .returning(Player)
    )
    result = await db.execute(stmt)
    player = result.scalar_one()
    await db.flush()
    return player
