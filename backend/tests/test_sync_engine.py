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
    PlatformLeagueUser,
    PlatformMatchup,
    PlatformRosterEntry,
    PlatformStanding,
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
            roster_id="1",
            player_ids=["p1", "p2"],
            starters=["p1"],
        )
    ]
    adapter.get_league_users.return_value = [
        PlatformLeagueUser(
            user_id="sleeper123",
            display_name="Test User",
            team_name="Test Team",
        )
    ]
    adapter.get_players_map.return_value = {}
    adapter.get_matchups.return_value = []
    adapter.get_transactions.return_value = []
    adapter.get_standings.return_value = None
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


class TestSyncUserLeagues:
    async def test_sync_user_leagues_creates_all_teams(self, db_session: AsyncSession):
        """_sync_user_leagues creates entries for ALL teams, not just the current user."""
        user = await _create_test_user(db_session)

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="Test",
            season=2025,
        )
        db_session.add(league)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(owner_id="sleeper123", roster_id="1", player_ids=["p1"]),
            PlatformRosterEntry(owner_id="other_owner1", roster_id="2", player_ids=["p2"]),
            PlatformRosterEntry(owner_id="other_owner2", roster_id="3", player_ids=["p3"]),
        ]
        mock_adapter.get_league_users.return_value = [
            PlatformLeagueUser(user_id="sleeper123", display_name="Me", team_name="My Team"),
            PlatformLeagueUser(user_id="other_owner1", display_name="Bob", team_name="Bob's Team"),
            PlatformLeagueUser(user_id="other_owner2", display_name="Alice", team_name=None),
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine._sync_user_leagues(league, user.id, "sleeper123")

        result = await db_session.execute(
            select(UserLeague).where(UserLeague.league_id == league.id)
        )
        user_leagues = result.scalars().all()
        assert len(user_leagues) == 3

        # Current user's team has user_id set
        my_ul = next(ul for ul in user_leagues if ul.platform_team_id == "1")
        assert my_ul.user_id == user.id
        assert my_ul.team_name == "My Team"

        # Other teams have user_id=None
        bob_ul = next(ul for ul in user_leagues if ul.platform_team_id == "2")
        assert bob_ul.user_id is None
        assert bob_ul.team_name == "Bob's Team"

        alice_ul = next(ul for ul in user_leagues if ul.platform_team_id == "3")
        assert alice_ul.user_id is None
        # Falls back to display_name when team_name is None
        assert alice_ul.team_name == "Alice"


class TestSyncMatchups:
    async def test_sync_matchups_creates_matchups(self, db_session: AsyncSession):
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)
        mock_adapter = _mock_adapter()

        # First sync leagues to create league
        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)

        league = leagues[0]

        # Create user_leagues with roster_id-based platform_team_ids
        ul1 = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        ul2 = UserLeague(
            user_id=None,
            league_id=league.id,
            team_name="Opponent",
            platform_team_id="2",
        )
        db_session.add_all([ul1, ul2])
        await db_session.flush()
        await db_session.refresh(ul1)
        await db_session.refresh(ul2)

        mock_adapter.get_matchups.return_value = [
            PlatformMatchup(
                matchup_id=1, roster_id="1", points=120.5, week=1,
                starters=["p1"], starters_points={"p1": 120.5},
            ),
            PlatformMatchup(
                matchup_id=1, roster_id="2", points=115.3, week=1,
                starters=["p2"], starters_points={"p2": 115.3},
            ),
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_matchups(league, user.id, 1)

        result = await db_session.execute(select(Matchup))
        matchups = result.scalars().all()
        assert len(matchups) == 1
        # Home/away assigned by sorted roster_id: "1" < "2"
        assert float(matchups[0].home_score) == 120.5
        assert float(matchups[0].away_score) == 115.3
        # Starters JSON should be populated
        assert matchups[0].home_starters_json is not None
        assert len(matchups[0].home_starters_json) == 1
        assert matchups[0].home_starters_json[0]["player_id"] == "p1"
        assert matchups[0].home_starters_json[0]["points"] == 120.5
        assert matchups[0].away_starters_json is not None
        assert matchups[0].away_starters_json[0]["player_id"] == "p2"


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

        ul1 = UserLeague(
            user_id=user.id, league_id=league.id,
            team_name="Team A", platform_team_id="1",
        )
        ul2 = UserLeague(
            user_id=None, league_id=league.id,
            team_name="Team B", platform_team_id="2",
        )
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

        mock_adapter = _mock_adapter()
        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
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

        # Sync leagues to create league
        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)

        league = leagues[0]

        # Set up user_league with platform_team_id (roster_id)
        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()

        mock_adapter.get_transactions.return_value = [
            PlatformTransaction(
                type="add",
                player_ids_added=["p1"],
                player_ids_dropped=[],
                roster_ids=["1"],
                timestamp=1700000000000,
            ),
            PlatformTransaction(
                type="add",
                player_ids_added=["p2"],
                player_ids_dropped=["p3"],
                roster_ids=["1"],
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
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(
                owner_id="sleeper123",
                roster_id="1",
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
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(
                owner_id="sleeper123",
                roster_id="1",
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
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()

        # Only 3 starters but 7 starter slots in roster_positions
        mock_adapter = _mock_adapter()
        mock_adapter.get_rosters.return_value = [
            PlatformRosterEntry(
                owner_id="sleeper123",
                roster_id="1",
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


class TestSyncMFLLeague:
    async def test_sync_mfl_league_passes_credentials(self, db_session: AsyncSession):
        """Sync engine passes credentials_json when creating MFL adapter."""
        user = await _create_test_user(db_session)
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.mfl,
            platform_username="mfluser",
            platform_user_id="mfluser",  # MFL sets this at login
            credentials_json={"cookie": "MFL_USER_ID=test123", "password": "secret"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        mfl_league = PlatformLeague(
            league_id="40750",
            name="MFL Dynasty",
            season=2025,
            roster_size=25,
            scoring_type="ppr",
            league_type="dynasty",
            settings={"startWeek": "1", "endWeek": "17", "lastRegularSeasonWeek": "14"},
        )

        mock_adapter = _mock_adapter()
        mock_adapter.get_leagues.return_value = [mfl_league]
        # MFL sync_leagues enriches via get_league per league
        mock_adapter.get_league = AsyncMock(return_value=mfl_league)

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter) as mock_get:
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)

        assert len(leagues) == 1
        assert leagues[0].name == "MFL Dynasty"
        # Verify credentials were passed to get_adapter
        mock_get.assert_called_with(
            PlatformType.mfl,
            credentials_json=account.credentials_json,
        )


class TestSyncMFLWeekCount:
    async def test_sync_all_does_not_fetch_matchups(self, db_session: AsyncSession):
        """sync_all no longer syncs matchups — they are fetched lazily."""
        user = await _create_test_user(db_session)
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.mfl,
            platform_username="mfluser",
            platform_user_id="mfluser",
            credentials_json={"cookie": "MFL_USER_ID=test123"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        mfl_league = PlatformLeague(
            league_id="40750",
            name="MFL League",
            season=2025,
            settings={"endWeek": "16"},
        )

        mock_adapter = _mock_adapter()
        mock_adapter.get_leagues.return_value = [mfl_league]
        mock_adapter.get_league = AsyncMock(return_value=mfl_league)
        mock_adapter.get_rosters.return_value = []
        mock_adapter.get_league_users.return_value = []

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_all(user.id, account, 2025)

        # Matchups should NOT be fetched during sync_all (lazy loading)
        mock_adapter.get_matchups.assert_not_called()


class TestSyncMFLHistoricalSeasons:
    async def test_mfl_historical_uses_year_adapter(self, db_session: AsyncSession):
        """MFL historical sync creates new adapter with correct year parameter."""
        user = await _create_test_user(db_session)
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.mfl,
            platform_username="mfluser",
            platform_user_id="mfluser",
            credentials_json={"cookie": "MFL_USER_ID=test123"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        current_league = League(
            platform_type=PlatformType.mfl,
            platform_league_id="40750",
            name="MFL Dynasty",
            season=2025,
            settings_json={"endWeek": "17"},
        )
        db_session.add(current_league)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        # MFL historical uses get_history_years to discover past seasons
        mock_adapter.get_history_years = AsyncMock(return_value=[2025, 2024])
        mock_adapter.get_league.return_value = PlatformLeague(
            league_id="40750",
            name="MFL Dynasty",
            season=2024,
            roster_size=25,
            scoring_type="ppr",
            settings={"endWeek": "17"},
            previous_league_id=None,
        )
        mock_adapter.get_rosters.return_value = []
        mock_adapter.get_league_users.return_value = []

        get_adapter_calls = []

        def mock_get_adapter(platform_type, **kwargs):
            get_adapter_calls.append((platform_type, kwargs))
            return mock_adapter

        with patch("app.sync.engine.get_adapter", side_effect=mock_get_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_historical_seasons(current_league, user.id, account)

        # First call: year=2025 (to fetch history entries)
        # Second call: year=2024 (to sync the historical season)
        year_calls = [c for c in get_adapter_calls if c[1].get("year") is not None]
        assert len(year_calls) >= 2
        assert year_calls[0][1]["year"] == 2025  # history discovery
        assert year_calls[1][1]["year"] == 2024  # historical season sync

    async def test_mfl_historical_uses_history_entries(self, db_session: AsyncSession):
        """MFL historical sync discovers years from get_history_years, not chain walking."""
        user = await _create_test_user(db_session)
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.mfl,
            platform_username="mfluser",
            platform_user_id="mfluser",
            credentials_json={"cookie": "MFL_USER_ID=test123"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        current_league = League(
            platform_type=PlatformType.mfl,
            platform_league_id="40750",
            name="MFL Dynasty",
            season=2025,
            settings_json={"endWeek": "17"},
        )
        db_session.add(current_league)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        # get_history_years returns multiple past years
        mock_adapter.get_history_years = AsyncMock(return_value=[2025, 2024, 2023, 2022])
        # get_league returns metadata for each historical year
        mock_adapter.get_league = AsyncMock(side_effect=lambda lid: PlatformLeague(
            league_id="40750",
            name="MFL Dynasty",
            season=2020,  # will be overridden by year adapter
            roster_size=25,
            scoring_type="ppr",
            settings={"endWeek": "17"},
        ))
        mock_adapter.get_rosters.return_value = []
        mock_adapter.get_league_users.return_value = []

        def mock_get_adapter(platform_type, **kwargs):
            return mock_adapter

        with patch("app.sync.engine.get_adapter", side_effect=mock_get_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_historical_seasons(current_league, user.id, account)

        # get_history_years should have been called
        mock_adapter.get_history_years.assert_called_once_with("40750")
        # get_league should have been called for each historical year (2024, 2023, 2022)
        assert mock_adapter.get_league.call_count == 3

    async def test_mfl_historical_carries_user_franchise_id(self, db_session: AsyncSession):
        """user_franchise_id from parent league settings is carried to historical leagues."""
        user = await _create_test_user(db_session)
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.mfl,
            platform_username="mfluser",
            platform_user_id="mfluser",
            credentials_json={"cookie": "MFL_USER_ID=test123"},
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        current_league = League(
            platform_type=PlatformType.mfl,
            platform_league_id="40750",
            name="MFL Dynasty",
            season=2025,
            settings_json={"endWeek": "17", "user_franchise_id": "0003"},
        )
        db_session.add(current_league)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_history_years = AsyncMock(return_value=[2025, 2024])
        mock_adapter.get_league = AsyncMock(return_value=PlatformLeague(
            league_id="40750",
            name="MFL Dynasty",
            season=2024,
            roster_size=25,
            scoring_type="ppr",
            settings={"endWeek": "17"},
        ))
        mock_adapter.get_rosters.return_value = []
        mock_adapter.get_league_users.return_value = []

        def mock_get_adapter(platform_type, **kwargs):
            return mock_adapter

        with patch("app.sync.engine.get_adapter", side_effect=mock_get_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_historical_seasons(current_league, user.id, account)

        # Verify historical league has user_franchise_id carried over
        result = await db_session.execute(
            select(League).where(
                League.platform_type == PlatformType.mfl,
                League.platform_league_id == "40750",
                League.season == 2024,
            )
        )
        hist_league = result.scalar_one()
        assert hist_league.settings_json.get("user_franchise_id") == "0003"

    async def test_chain_historical_cycle_detection(self, db_session: AsyncSession):
        """Chain walking stops if it encounters a league that already exists (no infinite loop)."""
        user = await _create_test_user(db_session)
        account = await _create_platform_account(db_session, user)

        # Create a league chain: 2025 -> 2024 -> 2023 -> 2024 (cycle!)
        mock_adapter = _mock_adapter()
        mock_adapter.get_leagues.return_value = [
            PlatformLeague(
                league_id="lg_2025",
                name="Dynasty",
                season=2025,
                settings={"leg": 1},
                previous_league_id="lg_2024",
            )
        ]

        call_count = 0

        async def mock_get_league(league_id: str):
            nonlocal call_count
            call_count += 1
            if call_count > 10:
                raise RuntimeError("Infinite loop detected in test")
            if league_id == "lg_2024":
                return PlatformLeague(
                    league_id="lg_2024",
                    name="Dynasty",
                    season=2024,
                    settings={"leg": 17},
                    previous_league_id="lg_2023",
                )
            elif league_id == "lg_2023":
                return PlatformLeague(
                    league_id="lg_2023",
                    name="Dynasty",
                    season=2023,
                    settings={"leg": 17},
                    previous_league_id="lg_2024",  # Cycle!
                )
            raise ValueError(f"Unknown league: {league_id}")

        mock_adapter.get_league = AsyncMock(side_effect=mock_get_league)
        mock_adapter.get_rosters.return_value = []
        mock_adapter.get_league_users.return_value = []

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            leagues = await engine.sync_leagues(user.id, account, 2025)
            # This should NOT loop forever — cycle is broken because
            # chain walking checks for existing leagues in DB
            await engine.sync_historical_seasons(leagues[0], user.id, account)

        # Should have created 2024 and 2023, then stopped when 2024 already exists
        result = await db_session.execute(select(League))
        db_leagues = result.scalars().all()
        seasons = sorted([lg.season for lg in db_leagues])
        assert 2023 in seasons
        assert 2024 in seasons
        assert 2025 in seasons
        # Should not have looped more than necessary
        assert call_count <= 4


class TestSyncMFLStandings:
    async def test_sync_standings_uses_platform_standings(self, db_session: AsyncSession):
        """When adapter returns standings, use them instead of computing from matchups."""
        user = await _create_test_user(db_session)

        league = League(
            platform_type=PlatformType.mfl,
            platform_league_id="40750",
            name="MFL League",
            season=2025,
        )
        db_session.add(league)
        await db_session.flush()

        ul1 = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="Team A",
            platform_team_id="0001",
        )
        ul2 = UserLeague(
            user_id=None,
            league_id=league.id,
            team_name="Team B",
            platform_team_id="0002",
        )
        db_session.add_all([ul1, ul2])
        await db_session.flush()
        await db_session.refresh(ul1)
        await db_session.refresh(ul2)

        mock_adapter = _mock_adapter()
        mock_adapter.get_standings.return_value = [
            PlatformStanding(
                franchise_id="0001",
                wins=10,
                losses=3,
                ties=0,
                points_for=1500.5,
                points_against=1200.3,
            ),
            PlatformStanding(
                franchise_id="0002",
                wins=7,
                losses=6,
                ties=0,
                points_for=1300.0,
                points_against=1350.0,
            ),
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_standings(league, user.id)

        result = await db_session.execute(
            select(Standing).where(Standing.league_id == league.id).order_by(Standing.rank)
        )
        standings = result.scalars().all()
        assert len(standings) == 2
        # Team A should be rank 1 (more wins)
        assert standings[0].user_league_id == ul1.id
        assert standings[0].wins == 10
        assert standings[0].losses == 3
        assert float(standings[0].points_for) == 1500.5

    async def test_sync_standings_falls_back_to_matchups(self, db_session: AsyncSession):
        """When adapter returns None for standings, compute from matchups as before."""
        user = await _create_test_user(db_session)

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="Sleeper League",
            season=2025,
        )
        db_session.add(league)
        await db_session.flush()

        ul1 = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="Team A",
            platform_team_id="1",
        )
        ul2 = UserLeague(
            user_id=None,
            league_id=league.id,
            team_name="Team B",
            platform_team_id="2",
        )
        db_session.add_all([ul1, ul2])
        await db_session.flush()
        await db_session.refresh(ul1)
        await db_session.refresh(ul2)

        # Create a matchup
        m1 = Matchup(
            league_id=league.id,
            week=1,
            home_user_league_id=ul1.id,
            away_user_league_id=ul2.id,
            home_score=120,
            away_score=100,
        )
        db_session.add(m1)
        await db_session.flush()

        mock_adapter = _mock_adapter()
        mock_adapter.get_standings.return_value = None  # No platform standings

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_standings(league, user.id)

        result = await db_session.execute(
            select(Standing).where(Standing.league_id == league.id).order_by(Standing.rank)
        )
        standings = result.scalars().all()
        assert len(standings) == 2
        # Team A won, so should be rank 1
        assert standings[0].user_league_id == ul1.id
        assert standings[0].wins == 1


class TestSyncPlayoffBrackets:
    """Tests for bracket sync: consolation flags, champion detection, and byes."""

    async def _setup_league_with_teams(
        self, db_session: AsyncSession, *, platform: PlatformType = PlatformType.sleeper,
        settings: dict | None = None, num_teams: int = 6,
    ):
        """Create a league with user_leagues for testing bracket sync."""
        user = await _create_test_user(db_session)

        league = League(
            platform_type=platform,
            platform_league_id="bracket_lg",
            name="Bracket Test",
            season=2025,
            settings_json=settings or {"playoff_week_start": 15, "playoff_teams": 6, "leg": 17},
        )
        db_session.add(league)
        await db_session.flush()

        uls = {}
        for i in range(1, num_teams + 1):
            ul = UserLeague(
                user_id=user.id if i == 1 else None,
                league_id=league.id,
                team_name=f"Team {i}",
                platform_team_id=str(i),
            )
            db_session.add(ul)
            uls[str(i)] = ul
        await db_session.flush()
        for ul in uls.values():
            await db_session.refresh(ul)

        return user, league, uls

    async def test_sleeper_consolation_pairings_applied(self, db_session: AsyncSession):
        """Bracket sync stores consolation pairings and flags matchups correctly."""
        _, league, uls = await self._setup_league_with_teams(db_session)

        # Create playoff matchups: round 2 has a consolation game (5 vs 6)
        # and a winners game (1 vs 3)
        m_winners = Matchup(
            league_id=league.id, week=16,
            home_user_league_id=uls["1"].id, away_user_league_id=uls["3"].id,
            home_score=120, away_score=100, playoff_round=2,
        )
        m_consolation = Matchup(
            league_id=league.id, week=16,
            home_user_league_id=uls["5"].id, away_user_league_id=uls["6"].id,
            home_score=90, away_score=80, playoff_round=2,
        )
        db_session.add_all([m_winners, m_consolation])
        await db_session.flush()

        # Mock adapter returns brackets
        mock_adapter = AsyncMock()
        mock_adapter.get_winners_bracket.return_value = [
            {"r": 1, "m": 1, "t1": 3, "t2": 6, "w": 3, "l": 6},
            {"r": 1, "m": 2, "t1": 4, "t2": 5, "w": 4, "l": 5},
            {"r": 2, "m": 3, "t1": 1, "t2": 3, "w": 1, "l": 3},
            {"r": 2, "m": 4, "t1": 2, "t2": 4, "w": 2, "l": 4},
            {"r": 3, "m": 5, "t1": 1, "t2": 2, "w": 1, "l": 2},
        ]
        mock_adapter.get_losers_bracket.return_value = [
            {"r": 1, "m": 1, "t1": 5, "t2": 6, "w": 5, "l": 6},
            {"r": 2, "m": 2, "t1": 3, "t2": 4, "w": 3, "l": 4},
        ]

        engine = SyncEngine(db_session)
        await engine.sync_playoff_brackets(league, adapter=mock_adapter)

        # Verify bracket_data stored
        bracket_data = league.settings_json.get("bracket_data", {})
        assert bracket_data["champion_franchise_id"] == "1"
        assert len(bracket_data["consolation_pairings"]) == 2
        assert ["5", "6"] in bracket_data["consolation_pairings"]
        assert bracket_data["byes"] == {"1": ["1", "2"]}

        # Verify consolation flags on matchups
        await db_session.refresh(m_winners)
        await db_session.refresh(m_consolation)
        assert m_winners.is_consolation is False
        assert m_consolation.is_consolation is True

    async def test_mfl_consolation_by_round_applied(self, db_session: AsyncSession):
        """MFL bracket sync uses round-based consolation and flags matchups."""
        _, league, uls = await self._setup_league_with_teams(
            db_session,
            platform=PlatformType.mfl,
            settings={"lastRegularSeasonWeek": "14", "endWeek": "17"},
        )

        # Week 17 (playoff_round 3): championship + 3rd place game
        m_champ = Matchup(
            league_id=league.id, week=17,
            home_user_league_id=uls["1"].id, away_user_league_id=uls["2"].id,
            home_score=140, away_score=130, playoff_round=3,
        )
        m_3rd = Matchup(
            league_id=league.id, week=17,
            home_user_league_id=uls["3"].id, away_user_league_id=uls["4"].id,
            home_score=110, away_score=100, playoff_round=3,
        )
        db_session.add_all([m_champ, m_3rd])
        await db_session.flush()

        mock_adapter = AsyncMock()
        # MFL winners bracket: 3 rounds
        mock_adapter.get_winners_bracket.return_value = [
            {"week": "15", "playoffGame": [
                {"home": {"franchise_id": "3", "seed": "3", "points": "100"},
                 "away": {"franchise_id": "6", "seed": "6", "points": "90"}},
                {"home": {"franchise_id": "4", "seed": "4", "points": "95"},
                 "away": {"franchise_id": "5", "seed": "5", "points": "85"}},
            ]},
            {"week": "16", "playoffGame": [
                {"home": {"franchise_id": "1", "seed": "1", "points": "130"},
                 "away": {"franchise_id": "3", "points": "110"}},
                {"home": {"franchise_id": "2", "seed": "2", "points": "125"},
                 "away": {"franchise_id": "4", "points": "105"}},
            ]},
            {"week": "17", "playoffGame": {
                "home": {"franchise_id": "1", "points": "140"},
                "away": {"franchise_id": "2", "points": "130"},
            }},
        ]
        # MFL losers bracket: 3rd place game
        mock_adapter.get_losers_bracket.return_value = [
            {"week": "17", "playoffGame": {
                "home": {"franchise_id": "3"},
                "away": {"franchise_id": "4"},
            }},
        ]

        engine = SyncEngine(db_session)
        await engine.sync_playoff_brackets(league, adapter=mock_adapter)

        bracket_data = league.settings_json.get("bracket_data", {})
        assert bracket_data["champion_franchise_id"] == "1"
        assert "3" in bracket_data["consolation_by_round"]
        assert set(bracket_data["consolation_by_round"]["3"]) == {"3", "4"}
        assert set(bracket_data["byes"]["1"]) == {"1", "2"}

        await db_session.refresh(m_champ)
        await db_session.refresh(m_3rd)
        assert m_champ.is_consolation is False
        assert m_3rd.is_consolation is True

    async def test_bye_matchups_created_during_sync(self, db_session: AsyncSession):
        """sync_matchups creates bye rows for teams with first-round byes."""
        user, league, uls = await self._setup_league_with_teams(db_session)

        # Pre-seed bracket_data with byes
        settings = dict(league.settings_json or {})
        settings["bracket_data"] = {
            "champion_franchise_id": None,
            "consolation_by_round": {},
            "consolation_pairings": [],
            "byes": {"1": ["1", "2"]},
        }
        league.settings_json = settings
        await db_session.flush()

        # Mock adapter returns round 1 matchups (only seeds 3-6 play)
        mock_adapter = _mock_adapter()
        mock_adapter.get_matchups.return_value = [
            PlatformMatchup(matchup_id=1, roster_id="3", points=100, week=15),
            PlatformMatchup(matchup_id=1, roster_id="6", points=90, week=15),
            PlatformMatchup(matchup_id=2, roster_id="4", points=95, week=15),
            PlatformMatchup(matchup_id=2, roster_id="5", points=85, week=15),
        ]

        with patch("app.sync.engine.get_adapter", return_value=mock_adapter):
            engine = SyncEngine(db_session)
            await engine.sync_matchups(league, user.id, 15, adapter=mock_adapter)

        result = await db_session.execute(
            select(Matchup).where(
                Matchup.league_id == league.id,
                Matchup.week == 15,
            )
        )
        matchups = result.scalars().all()

        # 2 real matchups + 2 bye matchups = 4
        assert len(matchups) == 4

        bye_matchups = [m for m in matchups if m.away_user_league_id is None]
        assert len(bye_matchups) == 2

        bye_home_ids = {
            next(
                ul.platform_team_id
                for ul in uls.values()
                if ul.id == bm.home_user_league_id
            )
            for bm in bye_matchups
        }
        assert bye_home_ids == {"1", "2"}

        for bm in bye_matchups:
            assert bm.playoff_round == 1
            assert bm.is_consolation is False
            assert bm.home_score is None
            assert bm.away_score is None
