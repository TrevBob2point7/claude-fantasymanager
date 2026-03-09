"""Integration tests for the sync API endpoints."""

import os
import uuid

import pytest
from app.models import PlatformAccount, PlatformType, SyncLog, SyncStatus
from app.models.enums import DataType
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# SSE stream tests require the `db` hostname (Docker network) because
# _sync_stream creates its own async_session outside the DI system.
_IN_DOCKER = os.path.exists("/.dockerenv") or "db:" in os.environ.get("TEST_DATABASE_URL", "db:")


class TestTriggerSync:
    """POST /api/sync/{account_id}"""

    @pytest.mark.skipif(
        "localhost" in os.environ.get("TEST_DATABASE_URL", ""),
        reason="SSE stream creates own DB session using Docker hostname",
    )
    async def test_trigger_sync_returns_sse_stream(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        """Sync endpoint returns text/event-stream with SSE events."""
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

        response = await authenticated_client.post(
            f"/api/sync/{account.id}"
        )

        # Endpoint returns 200 with SSE content type
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

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
