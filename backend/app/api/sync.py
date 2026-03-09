import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.core.database import async_session, get_db
from app.models import League, PlatformAccount, SyncLog, UserLeague
from app.models.user import User
from app.platforms.registry import get_adapter
from app.schemas.sync import SyncLogRead
from app.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


async def _sync_stream(
    user_id: UUID, account_id: UUID, season: int
) -> AsyncGenerator[str, None]:
    """Stream SSE events as sync progresses.

    Only syncs league metadata, user_leagues, rosters, and standings.
    Matchups and transactions are fetched lazily when the user views them.
    """
    async with async_session() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Account not found'})}\n\n"
            return

        synced: list[str] = []
        errors: list[str] = []

        def progress(message: str) -> str:
            return f"data: {json.dumps({'type': 'progress', 'message': message})}\n\n"

        engine = SyncEngine(db)

        # 1. Sync leagues
        yield progress("Discovering leagues...")
        try:
            leagues = await engine.sync_leagues(user_id, account, season)
            synced.append("leagues")
            yield progress(f"Found {len(leagues)} league{'s' if len(leagues) != 1 else ''}")
        except Exception as e:
            errors.append(f"leagues: {e}")
            yield f"data: {json.dumps({'type': 'done', 'synced': synced, 'errors': errors})}\n\n"
            return

        # 2. Create shared adapter and fetch player data
        yield progress("Loading player data...")
        credentials_json = account.credentials_json
        adapter = get_adapter(account.platform_type, credentials_json=credentials_json)
        players_map: dict[str, dict] = {}
        try:
            players_map = await adapter.get_players_map()
        except Exception:
            logger.warning("Could not fetch players map, will use stubs")

        # 3. Sync each league — rosters + standings only
        for i, league in enumerate(leagues, 1):
            league_label = f"({i}/{len(leagues)}) {league.name}"
            yield progress(f"Syncing {league_label}...")

            try:
                await engine._sync_user_leagues(
                    league, user_id, account.platform_user_id,
                    credentials_json=credentials_json, adapter=adapter,
                )
            except Exception as e:
                errors.append(f"user_leagues({league.name}): {e}")

            try:
                await engine.sync_rosters(
                    league, user_id, players_map=players_map,
                    credentials_json=credentials_json, adapter=adapter,
                )
            except Exception as e:
                errors.append(f"rosters({league.name}): {e}")

            yield progress(f"Syncing {league_label} - standings...")
            try:
                await engine.sync_standings(
                    league, user_id, credentials_json=credentials_json, adapter=adapter,
                )
            except Exception as e:
                errors.append(f"standings({league.name}): {e}")

            yield progress(f"Synced {league_label}")

        # 4. Historical seasons
        hist_leagues = [lg for lg in leagues if lg.previous_league_id]
        if hist_leagues:
            yield progress("Syncing historical seasons...")
            for league in hist_leagues:
                try:
                    await engine.sync_historical_seasons(
                        league, user_id, account,
                        players_map=players_map, adapter=adapter,
                    )
                except Exception as e:
                    errors.append(f"historical({league.name}): {e}")

        # 5. Bye weeks
        try:
            from app.models.team_bye_week import TeamByeWeek
            existing = await db.execute(
                select(TeamByeWeek).where(TeamByeWeek.season == season).limit(1)
            )
            if existing.scalar_one_or_none() is None:
                await engine.sync_bye_weeks(season)
        except Exception:
            pass

        await db.commit()
        done_payload = {"type": "done", "synced": list(set(synced)), "errors": errors}
        yield f"data: {json.dumps(done_payload)}\n\n"


async def _league_sync_stream(
    user_id: UUID, league_id: UUID, account_id: UUID,
) -> AsyncGenerator[str, None]:
    """Stream SSE events for syncing a single league."""
    async with async_session() as db:
        result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Account not found'})}\n\n"
            return

        result = await db.execute(select(League).where(League.id == league_id))
        league = result.scalar_one_or_none()
        if league is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'League not found'})}\n\n"
            return

        synced: list[str] = []
        errors: list[str] = []

        def progress(message: str) -> str:
            return f"data: {json.dumps({'type': 'progress', 'message': message})}\n\n"

        engine = SyncEngine(db)
        credentials_json = account.credentials_json
        adapter = get_adapter(
            account.platform_type,
            credentials_json=credentials_json,
            year=league.season,
        )

        yield progress(f"Syncing {league.name}...")

        # Refresh league metadata if missing
        try:
            platform_league = await adapter.get_league(
                league.platform_league_id,
            )
            if platform_league.scoring_type:
                league.scoring_type = platform_league.scoring_type
            if platform_league.league_type:
                league.league_type = platform_league.league_type
            if platform_league.roster_size:
                league.roster_size = platform_league.roster_size
            if platform_league.name:
                league.name = platform_league.name
            # Merge settings
            settings = {**(league.settings_json or {})}
            if platform_league.settings:
                settings.update(platform_league.settings)
            if platform_league.roster_positions is not None:
                settings["roster_positions"] = platform_league.roster_positions
            league.settings_json = settings
            await db.flush()
        except Exception as e:
            errors.append(f"league_metadata: {e}")

        # Fetch player data
        players_map: dict[str, dict] = {}
        try:
            players_map = await adapter.get_players_map()
        except Exception:
            logger.warning("Could not fetch players map, will use stubs")

        try:
            await engine._sync_user_leagues(
                league, user_id, account.platform_user_id,
                credentials_json=credentials_json, adapter=adapter,
            )
        except Exception as e:
            errors.append(f"user_leagues: {e}")

        yield progress("Syncing rosters...")
        try:
            await engine.sync_rosters(
                league, user_id, players_map=players_map,
                credentials_json=credentials_json, adapter=adapter,
            )
        except Exception as e:
            errors.append(f"rosters: {e}")

        yield progress("Syncing standings...")
        try:
            await engine.sync_standings(
                league, user_id, credentials_json=credentials_json, adapter=adapter,
            )
        except Exception as e:
            errors.append(f"standings: {e}")

        # Sync historical seasons (metadata + standings only)
        if league.previous_league_id or account.platform_type == "mfl":
            yield progress("Discovering historical seasons...")
            try:
                await engine.sync_historical_seasons(
                    league, user_id, account,
                    players_map=players_map, adapter=adapter,
                )
                synced.append("historical_seasons")
            except Exception as e:
                errors.append(f"historical: {e}")

        await db.commit()
        synced.extend(["rosters", "standings"])
        yield progress(f"Synced {league.name}")
        yield f"data: {json.dumps({'type': 'done', 'synced': synced, 'errors': errors})}\n\n"


@router.post("/{account_id}")
async def trigger_sync(
    account_id: UUID,
    season: int = Query(2025, ge=2000, le=2100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.id == account_id,
            PlatformAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform account not found",
        )

    return StreamingResponse(
        _sync_stream(current_user.id, account_id, season),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/league/{league_id}")
async def trigger_league_sync(
    league_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync a single league's rosters and standings."""
    # Verify user has access to this league
    result = await db.execute(
        select(League)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(League.id == league_id, UserLeague.user_id == current_user.id)
    )
    league = result.scalar_one_or_none()
    if league is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="League not found",
        )

    # Find the platform account for this league's platform
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.user_id == current_user.id,
            PlatformAccount.platform_type == league.platform_type,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No platform account found for this league",
        )

    return StreamingResponse(
        _league_sync_stream(current_user.id, league_id, account.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/log", response_model=list[SyncLogRead])
async def get_sync_log(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.user_id == current_user.id)
        .order_by(SyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
