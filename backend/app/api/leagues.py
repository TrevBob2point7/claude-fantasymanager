import contextlib
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.core.database import get_db
from app.models import League, Matchup, PlatformAccount, Roster, Standing, Transaction, UserLeague
from app.models.team_bye_week import TeamByeWeek
from app.models.user import User
from app.platforms.registry import get_adapter
from app.schemas.league import (
    DiscoveredLeague,
    DiscoverRequest,
    LeagueDetailRead,
    LeagueLinkRequest,
    LeagueRead,
    LeagueSeasonRead,
    LeagueSeasonsResponse,
    LeagueUnlinkRequest,
    MatchupPlayerRead,
    MatchupRead,
    MatchupSummaryRead,
    RosterEntryRead,
    StandingRead,
    TransactionRead,
)
from app.sync.engine import SyncEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leagues", tags=["leagues"])


@router.post("/discover", response_model=list[DiscoveredLeague])
async def discover_leagues(
    body: DiscoverRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify platform account belongs to user
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.id == body.platform_account_id,
            PlatformAccount.user_id == current_user.id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform account not found",
        )

    season = body.season or datetime.now(UTC).year

    try:
        adapter = get_adapter(account.platform_type)
        platform_user_id = account.platform_user_id

        # Resolve username to numeric user ID if needed
        if account.platform_username and (
            not platform_user_id or not platform_user_id.isdigit()
        ):
            user_info = await adapter.get_user(account.platform_username)
            platform_user_id = user_info.user_id
            account.platform_user_id = platform_user_id
            await db.commit()

        if not platform_user_id:
            raise ValueError("No platform user ID or username available")

        platform_leagues = await adapter.get_leagues(platform_user_id, season)
    except Exception as e:
        logger.exception("Failed to fetch leagues from platform")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch leagues from platform",
        ) from e

    # Check which leagues are already linked
    result = await db.execute(
        select(League.platform_league_id).where(
            League.platform_type == account.platform_type,
            League.season == season,
        )
    )
    linked_ids = set(result.scalars().all())

    return [
        DiscoveredLeague(
            platform_league_id=pl.league_id,
            name=pl.name,
            season=pl.season,
            roster_size=pl.roster_size,
            scoring_type=pl.scoring_type,
            already_linked=pl.league_id in linked_ids,
        )
        for pl in platform_leagues
    ]


@router.get("", response_model=list[LeagueRead])
async def list_leagues(
    season: int | None = Query(None),
    latest: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(League, UserLeague.team_name)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(UserLeague.user_id == current_user.id)
    )

    if latest:
        # Return the most recent season per league group using DISTINCT ON.
        # COALESCE with id so NULL league_group_id leagues don't collapse.
        group_key = sa_func.coalesce(League.league_group_id, League.id)
        query = (
            select(League, UserLeague.team_name)
            .join(UserLeague, UserLeague.league_id == League.id)
            .where(UserLeague.user_id == current_user.id)
            .distinct(group_key)
            .order_by(group_key, League.season.desc())
        )
    elif season is not None:
        query = query.where(League.season == season)
    else:
        effective_season = datetime.now(UTC).year
        query = query.where(League.season == effective_season)

    result = await db.execute(query)
    rows = result.all()

    return [
        LeagueRead(
            id=league.id,
            platform_type=league.platform_type,
            platform_league_id=league.platform_league_id,
            name=league.name,
            season=league.season,
            roster_size=league.roster_size,
            scoring_type=league.scoring_type,
            league_type=league.league_type,
            team_name=team_name,
            created_at=league.created_at,
        )
        for league, team_name in rows
    ]


@router.get("/{league_id}", response_model=LeagueDetailRead)
async def get_league_detail(
    league_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify user has access to this league
    result = await db.execute(
        select(League, UserLeague.team_name)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(League.id == league_id, UserLeague.user_id == current_user.id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="League not found",
        )
    league, team_name = row

    # Get user's user_league to identify "me"
    result = await db.execute(
        select(UserLeague).where(
            UserLeague.league_id == league_id,
            UserLeague.user_id == current_user.id,
        )
    )
    user_league = result.scalar_one_or_none()
    user_league_id = user_league.id if user_league else None

    # Get standings with team names
    result = await db.execute(
        select(Standing, UserLeague.team_name, UserLeague.id)
        .join(UserLeague, UserLeague.id == Standing.user_league_id)
        .where(Standing.league_id == league_id)
        .order_by(Standing.rank)
    )
    standings = [
        StandingRead(
            id=s.id,
            team_name=t_name,
            wins=s.wins,
            losses=s.losses,
            ties=s.ties,
            points_for=s.points_for,
            points_against=s.points_against,
            rank=s.rank,
            is_me=ul_id == user_league_id,
        )
        for s, t_name, ul_id in result.all()
    ]

    # Build bye week lookup for this season
    bye_result = await db.execute(
        select(TeamByeWeek).where(TeamByeWeek.season == league.season)
    )
    bye_map = {bw.team: bw.bye_week for bw in bye_result.scalars().all()}

    roster_entries = []
    if user_league:
        result = await db.execute(
            select(Roster)
            .options(selectinload(Roster.player))
            .where(Roster.user_league_id == user_league.id)
        )
        rosters = result.scalars().all()
        roster_entries = [
            RosterEntryRead(
                id=r.id,
                player_id=r.player_id,
                player_name=r.player.full_name if r.player else "Unknown",
                position=r.player.position.value if r.player and r.player.position else None,
                team=r.player.team if r.player else None,
                slot=r.slot,
                status=r.player.status.value if r.player and r.player.status else None,
                bye_week=bye_map.get(r.player.team) if r.player and r.player.team else None,
            )
            for r in rosters
        ]

    # Get all matchups for the league
    result = await db.execute(
        select(Matchup)
        .where(Matchup.league_id == league_id)
        .order_by(Matchup.week.asc())
    )
    matchups_raw = result.scalars().all()

    # Get user_league names for matchup display and champion lookup
    result = await db.execute(select(UserLeague).where(UserLeague.league_id == league_id))
    all_uls_list = result.scalars().all()
    all_uls = {ul.id: ul.team_name for ul in all_uls_list}

    recent_matchups = [
        MatchupRead(
            id=m.id,
            week=m.week,
            home_team_name=all_uls.get(m.home_user_league_id),
            away_team_name=all_uls.get(m.away_user_league_id),
            home_score=m.home_score,
            away_score=m.away_score,
            is_user_matchup=(
                m.home_user_league_id == user_league_id
                or m.away_user_league_id == user_league_id
            ),
            home_starters=[
                MatchupPlayerRead(**p) for p in m.home_starters_json
            ] if m.home_starters_json else None,
            away_starters=[
                MatchupPlayerRead(**p) for p in m.away_starters_json
            ] if m.away_starters_json else None,
            playoff_round=m.playoff_round,
            is_consolation=m.is_consolation,
        )
        for m in matchups_raw
    ]

    # Get recent transactions
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.player))
        .where(Transaction.league_id == league_id)
        .order_by(Transaction.timestamp.desc())
        .limit(20)
    )
    txns_raw = result.scalars().all()

    recent_transactions = [
        TransactionRead(
            id=t.id,
            type=t.type,
            player_name=t.player.full_name if t.player else None,
            from_team_name=all_uls.get(t.from_user_league_id),
            to_team_name=all_uls.get(t.to_user_league_id),
            timestamp=t.timestamp,
        )
        for t in txns_raw
    ]

    current_week = (
        league.settings_json.get("leg") if league.settings_json else None
    )

    # Resolve champion team name from stored bracket data
    champion_team_name: str | None = None
    bracket_data = (league.settings_json or {}).get("bracket_data", {})
    champion_fid = bracket_data.get("champion_franchise_id")
    if champion_fid:
        for ul in all_uls_list:
            if ul.platform_team_id == champion_fid:
                champion_team_name = ul.team_name
                break

    return LeagueDetailRead(
        id=league.id,
        platform_type=league.platform_type,
        platform_league_id=league.platform_league_id,
        name=league.name,
        season=league.season,
        roster_size=league.roster_size,
        scoring_type=league.scoring_type,
        league_type=league.league_type,
        team_name=team_name,
        current_week=current_week,
        champion_team_name=champion_team_name,
        created_at=league.created_at,
        standings=standings,
        roster=roster_entries,
        recent_matchups=recent_matchups,
        recent_transactions=recent_transactions,
    )


@router.get("/{league_id}/seasons", response_model=LeagueSeasonsResponse)
async def get_league_seasons(
    league_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all seasons in the same league group."""
    # Verify user has access
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

    if league.league_group_id:
        # Get all seasons in the group
        result = await db.execute(
            select(League)
            .where(League.league_group_id == league.league_group_id)
            .order_by(League.season.desc())
        )
        group_leagues = result.scalars().all()
        seasons = [
            LeagueSeasonRead(season=lg.season, league_id=lg.id, platform_type=lg.platform_type)
            for lg in group_leagues
        ]
    else:
        seasons = [
            LeagueSeasonRead(
                season=league.season, league_id=league.id, platform_type=league.platform_type
            )
        ]

    return LeagueSeasonsResponse(seasons=seasons)


@router.post("/{league_id}/link", response_model=LeagueSeasonsResponse)
async def link_leagues(
    league_id: UUID,
    body: LeagueLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Link two leagues into the same league group.

    Note: league_group_id lives on the shared League row, so linking
    affects all users who belong to either league.  This is intentional —
    grouping reflects a factual "same league" relationship, not a
    per-user preference.  Re-evaluate if user-scoped grouping is needed.
    """
    # Verify both leagues belong to the requesting user
    result = await db.execute(
        select(League)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(League.id == league_id, UserLeague.user_id == current_user.id)
    )
    source_league = result.scalar_one_or_none()
    if source_league is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="League not found",
        )

    result = await db.execute(
        select(League)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(League.id == body.target_league_id, UserLeague.user_id == current_user.id)
    )
    target_league = result.scalar_one_or_none()
    if target_league is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target league not found",
        )

    # Ensure source has a league_group_id
    if not source_league.league_group_id:
        source_league.league_group_id = uuid4()

    source_group_id = source_league.league_group_id

    # Update all leagues in the target's group to use the source's group_id
    if target_league.league_group_id:
        await db.execute(
            update(League)
            .where(League.league_group_id == target_league.league_group_id)
            .values(league_group_id=source_group_id)
        )
    else:
        target_league.league_group_id = source_group_id

    await db.commit()

    # Return the updated season list
    result = await db.execute(
        select(League)
        .where(League.league_group_id == source_group_id)
        .order_by(League.season.desc())
    )
    group_leagues = result.scalars().all()
    seasons = [
        LeagueSeasonRead(season=lg.season, league_id=lg.id, platform_type=lg.platform_type)
        for lg in group_leagues
    ]

    return LeagueSeasonsResponse(seasons=seasons)


@router.post("/{league_id}/unlink", response_model=LeagueSeasonsResponse)
async def unlink_leagues(
    league_id: UUID,
    body: LeagueUnlinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unlink leagues of a specific platform type from a league group.

    Note: league_group_id lives on the shared League row, so unlinking
    affects all users who belong to the affected leagues.  This is
    intentional — grouping reflects a factual "same league" relationship,
    not a per-user preference.  Re-evaluate if user-scoped grouping is
    needed.
    """
    # Verify the league belongs to the requesting user
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

    if not league.league_group_id:
        # Nothing to unlink
        return LeagueSeasonsResponse(
            seasons=[
                LeagueSeasonRead(
                    season=league.season, league_id=league.id, platform_type=league.platform_type
                )
            ]
        )

    original_group_id = league.league_group_id

    # Assign a new group_id to leagues in this group with the specified platform_type
    new_group_id = uuid4()
    await db.execute(
        update(League)
        .where(
            League.league_group_id == original_group_id,
            League.platform_type == body.platform_type,
        )
        .values(league_group_id=new_group_id)
    )

    await db.commit()

    # Refresh the league to get updated group_id
    await db.refresh(league)

    # Return seasons for the original league's (possibly updated) group
    result = await db.execute(
        select(League)
        .where(League.league_group_id == league.league_group_id)
        .order_by(League.season.desc())
    )
    group_leagues = result.scalars().all()
    seasons = [
        LeagueSeasonRead(season=lg.season, league_id=lg.id, platform_type=lg.platform_type)
        for lg in group_leagues
    ]

    return LeagueSeasonsResponse(seasons=seasons)


# ---------------------------------------------------------------------------
# Lazy-fetch endpoints: matchups & transactions
# ---------------------------------------------------------------------------

async def _get_league_and_account(
    league_id: UUID, user_id: UUID, db: AsyncSession
) -> tuple[League, UserLeague, PlatformAccount]:
    """Verify user access and find platform account for a league."""
    result = await db.execute(
        select(League, UserLeague)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(League.id == league_id, UserLeague.user_id == user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    league, user_league = row

    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.user_id == user_id,
            PlatformAccount.platform_type == league.platform_type,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No platform account found for this league",
        )
    return league, user_league, account


def _current_week(league: League) -> int:
    """Get the current week from league settings.

    Sleeper uses ``leg`` for the current week.
    MFL uses ``lastRegularSeasonWeek`` / ``endWeek`` (no per-week cursor).
    Falls back to 17 for completed seasons, 1 otherwise.
    """
    settings = league.settings_json or {}
    # Sleeper stores the current "leg"
    leg = settings.get("leg")
    if leg:
        return int(leg)
    # MFL: use endWeek (includes playoffs) or lastRegularSeasonWeek
    end_week = settings.get("endWeek")
    if end_week:
        return int(end_week)
    last_reg = settings.get("lastRegularSeasonWeek")
    if last_reg:
        return int(last_reg)
    # Default: assume full season for completed leagues
    return 17


@router.get("/{league_id}/matchups/summary", response_model=list[MatchupSummaryRead])
async def get_matchup_summary(
    league_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all matchup summaries (scores + teams, no starters) for a league.

    Fetches from platform on-demand if no matchups are cached.
    Completed weeks are never re-fetched.
    """
    league, user_league, account = await _get_league_and_account(
        league_id, current_user.id, db
    )

    cur_week = _current_week(league)
    season_finished = league.season < datetime.now(UTC).year

    # Check what's already cached
    result = await db.execute(
        select(Matchup).where(Matchup.league_id == league_id).order_by(Matchup.week.asc())
    )
    cached = result.scalars().all()
    cached_weeks = {m.week for m in cached}

    # Determine which weeks need fetching
    weeks_to_fetch: list[int] = []
    end_week = int((league.settings_json or {}).get("endWeek", 0) or 0) or 17
    week_range = range(1, end_week + 1) if season_finished else range(1, min(cur_week + 1, 19))
    for w in week_range:
        if w not in cached_weeks:
            weeks_to_fetch.append(w)
        elif not season_finished and w == cur_week:
            # Current week may have updated scores — re-fetch
            weeks_to_fetch.append(w)

    if weeks_to_fetch:
        adapter = get_adapter(
            account.platform_type,
            credentials_json=account.credentials_json,
            year=league.season,
        )
        players_map: dict[str, dict] = {}
        with contextlib.suppress(Exception):
            players_map = await adapter.get_players_map()

        engine = SyncEngine(db)
        for w in weeks_to_fetch:
            try:
                await engine.sync_matchups(
                    league, current_user.id, w,
                    players_map=players_map, adapter=adapter,
                )
            except Exception:
                logger.exception("Failed to fetch matchups for week %d", w)

        await db.commit()

        # Re-query
        result = await db.execute(
            select(Matchup).where(Matchup.league_id == league_id).order_by(Matchup.week.asc())
        )
        cached = result.scalars().all()

    # Build name lookup
    result = await db.execute(select(UserLeague).where(UserLeague.league_id == league_id))
    all_uls = {ul.id: ul.team_name for ul in result.scalars().all()}

    return [
        MatchupSummaryRead(
            id=m.id,
            week=m.week,
            home_team_name=all_uls.get(m.home_user_league_id),
            away_team_name=all_uls.get(m.away_user_league_id),
            home_score=m.home_score,
            away_score=m.away_score,
            is_user_matchup=(
                m.home_user_league_id == user_league.id
                or m.away_user_league_id == user_league.id
            ),
            playoff_round=m.playoff_round,
            is_consolation=m.is_consolation,
        )
        for m in cached
    ]


@router.get("/{league_id}/matchups/{week}", response_model=list[MatchupRead])
async def get_matchup_detail(
    league_id: UUID,
    week: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return full matchup detail (with starters) for a specific week.

    Fetches from platform if not cached or if it's the current week.
    """
    league, user_league, account = await _get_league_and_account(
        league_id, current_user.id, db
    )

    cur_week = _current_week(league)
    season_finished = league.season < datetime.now(UTC).year

    # Check cache
    result = await db.execute(
        select(Matchup).where(Matchup.league_id == league_id, Matchup.week == week)
    )
    cached = result.scalars().all()

    # Fetch if missing (even finished seasons) or active season current/future week
    needs_fetch = not cached or (not season_finished and week >= cur_week)
    if needs_fetch:
        adapter = get_adapter(
            account.platform_type,
            credentials_json=account.credentials_json,
            year=league.season,
        )
        players_map: dict[str, dict] = {}
        with contextlib.suppress(Exception):
            players_map = await adapter.get_players_map()

        engine = SyncEngine(db)
        try:
            await engine.sync_matchups(
                league, current_user.id, week,
                players_map=players_map, adapter=adapter,
            )
            await db.commit()
        except Exception:
            logger.exception("Failed to fetch matchup detail for week %d", week)

        result = await db.execute(
            select(Matchup).where(Matchup.league_id == league_id, Matchup.week == week)
        )
        cached = result.scalars().all()

    # Build name lookup
    result = await db.execute(select(UserLeague).where(UserLeague.league_id == league_id))
    all_uls = {ul.id: ul.team_name for ul in result.scalars().all()}

    return [
        MatchupRead(
            id=m.id,
            week=m.week,
            home_team_name=all_uls.get(m.home_user_league_id),
            away_team_name=all_uls.get(m.away_user_league_id),
            home_score=m.home_score,
            away_score=m.away_score,
            is_user_matchup=(
                m.home_user_league_id == user_league.id
                or m.away_user_league_id == user_league.id
            ),
            home_starters=[
                MatchupPlayerRead(**p) for p in m.home_starters_json
            ] if m.home_starters_json else None,
            away_starters=[
                MatchupPlayerRead(**p) for p in m.away_starters_json
            ] if m.away_starters_json else None,
            playoff_round=m.playoff_round,
            is_consolation=m.is_consolation,
        )
        for m in cached
    ]


@router.get("/{league_id}/transactions", response_model=list[TransactionRead])
async def get_league_transactions(
    league_id: UUID,
    week: int | None = Query(None, ge=1, le=18),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return transactions for a league, optionally filtered by week.

    Fetches from platform if not cached or if it's the current week.
    """
    league, _user_league, account = await _get_league_and_account(
        league_id, current_user.id, db
    )

    cur_week = _current_week(league)
    season_finished = league.season < datetime.now(UTC).year

    # Check cache
    tx_query = select(Transaction).where(Transaction.league_id == league_id)
    if week is not None:
        tx_query = tx_query.where(Transaction.week == week)
    tx_query = tx_query.order_by(Transaction.timestamp.desc())

    result = await db.execute(tx_query.options(selectinload(Transaction.player)))
    cached = result.scalars().all()

    # Fetch if missing (even finished seasons) or active season current/future week
    needs_fetch = False
    if not cached:
        needs_fetch = True
    elif not season_finished:
        if week is not None and week >= cur_week:
            needs_fetch = True

    if needs_fetch:
        adapter = get_adapter(
            account.platform_type,
            credentials_json=account.credentials_json,
            year=league.season,
        )
        players_map: dict[str, dict] = {}
        with contextlib.suppress(Exception):
            players_map = await adapter.get_players_map()

        engine = SyncEngine(db)
        end_week = int((league.settings_json or {}).get("endWeek", 0) or 0) or 17
        if week:
            weeks_to_fetch = [week]
        elif season_finished:
            weeks_to_fetch = list(range(1, end_week + 1))
        else:
            weeks_to_fetch = list(range(1, min(cur_week + 1, 19)))
        for w in weeks_to_fetch:
            try:
                await engine.sync_transactions(
                    league, current_user.id, w,
                    players_map=players_map, adapter=adapter,
                )
            except Exception:
                logger.exception("Failed to fetch transactions for week %d", w)

        await db.commit()

        result = await db.execute(tx_query.options(selectinload(Transaction.player)))
        cached = result.scalars().all()

    # Build name lookup
    result = await db.execute(select(UserLeague).where(UserLeague.league_id == league_id))
    all_uls = {ul.id: ul.team_name for ul in result.scalars().all()}

    return [
        TransactionRead(
            id=t.id,
            type=t.type,
            player_name=t.player.full_name if t.player else None,
            from_team_name=all_uls.get(t.from_user_league_id),
            to_team_name=all_uls.get(t.to_user_league_id),
            timestamp=t.timestamp,
        )
        for t in cached
    ]
