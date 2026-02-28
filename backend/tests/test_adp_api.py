import uuid
from unittest.mock import AsyncMock, patch

from app.models.enums import ADPFormat, Position
from app.models.player import Player
from app.models.player_adp import PlayerADP
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_player(
    db: AsyncSession,
    full_name: str,
    position: Position,
    team: str = "NYJ",
    sleeper_id: str | None = None,
) -> Player:
    player = Player(
        id=uuid.uuid4(),
        full_name=full_name,
        position=position,
        team=team,
        sleeper_id=sleeper_id,
    )
    db.add(player)
    await db.commit()
    await db.refresh(player)
    return player


async def _create_adp_entry(
    db: AsyncSession,
    player_id: uuid.UUID,
    source: str = "sleeper",
    format: ADPFormat = ADPFormat.ppr,
    season: int = 2025,
    adp: float = 10.0,
    position_rank: int | None = None,
) -> PlayerADP:
    entry = PlayerADP(
        player_id=player_id,
        source=source,
        format=format,
        season=season,
        adp=adp,
        position_rank=position_rank,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


class TestSyncADPEndpoint:
    """POST /api/adp/sync"""

    async def test_sync_success(self, authenticated_client: AsyncClient):
        mock_result = {"synced": 5, "skipped": 2, "errored": 0}
        with patch(
            "app.api.adp.ADPSyncService"
        ) as MockService:
            instance = MockService.return_value
            instance.sync_adp = AsyncMock(return_value=mock_result)

            response = await authenticated_client.post(
                "/api/adp/sync", params={"season": 2025}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["synced"] == 5
        assert data["skipped"] == 2
        assert data["errored"] == 0

    async def test_sync_with_sources_filter(self, authenticated_client: AsyncClient):
        mock_result = {"synced": 3, "skipped": 0, "errored": 0}
        with patch(
            "app.api.adp.ADPSyncService"
        ) as MockService:
            instance = MockService.return_value
            instance.sync_adp = AsyncMock(return_value=mock_result)

            response = await authenticated_client.post(
                "/api/adp/sync",
                params={"season": 2025, "sources": ["sleeper", "ffc"]},
            )

        assert response.status_code == 200
        instance.sync_adp.assert_called_once_with(
            season=2025, sources=["sleeper", "ffc"]
        )

    async def test_sync_unauthenticated(self, client: AsyncClient):
        response = await client.post("/api/adp/sync", params={"season": 2025})
        assert response.status_code in (401, 403)


class TestPlayerADPHistoryEndpoint:
    """GET /api/adp/players/{player_id}/history"""

    async def test_get_history_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        player = await _create_player(
            db_session, "Lamar Jackson", Position.QB, "BAL"
        )
        await _create_adp_entry(
            db_session, player.id, source="sleeper", format=ADPFormat.ppr,
            season=2025, adp=20.0, position_rank=5,
        )
        await _create_adp_entry(
            db_session, player.id, source="ffc", format=ADPFormat.ppr,
            season=2025, adp=18.5, position_rank=4,
        )

        response = await authenticated_client.get(
            f"/api/adp/players/{player.id}/history"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(entry["player_id"] == str(player.id) for entry in data)
        sources = {entry["source"] for entry in data}
        assert sources == {"sleeper", "ffc"}

    async def test_get_history_filter_by_format(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        player = await _create_player(
            db_session, "Derrick Henry", Position.RB, "BAL"
        )
        await _create_adp_entry(
            db_session, player.id, format=ADPFormat.ppr, season=2025, adp=15.0,
        )
        await _create_adp_entry(
            db_session, player.id, format=ADPFormat.standard, season=2025, adp=12.0,
        )

        response = await authenticated_client.get(
            f"/api/adp/players/{player.id}/history",
            params={"format": "ppr"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["format"] == "ppr"

    async def test_get_history_empty(
        self,
        authenticated_client: AsyncClient,
    ):
        fake_id = uuid.uuid4()
        response = await authenticated_client.get(
            f"/api/adp/players/{fake_id}/history"
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_history_unauthenticated(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/adp/players/{fake_id}/history")
        assert response.status_code in (401, 403)

    async def test_get_history_ordered_by_season_desc(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        player = await _create_player(
            db_session, "Davante Adams", Position.WR, "NYJ"
        )
        await _create_adp_entry(
            db_session, player.id, source="ffc", season=2024, adp=20.0,
        )
        await _create_adp_entry(
            db_session, player.id, source="ffc", season=2025, adp=35.0,
        )

        response = await authenticated_client.get(
            f"/api/adp/players/{player.id}/history"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Should be ordered by season descending
        assert data[0]["season"] == 2025
        assert data[1]["season"] == 2024
