"""Re-fetch playoff brackets and reapply consolation flags + bye matchups.

Run inside the backend container:
    python -m scripts.reapply_brackets

Fetches bracket data from each platform (lightweight API calls),
recomputes consolation pairings/round data, updates matchup flags,
and creates bye matchup rows for teams with first-round byes.
No full resync required.
"""

import asyncio
import logging
import math

from sqlalchemy import select

from app.core.database import async_session
from app.models.enums import PlatformType
from app.models.league import League
from app.models.matchup import Matchup
from app.models.platform_account import PlatformAccount
from app.models.user_league import UserLeague
from app.sync.engine import SyncEngine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _playoff_start_week(league: League) -> int | None:
    """Derive the first playoff week from league settings."""
    settings = league.settings_json or {}
    if league.platform_type == PlatformType.sleeper:
        start = settings.get("playoff_week_start")
        if start:
            return int(start)
        playoff_teams = settings.get("playoff_teams", 0)
        if not playoff_teams or int(playoff_teams) <= 0:
            return None
        num_rounds = math.ceil(math.log2(int(playoff_teams)))
        total_weeks = int(settings.get("leg", 17))
        return total_weeks - num_rounds + 1
    elif league.platform_type == PlatformType.mfl:
        last_reg = settings.get("lastRegularSeasonWeek")
        if last_reg:
            return int(last_reg) + 1
    return None


async def _create_bye_matchups(db, league: League) -> int:
    """Create bye matchup rows from stored bracket bye data."""
    bracket_data = (league.settings_json or {}).get("bracket_data", {})
    bye_ids = bracket_data.get("byes", {}).get("1", [])
    if not bye_ids:
        return 0

    start = _playoff_start_week(league)
    if not start:
        return 0

    # Get user_leagues keyed by platform_team_id
    result = await db.execute(
        select(UserLeague).where(UserLeague.league_id == league.id)
    )
    ul_by_pid = {
        ul.platform_team_id: ul for ul in result.scalars().all()
        if ul.platform_team_id
    }

    created = 0
    for bye_fid in bye_ids:
        bye_ul = ul_by_pid.get(bye_fid)
        if not bye_ul:
            continue
        existing = await db.execute(
            select(Matchup).where(
                Matchup.league_id == league.id,
                Matchup.week == start,
                Matchup.home_user_league_id == bye_ul.id,
                Matchup.away_user_league_id.is_(None),
            )
        )
        if not existing.scalar_one_or_none():
            db.add(Matchup(
                league_id=league.id,
                week=start,
                home_user_league_id=bye_ul.id,
                away_user_league_id=None,
                home_score=None,
                away_score=None,
                playoff_round=1,
                is_consolation=False,
            ))
            created += 1
    return created


async def main() -> None:
    async with async_session() as db:
        result = await db.execute(select(League))
        leagues = result.scalars().all()
        logger.info("Found %d leagues", len(leagues))

        # Pre-load credentials for MFL (needs auth)
        pa_result = await db.execute(select(PlatformAccount))
        accounts = pa_result.scalars().all()
        creds_by_user_platform = {
            (pa.user_id, pa.platform_type): pa.credentials_json
            for pa in accounts
        }

        engine = SyncEngine(db)
        updated = 0
        byes_created = 0

        for league in leagues:
            league_type = str(league.league_type) if league.league_type else None
            if league_type in ("bestball", "guillotine"):
                continue

            # Find credentials for this league's platform
            creds = None
            for (uid, ptype), c in creds_by_user_platform.items():
                if ptype == league.platform_type:
                    creds = c
                    break

            try:
                await engine.sync_playoff_brackets(
                    league, credentials_json=creds,
                )
                n = await _create_bye_matchups(db, league)
                byes_created += n
                updated += 1
                logger.info(
                    "Updated brackets for %s (%s)%s",
                    league.name, league.platform_type,
                    f" (+{n} bye matchups)" if n else "",
                )
            except Exception:
                logger.exception(
                    "Failed to update brackets for %s (%s)",
                    league.name, league.platform_type,
                )

        await db.commit()
        logger.info(
            "Done — updated %d / %d leagues, created %d bye matchups",
            updated, len(leagues), byes_created,
        )


if __name__ == "__main__":
    asyncio.run(main())
