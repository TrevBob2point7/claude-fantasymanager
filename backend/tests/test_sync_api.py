"""Integration tests for the sync API endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

from app.models import PlatformAccount, PlatformType, SyncLog, SyncStatus
from app.models.enums import DataType
from app.platforms.schemas import PlatformLeague
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


class TestTriggerSync:
    """POST /api/sync/{account_id}"""

    async def test_trigger_sync_success(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
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
                name="Test League",
                season=2025,
                roster_size=15,
                scoring_type="ppr",
                settings={"leg": 1},
            )
        ]
        mock_adapter.get_rosters.return_value = []
        mock_adapter.get_matchups.return_value = []
        mock_adapter.get_transactions.return_value = []

        with patch(
            "app.sync.engine.get_adapter", return_value=mock_adapter
        ):
            response = await authenticated_client.post(
                f"/api/sync/{account.id}"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "leagues" in data["synced"]

    async def test_trigger_sync_account_not_found(
        self, authenticated_client: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await authenticated_client.post(f"/api/sync/{fake_id}")
        assert response.status_code == 404

    async def test_trigger_sync_unauthenticated(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.post(f"/api/sync/{fake_id}")
        assert response.status_code == 401


class TestSyncLog:
    """GET /api/sync/log"""

    async def test_get_sync_log_success(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        log = SyncLog(
            user_id=user.id,
            platform_type=PlatformType.sleeper,
            data_type=DataType.leagues,
            status=SyncStatus.completed,
        )
        db_session.add(log)
        await db_session.commit()

        response = await authenticated_client.get("/api/sync/log")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"
        assert data[0]["data_type"] == "leagues"

    async def test_get_sync_log_empty(
        self, authenticated_client: AsyncClient
    ):
        response = await authenticated_client.get("/api/sync/log")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_sync_log_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/sync/log")
        assert response.status_code == 401

    async def test_get_sync_log_respects_limit(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        user = authenticated_client.test_user  # type: ignore[attr-defined]

        for _i in range(5):
            log = SyncLog(
                user_id=user.id,
                platform_type=PlatformType.sleeper,
                data_type=DataType.leagues,
                status=SyncStatus.completed,
            )
            db_session.add(log)
        await db_session.commit()

        response = await authenticated_client.get("/api/sync/log?limit=3")
        assert response.status_code == 200
        assert len(response.json()) == 3
