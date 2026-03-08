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
    """Link two leagues into the same league group."""
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
    """Unlink leagues of a specific platform type from a league group."""
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
