"""Sync NFL bye week data from ESPN Fantasy API."""

import logging

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team_bye_week import TeamByeWeek

logger = logging.getLogger(__name__)

ESPN_URL = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}?view=proTeamSchedules_wl"


async def sync_bye_weeks(db: AsyncSession, season: int) -> None:
    """Fetch bye weeks from ESPN and upsert into team_bye_weeks table."""
    url = ESPN_URL.format(season=season)

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

    pro_teams = data.get("settings", {}).get("proTeams", [])

    for team in pro_teams:
        bye_week = team.get("byeWeek", 0)
        abbrev = team.get("abbrev", "")

        # Skip FA entry (byeWeek == 0)
        if bye_week == 0:
            continue

        stmt = (
            pg_insert(TeamByeWeek)
            .values(
                season=season,
                team=abbrev.upper(),
                bye_week=bye_week,
            )
            .on_conflict_do_update(
                index_elements=["season", "team"],
                set_={"bye_week": bye_week},
            )
        )
        await db.execute(stmt)

    await db.flush()
    logger.info("Synced bye weeks for %d season (%d teams)", season, len(pro_teams))
