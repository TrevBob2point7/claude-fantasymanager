import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
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
    LeagueRead,
    LeagueSeasonRead,
    LeagueSeasonsResponse,
    MatchupPlayerRead,
    MatchupRead,
    RosterEntryRead,
    StandingRead,
    TransactionRead,
)

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
        # Only return leagues whose platform_league_id is NOT referenced
        # as another league's previous_league_id (i.e. the head of each chain)
        successor_ids = select(League.previous_league_id).where(
            League.previous_league_id.isnot(None)
        )
        query = query.where(League.platform_league_id.notin_(successor_ids))
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

    # Get user_league names for matchup display
    result = await db.execute(select(UserLeague).where(UserLeague.league_id == league_id))
    all_uls = {ul.id: ul.team_name for ul in result.scalars().all()}

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
    """Walk the previous_league_id chain to find all seasons for a league."""
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

    seasons = [LeagueSeasonRead(season=league.season, league_id=league.id)]

    # Walk backward via previous_league_id
    current = league
    while current.previous_league_id:
        result = await db.execute(
            select(League)
            .join(UserLeague, UserLeague.league_id == League.id)
            .where(
                League.platform_type == league.platform_type,
                League.platform_league_id == current.previous_league_id,
                UserLeague.user_id == current_user.id,
            )
        )
        prev = result.scalar_one_or_none()
        if prev is None:
            break
        seasons.append(LeagueSeasonRead(season=prev.season, league_id=prev.id))
        current = prev

    # Walk forward — find leagues whose previous_league_id points to us
    current = league
    while True:
        result = await db.execute(
            select(League)
            .join(UserLeague, UserLeague.league_id == League.id)
            .where(
                League.platform_type == league.platform_type,
                League.previous_league_id == current.platform_league_id,
                UserLeague.user_id == current_user.id,
            )
        )
        nxt = result.scalar_one_or_none()
        if nxt is None:
            break
        seasons.append(LeagueSeasonRead(season=nxt.season, league_id=nxt.id))
        current = nxt

    # Sort by season descending
    seasons.sort(key=lambda s: s.season, reverse=True)

    return LeagueSeasonsResponse(seasons=seasons)
