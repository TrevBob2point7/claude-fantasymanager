"""Integration tests for the sync engine."""

from unittest.mock import AsyncMock, patch

import pytest
from app.models import (
    League,
    Matchup,
    PlatformAccount,
    PlatformType,
    Standing,
    SyncLog,
    SyncStatus,
    UserLeague,
)
from app.models.user import User
from app.platforms.schemas import (
    PlatformLeague,
    PlatformMatchup,
    PlatformRosterEntry,
    PlatformUser,
)
from app.sync.engine import SyncEngine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import UserFactory


async def _create_test_user(db: AsyncSession) -> User:
    """Create a test user in the database."""
    user = UserFactory.build()
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_platform_account(
    db: AsyncSession, user: User
) -> PlatformAccount:
    """Create a platform account for testing."""
    account = PlatformAccount(
        user_id=user.id,
        platform_type=PlatformType.sleeper,
        platform_username="testuser",
        platform_user_id="sleeper123",
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


def _mock_adapter():
    """Create a mock adapter with common return values."""
    adapter = AsyncMock()
    adapter.get_user.return_value = PlatformUser(
        user_id="sleeper123", username="testuser", display_name="Test"
    )
    adapter.get_leagues.return_value = [
        PlatformLeague(
            league_id="league1",
            name="Test League",
            season=2025,
            roster_size=15,
            scoring_type="ppr",
            settings={"leg": 1},
        )
    ]
    adapter.get_rosters.return_value = [
        PlatformRosterEntry(
            owner_id="sleeper123",
            player_ids=["p1", "p2"],
            starters=["p1"],
        )
    ]
    adapter.get_matchups.return_value = []
    adapter.get_transactions.return_value = []
    return adapter


class TestSyncLeagues:
    async def test_sync_leagues_creates_league(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)

        assert len(leagues) == 1
        assert leagues[0].name == "Test League"
        assert leagues[0].platform_league_id == "league1"

        # Verify league in DB
        result = await db_session.execute(select(League))
        db_leagues = result.scalars().all()
        assert len(db_leagues) == 1

        # Verify user_league created
        result = await db_session.execute(select(UserLeague))
        user_leagues = result.scalars().all()
        assert len(user_leagues) == 1

    async def test_sync_leagues_creates_sync_log(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_leagues(user.id, account, 2025)

        result = await db_session.execute(select(SyncLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].status == SyncStatus.completed

    async def test_sync_leagues_upserts_on_repeat(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_leagues(user.id, account, 2025)
            # Run again — should upsert, not duplicate
            await engine.sync_leagues(user.id, account, 2025)

        result = await db_session.execute(select(League))
        assert len(result.scalars().all()) == 1

    async def test_sync_leagues_error_logged(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()
        mock_adapter.get_leagues.side_effect = RuntimeError("API down")

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            with pytest.raises(RuntimeError, match="API down"):
                await engine.sync_leagues(user.id, account, 2025)

        result = await db_session.execute(select(SyncLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].status == SyncStatus.failed
        assert "API down" in logs[0].error_message


class TestSyncMatchups:
    async def test_sync_matchups_creates_matchups(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        # First sync leagues to create league + user_league
        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)

        league = leagues[0]

        # Set up user_leagues with platform_team_ids
        result = await db_session.execute(
            select(UserLeague).where(UserLeague.league_id == league.id)
        )
        ul = result.scalar_one()
        ul.platform_team_id = "sleeper123"
        await db_session.flush()

        # Create a second user_league for the opponent (different user)
        opponent_user = await _create_test_user(db_session)
        opponent_ul = UserLeague(
            user_id=opponent_user.id,
            league_id=league.id,
            team_name="Opponent",
            platform_team_id="opponent1",
        )
        db_session.add(opponent_ul)
        await db_session.flush()
        await db_session.refresh(opponent_ul)

        mock_adapter.get_matchups.return_value = [
            PlatformMatchup(matchup_id=1, roster_id="sleeper123", points=120.5, week=1),
            PlatformMatchup(matchup_id=1, roster_id="opponent1", points=115.3, week=1),
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_matchups(league, user.id, 1)

        result = await db_session.execute(select(Matchup))
        matchups = result.scalars().all()
        assert len(matchups) == 1
        # Home/away assigned by sorted roster_id: "opponent1" < "sleeper123"
        assert float(matchups[0].home_score) == 115.3
        assert float(matchups[0].away_score) == 120.5


class TestSyncStandings:
    async def test_sync_standings_calculates_correctly(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="Test",
            season=2025,
        )
        db_session.add(league)
        await db_session.flush()

        user2 = await _create_test_user(db_session)
        ul1 = UserLeague(user_id=user.id, league_id=league.id, team_name="Team A")
        ul2 = UserLeague(user_id=user2.id, league_id=league.id, team_name="Team B")
        db_session.add_all([ul1, ul2])
        await db_session.flush()
        await db_session.refresh(ul1)
        await db_session.refresh(ul2)

        # Create matchups: Team A wins week 1, Team B wins week 2
        m1 = Matchup(
            league_id=league.id, week=1,
            home_user_league_id=ul1.id, away_user_league_id=ul2.id,
            home_score=120, away_score=100,
        )
        m2 = Matchup(
            league_id=league.id, week=2,
            home_user_league_id=ul2.id, away_user_league_id=ul1.id,
            home_score=130, away_score=90,
        )
        db_session.add_all([m1, m2])
        await db_session.flush()

        with patch("app.sync.engine.get_adapter"):
            engine = SyncEngine(db_session)
            await engine.sync_standings(league, user.id)

        result = await db_session.execute(
            select(Standing).order_by(Standing.rank)
        )
        standings = result.scalars().all()
        assert len(standings) == 2
        # Both have 1 win, 1 loss; rank by points_for
        # Team B: 130 + 100 = 230 PF, Team A: 120 + 90 = 210 PF
        assert standings[0].user_league_id == ul2.id
        assert standings[0].wins == 1
        assert standings[0].losses == 1
        assert standings[0].rank == 1


class TestSyncAll:
    async def test_sync_all_orchestrates_full_sync(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            result = await engine.sync_all(user.id, account, 2025)

        assert result["status"] == "completed"
        assert "leagues" in result["synced"]

    async def test_sync_all_reports_errors(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()
        mock_adapter.get_leagues.side_effect = RuntimeError("Network error")

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            result = await engine.sync_all(user.id, account, 2025)

        assert result["status"] == "failed"
        assert len(result["errors"]) > 0
