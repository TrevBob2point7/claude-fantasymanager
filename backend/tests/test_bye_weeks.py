"""Contract tests for bye week sync (Phase 0.2).

These tests define the expected behavior for the bye week sync module.
They will fail until the module and model are implemented (Phases 1.2 + 5).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These imports will fail until Phase 1.2 (model) and Phase 5 (sync module)
# are implemented — that's intentional for contract tests.
from app.models.team_bye_week import TeamByeWeek
from app.sync.bye_weeks import sync_bye_weeks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Sample ESPN API response for proTeamSchedules_wl view
ESPN_RESPONSE = {
    "settings": {
        "proTeams": [
            {"id": 1, "abbrev": "Atl", "byeWeek": 11},
            {"id": 2, "abbrev": "Buf", "byeWeek": 12},
            {"id": 3, "abbrev": "chi", "byeWeek": 7},
            # FA entry should be skipped
            {"id": 0, "abbrev": "FA", "byeWeek": 0},
        ]
    }
}


@pytest.mark.asyncio(loop_scope="session")
class TestSyncByeWeeks:
    """Tests for the bye week sync module."""

    async def test_sync_bye_weeks_parses_espn_response(self, db_session: AsyncSession):
        """Mock ESPN API response with 2-3 teams, verify team_bye_weeks rows
        are created with correct season, team (uppercased), bye_week."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ESPN_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch("app.sync.bye_weeks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            await sync_bye_weeks(db_session, 2025)

        result = await db_session.execute(
            select(TeamByeWeek).where(TeamByeWeek.season == 2025)
        )
        rows = result.scalars().all()

        # Should have 3 teams (FA excluded)
        assert len(rows) == 3

        by_team = {r.team: r for r in rows}
        assert by_team["ATL"].bye_week == 11
        assert by_team["BUF"].bye_week == 12
        assert by_team["CHI"].bye_week == 7

    async def test_sync_bye_weeks_normalizes_team_abbrev(
        self, db_session: AsyncSession
    ):
        """ESPN returns 'Atl', DB stores 'ATL'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "settings": {
                "proTeams": [
                    {"id": 1, "abbrev": "Atl", "byeWeek": 11},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.sync.bye_weeks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            await sync_bye_weeks(db_session, 2025)

        result = await db_session.execute(
            select(TeamByeWeek).where(
                TeamByeWeek.season == 2025, TeamByeWeek.team == "ATL"
            )
        )
        row = result.scalar_one_or_none()
        assert row is not None
        assert row.team == "ATL"

    async def test_sync_bye_weeks_skips_fa_entry(self, db_session: AsyncSession):
        """FA team with byeWeek=0 is excluded."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "settings": {
                "proTeams": [
                    {"id": 1, "abbrev": "KC", "byeWeek": 6},
                    {"id": 0, "abbrev": "FA", "byeWeek": 0},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.sync.bye_weeks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            await sync_bye_weeks(db_session, 2025)

        result = await db_session.execute(
            select(TeamByeWeek).where(TeamByeWeek.season == 2025)
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].team == "KC"
        # Ensure FA was not inserted
        fa_result = await db_session.execute(
            select(TeamByeWeek).where(
                TeamByeWeek.season == 2025, TeamByeWeek.team == "FA"
            )
        )
        assert fa_result.scalar_one_or_none() is None

    async def test_sync_bye_weeks_upserts_on_conflict(
        self, db_session: AsyncSession
    ):
        """Running sync twice for same season updates existing rows."""
        mock_response_v1 = MagicMock()
        mock_response_v1.status_code = 200
        mock_response_v1.json.return_value = {
            "settings": {
                "proTeams": [
                    {"id": 1, "abbrev": "KC", "byeWeek": 6},
                ]
            }
        }
        mock_response_v1.raise_for_status = MagicMock()

        mock_response_v2 = MagicMock()
        mock_response_v2.status_code = 200
        mock_response_v2.json.return_value = {
            "settings": {
                "proTeams": [
                    {"id": 1, "abbrev": "KC", "byeWeek": 10},  # Changed bye week
                ]
            }
        }
        mock_response_v2.raise_for_status = MagicMock()

        with patch("app.sync.bye_weeks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # First sync
            mock_client.get.return_value = mock_response_v1
            await sync_bye_weeks(db_session, 2025)

            # Second sync with updated bye week
            mock_client.get.return_value = mock_response_v2
            await sync_bye_weeks(db_session, 2025)

        result = await db_session.execute(
            select(TeamByeWeek).where(
                TeamByeWeek.season == 2025, TeamByeWeek.team == "KC"
            )
        )
        rows = result.scalars().all()
        # Should have exactly 1 row (upserted, not duplicated)
        assert len(rows) == 1
        assert rows[0].bye_week == 10  # Updated value

    async def test_sync_bye_weeks_handles_espn_failure(
        self, db_session: AsyncSession
    ):
        """HTTP error from ESPN raises gracefully (doesn't crash caller)."""
        import httpx

        with patch("app.sync.bye_weeks.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.HTTPStatusError(
                "503 Service Unavailable",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(503),
            )
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await sync_bye_weeks(db_session, 2025)
