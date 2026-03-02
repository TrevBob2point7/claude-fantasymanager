"""Integration tests for the sync engine."""

from unittest.mock import AsyncMock, patch

import pytest
from app.models import (
    League,
    Matchup,
    PlatformAccount,
    PlatformType,
    Roster,
    Standing,
    SyncLog,
    SyncStatus,
    Transaction,
    UserLeague,
)
from app.models.player import Player
from app.models.user import User
from app.platforms.schemas import (
    PlatformLeague,
    PlatformMatchup,
    PlatformRosterEntry,
    PlatformTransaction,
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


class TestSyncTransactions:
    async def test_sync_transactions_idempotent(self, db_session: AsyncSession):
        """Re-syncing the same week should not create duplicate transactions."""
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        # Sync leagues to create league + user_league
        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)

        league = leagues[0]

        # Set up user_league with platform_team_id
        result = await db_session.execute(
            select(UserLeague).where(UserLeague.league_id == league.id)
        )
        ul = result.scalar_one()
        ul.platform_team_id = "sleeper123"
        await db_session.flush()

        mock_adapter.get_transactions.return_value = [
            PlatformTransaction(
                type="add",
                player_ids_added=["p1"],
                player_ids_dropped=[],
                roster_ids=["sleeper123"],
                timestamp=1700000000000,
            ),
            PlatformTransaction(
                type="add",
                player_ids_added=["p2"],
                player_ids_dropped=["p3"],
                roster_ids=["sleeper123"],
                timestamp=1700000001000,
            ),
        ]
        mock_adapter.get_players_map.return_value = {}

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_transactions(league, user.id, week=1)

        result = await db_session.execute(
            select(Transaction).where(Transaction.league_id == league.id)
        )
        first_count = len(result.scalars().all())
        assert first_count > 0

        # Sync again — should delete and rebuild, not duplicate
        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_transactions(league, user.id, week=1)

        result = await db_session.execute(
            select(Transaction).where(Transaction.league_id == league.id)
        )
        second_count = len(result.scalars().all())
        assert second_count == first_count


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


class TestSyncRostersSlotInference:
    """Phase 0.1: Contract tests for slot inference in sync_rosters()."""

    async def test_sync_rosters_assigns_slot_labels(self, db_session: AsyncSession):
        """Given roster_positions in settings_json, starters get actual slot labels."""
        user = await _create_test_user(db_session)

        # Create league with roster_positions in settings_json
        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_slots",
            name="Slot Test League",
            season=2025,
            settings_json={
                "leg": 1,
                "roster_positions": [
                    "QB", "RB", "RB", "WR", "WR", "TE", "FLEX",
                    "BN", "BN", "IR",
                ],
            },
        )
        db_session.add(league)
        await db_session.flush()

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="Slot Team",
            platform_team_id="sleeper123",
        )
        db_session.add(ul)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(
                owner_id="sleeper123",
                player_ids=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"],
                starters=["p1", "p2", "p3", "p4", "p5", "p6", "p7"],
            )
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_rosters(league, user.id)

        result = await db_session.execute(
            select(Roster).where(Roster.user_league_id == ul.id)
        )
        rosters = result.scalars().all()

        # Build a player_id → slot map (need to look up by sleeper_id)
        slot_by_position = {}
        for r in rosters:
            # Get the player's sleeper_id to map back
            player = await db_session.get(Player, r.player_id)
            if player and player.sleeper_id:
                slot_by_position[player.sleeper_id] = r.slot

        # Starters should have actual slot labels, not "STARTER"
        assert slot_by_position.get("p1") == "QB"
        assert slot_by_position.get("p2") == "RB"
        assert slot_by_position.get("p3") == "RB"
        assert slot_by_position.get("p4") == "WR"
        assert slot_by_position.get("p5") == "WR"
        assert slot_by_position.get("p6") == "TE"
        assert slot_by_position.get("p7") == "FLEX"
        # Bench players should have no slot
        assert slot_by_position.get("p8") is None
        assert slot_by_position.get("p9") is None

    async def test_sync_rosters_empty_roster_positions(self, db_session: AsyncSession):
        """When roster_positions is absent from settings_json, fall back to STARTER."""
        user = await _create_test_user(db_session)

        # League without roster_positions in settings
        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_no_positions",
            name="No Positions League",
            season=2025,
            settings_json={"leg": 1},
        )
        db_session.add(league)
        await db_session.flush()

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="No Pos Team",
            platform_team_id="sleeper123",
        )
        db_session.add(ul)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(
                owner_id="sleeper123",
                player_ids=["p1", "p2"],
                starters=["p1"],
            )
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_rosters(league, user.id)

        result = await db_session.execute(
            select(Roster).where(Roster.user_league_id == ul.id)
        )
        rosters = result.scalars().all()

        slot_by_sleeper_id = {}
        for r in rosters:
            player = await db_session.get(Player, r.player_id)
            if player and player.sleeper_id:
                slot_by_sleeper_id[player.sleeper_id] = r.slot

        # Should fall back to "STARTER" when no roster_positions available
        assert slot_by_sleeper_id.get("p1") == "STARTER"
        assert slot_by_sleeper_id.get("p2") is None

    async def test_sync_rosters_starter_count_mismatch(self, db_session: AsyncSession):
        """Fewer starters than starter slots → only assign slots for available starters."""
        user = await _create_test_user(db_session)

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_mismatch",
            name="Mismatch League",
            season=2025,
            settings_json={
                "leg": 1,
                "roster_positions": [
                    "QB", "RB", "RB", "WR", "WR", "TE", "FLEX",
                    "BN", "BN",
                ],
            },
        )
        db_session.add(league)
        await db_session.flush()

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="Mismatch Team",
            platform_team_id="sleeper123",
        )
        db_session.add(ul)
        await db_session.flush()

        # Only 3 starters but 7 starter slots in roster_positions
        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(
                owner_id="sleeper123",
                player_ids=["p1", "p2", "p3", "p4", "p5"],
                starters=["p1", "p2", "p3"],
            )
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_rosters(league, user.id)

        result = await db_session.execute(
            select(Roster).where(Roster.user_league_id == ul.id)
        )
        rosters = result.scalars().all()

        slot_by_sleeper_id = {}
        for r in rosters:
            player = await db_session.get(Player, r.player_id)
            if player and player.sleeper_id:
                slot_by_sleeper_id[player.sleeper_id] = r.slot

        # Only 3 starters mapped to first 3 starter slots
        assert slot_by_sleeper_id.get("p1") == "QB"
        assert slot_by_sleeper_id.get("p2") == "RB"
        assert slot_by_sleeper_id.get("p3") == "RB"
        # Bench players
        assert slot_by_sleeper_id.get("p4") is None
        assert slot_by_sleeper_id.get("p5") is None


class TestSyncHistoricalSeasons:
    """Phase 0.1: Contract tests for historical season chain walking."""

    async def test_sync_historical_walks_chain(self, db_session: AsyncSession):
        """Mock adapter with 2 past leagues chained via previous_league_id → all 3 in DB."""
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        # Current season league
        mock_adapter.get_leagues.return_value = [
            PlatformLeague(
                league_id="lg_2025",
                name="Dynasty League",
                season=2025,
                roster_size=15,
                scoring_type="ppr",
                settings={"leg": 1},
                previous_league_id="lg_2024",
            )
        ]

        # Historical leagues returned by get_league()
        async def mock_get_league(league_id: str):
            if league_id == "lg_2024":
                return PlatformLeague(
                    league_id="lg_2024",
                    name="Dynasty League",
                    season=2024,
                    roster_size=15,
                    scoring_type="ppr",
                    settings={"leg": 17},
                    previous_league_id="lg_2023",
                )
            elif league_id == "lg_2023":
                return PlatformLeague(
                    league_id="lg_2023",
                    name="Dynasty League",
                    season=2023,
                    roster_size=15,
                    scoring_type="ppr",
                    settings={"leg": 17},
                    previous_league_id=None,
                )
            raise ValueError(f"Unknown league: {league_id}")

        mock_adapter.get_league = AsyncMock(side_effect=mock_get_league)

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)
            # Trigger historical sync
            await engine.sync_historical_seasons(leagues[0], user.id, account)

        # All 3 seasons should be in the DB
        result = await db_session.execute(
            select(League).where(
                League.platform_type == PlatformType.sleeper,
                League.platform_league_id.in_(["lg_2025", "lg_2024", "lg_2023"]),
            )
        )
        db_leagues = result.scalars().all()
        seasons = sorted([lg.season for lg in db_leagues])
        assert seasons == [2023, 2024, 2025]

    async def test_sync_historical_skips_existing(self, db_session: AsyncSession):
        """If a past season league already exists in DB, skip it and stop walking."""
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)

        # Pre-create the 2024 league in DB
        existing_league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_2024",
            name="Dynasty League (old)",
            season=2024,
        )
        db_session.add(existing_league)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_leagues.return_value = [
            PlatformLeague(
                league_id="lg_2025",
                name="Dynasty League",
                season=2025,
                roster_size=15,
                scoring_type="ppr",
                settings={"leg": 1},
                previous_league_id="lg_2024",
            )
        ]
        mock_adapter.get_league = AsyncMock()

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)
            await engine.sync_historical_seasons(leagues[0], user.id, account)

        # get_league should NOT have been called (we skipped because it exists)
        mock_adapter.get_league.assert_not_called()

    async def test_sync_historical_handles_no_previous(self, db_session: AsyncSession):
        """League with previous_league_id=None → no historical sync attempted."""
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        # League with no previous_league_id
        mock_adapter.get_leagues.return_value = [
            PlatformLeague(
                league_id="lg_new",
                name="New League",
                season=2025,
                roster_size=10,
                scoring_type="half_ppr",
                settings={"leg": 1},
                previous_league_id=None,
            )
        ]
        mock_adapter.get_league = AsyncMock()

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)
            await engine.sync_historical_seasons(leagues[0], user.id, account)

        # get_league should never be called
        mock_adapter.get_league.assert_not_called()

        # Only the current season league should exist
        result = await db_session.execute(select(League))
        db_leagues = result.scalars().all()
        assert len(db_leagues) == 1
        assert db_leagues[0].platform_league_id == "lg_new"
