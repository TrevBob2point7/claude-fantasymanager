import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.core.database import get_db
from app.models import League, Matchup, PlatformAccount, PlayerADP, Roster, Standing, Transaction, UserLeague
from app.models.user import User
from app.platforms.registry import get_adapter
from app.schemas.league import (
    DiscoveredLeague,
    DiscoverRequest,
    LeagueDetailRead,
    LeagueRead,
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(League, UserLeague.team_name)
        .join(UserLeague, UserLeague.league_id == League.id)
        .where(UserLeague.user_id == current_user.id)
    )
    if season is not None:
        query = query.where(League.season == season)

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
    adp_format: str | None = Query(None),
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

    # Get standings with team names
    result = await db.execute(
        select(Standing, UserLeague.team_name)
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
        )
        for s, t_name in result.all()
    ]

    # Get user's roster with player info
    result = await db.execute(
        select(UserLeague).where(
            UserLeague.league_id == league_id,
            UserLeague.user_id == current_user.id,
        )
    )
    user_league = result.scalar_one_or_none()

    roster_entries = []
    if user_league:
        result = await db.execute(
            select(Roster)
            .options(selectinload(Roster.player))
            .where(Roster.user_league_id == user_league.id)
        )
        rosters = result.scalars().all()

        # Fetch ADP data for roster players using the most recent available season
        player_ids = [r.player_id for r in rosters if r.player_id]
        adp_by_player: dict = {}
        if player_ids:
            # Find the best ADP season: prefer league season, fall back to latest
            season_result = await db.execute(
                select(PlayerADP.season)
                .where(PlayerADP.player_id.in_(player_ids))
                .order_by(sa.func.abs(PlayerADP.season - league.season))
                .limit(1)
            )
            adp_season = season_result.scalar_one_or_none() or league.season

            adp_query = (
                select(PlayerADP.player_id, sa.func.min(PlayerADP.adp))
                .where(
                    PlayerADP.player_id.in_(player_ids),
                    PlayerADP.season == adp_season,
                )
            )
            if adp_format:
                adp_query = adp_query.where(PlayerADP.format == adp_format)
            adp_query = adp_query.group_by(PlayerADP.player_id)
            adp_result = await db.execute(adp_query)
            adp_by_player = dict(adp_result.all())

        roster_entries = [
            RosterEntryRead(
                id=r.id,
                player_id=r.player_id,
                player_name=r.player.full_name if r.player else "Unknown",
                position=r.player.position.value if r.player and r.player.position else None,
                team=r.player.team if r.player else None,
                slot=r.slot,
                adp=adp_by_player.get(r.player_id),
            )
            for r in rosters
        ]

    # Get recent matchups (last 3 weeks)
    result = await db.execute(
        select(Matchup)
        .where(Matchup.league_id == league_id)
        .order_by(Matchup.week.desc())
        .limit(20)
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
        created_at=league.created_at,
        standings=standings,
        roster=roster_entries,
        recent_matchups=recent_matchups,
        recent_transactions=recent_transactions,
    )
