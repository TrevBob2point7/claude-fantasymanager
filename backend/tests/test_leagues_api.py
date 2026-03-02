"""Integration tests for the leagues API endpoints."""

from unittest.mock import AsyncMock, patch

from app.models import League, PlatformAccount, PlatformType, ScoringType, UserLeague
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
        import uuid

        response = await authenticated_client.post(
            "/api/leagues/discover",
            json={
                "platform_account_id": str(uuid.uuid4()),
                "season": 2025,
            },
        )
        assert response.status_code == 404

    async def test_discover_unauthenticated(self, client: AsyncClient):
        import uuid

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
            ul = UserLeague(user_id=user.id, league_id=league.id)
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
        import uuid

        response = await authenticated_client.get(
            f"/api/leagues/{uuid.uuid4()}"
        )
        assert response.status_code == 404

    async def test_get_league_detail_unauthenticated(self, client: AsyncClient):
        import uuid

        response = await client.get(f"/api/leagues/{uuid.uuid4()}")
        assert response.status_code == 401
