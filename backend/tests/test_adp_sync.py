import uuid
from unittest.mock import AsyncMock, Mock, patch

from app.adp.base import ADPRecord
from app.adp.sync import ADPSyncService
from app.models.enums import ADPFormat, Position
from app.models.player import Player
from app.models.player_adp import PlayerADP
from sqlalchemy import select
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


def _make_provider(formats, records):
    """Create a mock ADPProvider with sync supported_formats and async fetch_adp."""
    provider = Mock()
    provider.supported_formats.return_value = formats
    provider.fetch_adp = AsyncMock(return_value=records)
    return provider


class TestADPSyncService:
    """ADPSyncService.sync_adp"""

    async def test_sync_upserts_new_records(self, db_session: AsyncSession):
        player = await _create_player(
            db_session, "Patrick Mahomes", Position.QB, "KC", sleeper_id="4046"
        )

        mock_provider = _make_provider(
            [ADPFormat.ppr],
            [
                ADPRecord(
                    player_name="Patrick Mahomes",
                    position="QB",
                    team="KC",
                    adp=15.0,
                    position_rank=1,
                    sleeper_id="4046",
                    source="test_source",
                    format=ADPFormat.ppr,
                ),
            ],
        )

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[mock_provider]
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["synced"] == 1
        assert result["skipped"] == 0
        assert result["errored"] == 0

        adp_rows = (
            await db_session.execute(
                select(PlayerADP).where(PlayerADP.player_id == player.id)
            )
        ).scalars().all()
        assert len(adp_rows) == 1
        assert float(adp_rows[0].adp) == 15.0
        assert adp_rows[0].source == "test_source"
        assert adp_rows[0].format == ADPFormat.ppr
        assert adp_rows[0].position_rank == 1

    async def test_sync_updates_existing_records(self, db_session: AsyncSession):
        player = await _create_player(
            db_session, "Josh Allen", Position.QB, "BUF", sleeper_id="5001"
        )

        mock_provider = _make_provider(
            [ADPFormat.standard],
            [
                ADPRecord(
                    player_name="Josh Allen",
                    position="QB",
                    team="BUF",
                    adp=10.0,
                    position_rank=2,
                    sleeper_id="5001",
                    source="test_source",
                    format=ADPFormat.standard,
                ),
            ],
        )

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[mock_provider]
        ):
            service = ADPSyncService(db_session)
            await service.sync_adp(season=2025)

        # Update with new ADP value
        mock_provider.fetch_adp.return_value = [
            ADPRecord(
                player_name="Josh Allen",
                position="QB",
                team="BUF",
                adp=5.0,
                position_rank=1,
                sleeper_id="5001",
                source="test_source",
                format=ADPFormat.standard,
            ),
        ]

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[mock_provider]
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["synced"] == 1

        adp_rows = (
            await db_session.execute(
                select(PlayerADP).where(PlayerADP.player_id == player.id)
            )
        ).scalars().all()
        assert len(adp_rows) == 1
        assert float(adp_rows[0].adp) == 5.0
        assert adp_rows[0].position_rank == 1

    async def test_sync_matches_by_sleeper_id(self, db_session: AsyncSession):
        player = await _create_player(
            db_session, "Tyreek Hill", Position.WR, "MIA", sleeper_id="4983"
        )

        mock_provider = _make_provider(
            [ADPFormat.ppr],
            [
                ADPRecord(
                    player_name="Tyreek Hill Misspelled",
                    position="WR",
                    team="MIA",
                    adp=8.0,
                    sleeper_id="4983",
                    source="test_source",
                    format=ADPFormat.ppr,
                ),
            ],
        )

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[mock_provider]
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["synced"] == 1

        adp_rows = (
            await db_session.execute(
                select(PlayerADP).where(PlayerADP.player_id == player.id)
            )
        ).scalars().all()
        assert len(adp_rows) == 1

    async def test_sync_matches_by_name_and_position(self, db_session: AsyncSession):
        player = await _create_player(
            db_session, "Travis Kelce", Position.TE, "KC"
        )

        mock_provider = _make_provider(
            [ADPFormat.ppr],
            [
                ADPRecord(
                    player_name="Travis Kelce",
                    position="TE",
                    team="KC",
                    adp=12.0,
                    source="test_source",
                    format=ADPFormat.ppr,
                ),
            ],
        )

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[mock_provider]
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["synced"] == 1

        adp_rows = (
            await db_session.execute(
                select(PlayerADP).where(PlayerADP.player_id == player.id)
            )
        ).scalars().all()
        assert len(adp_rows) == 1

    async def test_sync_skips_unmatched_players(self, db_session: AsyncSession):
        mock_provider = _make_provider(
            [ADPFormat.standard],
            [
                ADPRecord(
                    player_name="Unknown Player",
                    position="QB",
                    team="FA",
                    adp=200.0,
                    source="test_source",
                    format=ADPFormat.standard,
                ),
            ],
        )

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[mock_provider]
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["synced"] == 0
        assert result["skipped"] == 1

    async def test_sync_handles_provider_fetch_error(self, db_session: AsyncSession):
        provider = Mock()
        provider.supported_formats.return_value = [ADPFormat.ppr]
        provider.fetch_adp = AsyncMock(side_effect=Exception("Connection timeout"))

        with patch(
            "app.adp.sync.get_adp_providers", return_value=[provider]
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["errored"] == 1
        assert result["synced"] == 0

    async def test_sync_multiple_providers(self, db_session: AsyncSession):
        player = await _create_player(
            db_session, "Saquon Barkley", Position.RB, "PHI", sleeper_id="5555"
        )

        mock_sleeper = _make_provider(
            [ADPFormat.ppr],
            [
                ADPRecord(
                    player_name="Saquon Barkley",
                    position="RB",
                    team="PHI",
                    adp=3.0,
                    sleeper_id="5555",
                    source="sleeper",
                    format=ADPFormat.ppr,
                ),
            ],
        )

        mock_ffc = _make_provider(
            [ADPFormat.ppr],
            [
                ADPRecord(
                    player_name="Saquon Barkley",
                    position="RB",
                    team="PHI",
                    adp=4.0,
                    source="ffc",
                    format=ADPFormat.ppr,
                ),
            ],
        )

        with patch(
            "app.adp.sync.get_adp_providers",
            return_value=[mock_sleeper, mock_ffc],
        ):
            service = ADPSyncService(db_session)
            result = await service.sync_adp(season=2025)

        assert result["synced"] == 2

        adp_rows = (
            await db_session.execute(
                select(PlayerADP).where(PlayerADP.player_id == player.id)
            )
        ).scalars().all()
        assert len(adp_rows) == 2


class TestProviderName:
    """ADPSyncService._provider_name"""

    def test_extracts_provider_name(self):
        from app.adp.dynastyprocess import DynastyProcessADPProvider
        from app.adp.ffc import FFCADPProvider
        from app.adp.sleeper import SleeperADPProvider

        assert ADPSyncService._provider_name(SleeperADPProvider()) == "sleeper"
        assert ADPSyncService._provider_name(FFCADPProvider()) == "ffc"
        assert ADPSyncService._provider_name(DynastyProcessADPProvider()) == "dynastyprocess"
