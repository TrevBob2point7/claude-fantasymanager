"""Integration tests for the leagues API endpoints."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.models import (
    League,
    PlatformAccount,
    PlatformType,
    Player,
    PlayerStatus,
    Position,
    Roster,
    ScoringType,
    UserLeague,
)
from app.platforms.schemas import PlatformLeague
from httpx import AsyncClient


class TestDiscoverLeagues:
    """POST /api/leagues/discover"""

    async def test_discover_success(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]
        account = PlatformAccount(
            user_id=user.id,
            platform_type=PlatformType.sleeper,
            platform_username="testuser",
            platform_user_id="123456789",
        )
        db_session.add(account)
        await db_session.commit()
        await db_session.refresh(account)

        mock_adapter = AsyncMock()
        mock_adapter.get_leagues.return_value = [
            PlatformLeague(
                league_id="lg1",
                name="Dynasty League",
                season=2025,
                roster_size=15,
                scoring_type="ppr",
            )
        ]

        with patch(
            "app.api.leagues.get_adapter", return_value=mock_adapter
        ):
            response = await authenticated_client.post(
                "/api/leagues/discover",
                json={
                    "platform_account_id": str(account.id),
                    "season": 2025,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Dynasty League"
        assert data[0]["platform_league_id"] == "lg1"
        assert data[0]["already_linked"] is False

    async def test_discover_account_not_found(
        self, authenticated_client: AsyncClient
    ):
        response = await authenticated_client.post(
            "/api/leagues/discover",
            json={
                "platform_account_id": str(uuid.uuid4()),
                "season": 2025,
            },
        )
        assert response.status_code == 404

    async def test_discover_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/leagues/discover",
            json={
                "platform_account_id": str(uuid.uuid4()),
                "season": 2025,
            },
        )
        assert response.status_code == 401


class TestListLeagues:
    """GET /api/leagues"""

    async def test_list_leagues_success(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="My League",
            season=datetime.now().year,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get("/api/leagues")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "My League"
        assert data[0]["team_name"] == "My Team"

    async def test_list_leagues_filter_by_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        for season in [2024, 2025]:
            league = League(
                platform_type=PlatformType.sleeper,
                platform_league_id=f"lg_{season}",
                name=f"League {season}",
                season=season,
            )
            db_session.add(league)
            await db_session.flush()
            await db_session.refresh(league)
            ul = UserLeague(
                user_id=user.id, league_id=league.id,
                platform_team_id=f"1_{season}",
            )
            db_session.add(ul)

        await db_session.commit()

        response = await authenticated_client.get("/api/leagues?season=2025")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["season"] == 2025

    async def test_list_leagues_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/leagues")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_leagues_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/leagues")
        assert response.status_code == 401


class TestGetLeagueDetail:
    """GET /api/leagues/{league_id}"""

    async def test_get_league_detail_success(
        self, authenticated_client: AsyncClient, db_session
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg1",
            name="Detail League",
            season=2025,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Detail League"
        assert data["team_name"] == "My Team"
        assert "standings" in data
        assert "roster" in data
        assert "recent_matchups" in data
        assert "recent_transactions" in data

    async def test_get_league_detail_not_found(
        self, authenticated_client: AsyncClient
    ):
        response = await authenticated_client.get(
            f"/api/leagues/{uuid.uuid4()}"
        )
        assert response.status_code == 404

    async def test_get_league_detail_unauthenticated(self, client: AsyncClient):
        response = await client.get(f"/api/leagues/{uuid.uuid4()}")
        assert response.status_code == 401

    async def test_league_detail_includes_roster_status(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Roster entries include status field (from player model)."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_status",
            name="Status League",
            season=2025,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()
        await db_session.refresh(ul)

        player = Player(
            full_name="Patrick Mahomes",
            position=Position.QB,
            team="KC",
            sleeper_id="pm_status_test",
            status=PlayerStatus.questionable,
        )
        db_session.add(player)
        await db_session.flush()
        await db_session.refresh(player)

        roster = Roster(
            user_league_id=ul.id,
            player_id=player.id,
            slot="QB",
        )
        db_session.add(roster)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["roster"]) >= 1
        roster_entry = data["roster"][0]
        assert "status" in roster_entry
        assert roster_entry["status"] == "questionable"

    async def test_league_detail_includes_bye_week(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Roster entries include bye_week field (joined from team_bye_weeks)."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_bye",
            name="Bye Week League",
            season=2025,
            scoring_type=ScoringType.ppr,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()
        await db_session.refresh(ul)

        player = Player(
            full_name="Travis Kelce",
            position=Position.TE,
            team="KC",
            sleeper_id="tk_bye_test",
        )
        db_session.add(player)
        await db_session.flush()
        await db_session.refresh(player)

        roster = Roster(
            user_league_id=ul.id,
            player_id=player.id,
            slot="TE",
        )
        db_session.add(roster)

        # Insert bye week data for KC
        from app.models.team_bye_week import TeamByeWeek

        bye = TeamByeWeek(season=2025, team="KC", bye_week=6)
        db_session.add(bye)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["roster"]) >= 1
        roster_entry = data["roster"][0]
        assert "bye_week" in roster_entry
        assert roster_entry["bye_week"] == 6

    async def test_league_detail_includes_current_week(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Response includes current_week field."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_week",
            name="Current Week League",
            season=2025,
            scoring_type=ScoringType.ppr,
            settings_json={"leg": 8},
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        assert "current_week" in data
        assert data["current_week"] == 8

    async def test_league_detail_roster_has_slot_labels(
        self, authenticated_client: AsyncClient, db_session
    ):
        """Roster entries have slot values like 'QB', 'FLEX' (not 'STARTER')."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_slots",
            name="Slot Labels League",
            season=2025,
            scoring_type=ScoringType.ppr,
            settings_json={
                "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN", "BN"]
            },
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id,
            league_id=league.id,
            team_name="My Team",
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.flush()
        await db_session.refresh(ul)

        # Create a player with a QB slot
        player = Player(
            full_name="Josh Allen",
            position=Position.QB,
            team="BUF",
            sleeper_id="ja_slot_test",
        )
        db_session.add(player)
        await db_session.flush()
        await db_session.refresh(player)

        roster = Roster(
            user_league_id=ul.id,
            player_id=player.id,
            slot="QB",
        )
        db_session.add(roster)
        await db_session.commit()

        response = await authenticated_client.get(f"/api/leagues/{league.id}")
        assert response.status_code == 200
        data = response.json()
        slots = [r["slot"] for r in data["roster"] if r["slot"] is not None]
        # No slot should be "STARTER" — they should be actual position labels
        assert "STARTER" not in slots
        assert "QB" in slots


@pytest.mark.asyncio(loop_scope="session")
class TestGetLeagueSeasons:
    """GET /api/leagues/{league_id}/seasons"""

    async def test_get_league_seasons_returns_chain(
        self, authenticated_client: AsyncClient, db_session
    ):
        """New endpoint returns [{season, league_id}] sorted by season desc."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        # Create a chain of 3 seasons: 2025 -> 2024 -> 2023
        league_2023 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_chain_2023",
            name="Chain League 2023",
            season=2023,
            previous_league_id=None,
        )
        db_session.add(league_2023)
        await db_session.flush()
        await db_session.refresh(league_2023)

        league_2024 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_chain_2024",
            name="Chain League 2024",
            season=2024,
            previous_league_id="lg_chain_2023",
        )
        db_session.add(league_2024)
        await db_session.flush()
        await db_session.refresh(league_2024)

        league_2025 = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_chain_2025",
            name="Chain League 2025",
            season=2025,
            previous_league_id="lg_chain_2024",
        )
        db_session.add(league_2025)
        await db_session.flush()
        await db_session.refresh(league_2025)

        # Link user to all leagues
        for i, lg in enumerate([league_2023, league_2024, league_2025], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=str(i),
            )
            db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/leagues/{league_2025.id}/seasons"
        )
        assert response.status_code == 200
        data = response.json()

        # Should return all 3 seasons sorted desc
        seasons = data["seasons"]
        assert len(seasons) == 3
        assert seasons[0]["season"] == 2025
        assert seasons[1]["season"] == 2024
        assert seasons[2]["season"] == 2023

        # Each entry should have a league_id
        for entry in seasons:
            assert "league_id" in entry
            assert "season" in entry

    async def test_get_league_seasons_single_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        """League with no previous_league_id returns single-entry list."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_single",
            name="Single Season League",
            season=2025,
            previous_league_id=None,
        )
        db_session.add(league)
        await db_session.flush()
        await db_session.refresh(league)

        ul = UserLeague(
            user_id=user.id, league_id=league.id,
            platform_team_id="1",
        )
        db_session.add(ul)
        await db_session.commit()

        response = await authenticated_client.get(
            f"/api/leagues/{league.id}/seasons"
        )
        assert response.status_code == 200
        data = response.json()

        seasons = data["seasons"]
        assert len(seasons) == 1
        assert seasons[0]["season"] == 2025
        assert seasons[0]["league_id"] == str(league.id)


@pytest.mark.asyncio(loop_scope="session")
class TestListLeaguesCurrentSeason:
    """GET /api/leagues — current season filtering."""

    async def test_list_leagues_filters_current_season(
        self, authenticated_client: AsyncClient, db_session
    ):
        """GET /api/leagues only returns leagues matching current year (no season param)."""
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        current_year = datetime.now().year

        # Create a past-season league and a current-season league
        old_league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_old_filter",
            name="Old League",
            season=current_year - 1,
        )
        db_session.add(old_league)
        await db_session.flush()
        await db_session.refresh(old_league)

        current_league = League(
            platform_type=PlatformType.sleeper,
            platform_league_id="lg_current_filter",
            name="Current League",
            season=current_year,
        )
        db_session.add(current_league)
        await db_session.flush()
        await db_session.refresh(current_league)

        for i, lg in enumerate([old_league, current_league], start=1):
            ul = UserLeague(
                user_id=user.id, league_id=lg.id,
                platform_team_id=str(i),
            )
            db_session.add(ul)
        await db_session.commit()

        # Request without season param — should only return current year
        response = await authenticated_client.get("/api/leagues")
        assert response.status_code == 200
        data = response.json()

        # Should only include the current-season league
        seasons_returned = [d["season"] for d in data]
        assert current_year in seasons_returned
        assert (current_year - 1) not in seasons_returned
