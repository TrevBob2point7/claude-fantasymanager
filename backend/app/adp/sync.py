import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adp.base import ADPProvider, ADPRecord
from app.adp.registry import get_adp_providers
from app.models.player import Player
from app.models.player_adp import PlayerADP

logger = logging.getLogger(__name__)


class ADPSyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def sync_adp(
        self,
        season: int,
        sources: list[str] | None = None,
    ) -> dict[str, int]:
        """Sync ADP data from all (or selected) providers.

        Returns dict with keys: synced, skipped, errored.
        """
        providers = get_adp_providers()
        if sources:
            providers = [p for p in providers if self._provider_name(p) in sources]

        # Pre-load player lookup maps
        sleeper_map = await self._build_sleeper_map()
        name_map = await self._build_name_position_map()

        synced = 0
        skipped = 0
        errored = 0

        for provider in providers:
            for fmt in provider.supported_formats():
                try:
                    records = await provider.fetch_adp(season, fmt)
                except Exception:
                    logger.exception(
                        "Failed to fetch ADP from %s for %s",
                        self._provider_name(provider),
                        fmt,
                    )
                    errored += 1
                    continue

                rows = []
                for record in records:
                    player_id = self._match_player(record, sleeper_map, name_map)
                    if player_id is None:
                        skipped += 1
                        continue
                    rows.append({
                        "player_id": player_id,
                        "source": record.source,
                        "format": record.format,
                        "season": season,
                        "adp": min(record.adp, 999999.99),
                        "position_rank": record.position_rank,
                    })

                if rows:
                    try:
                        await self._bulk_upsert(rows)
                        synced += len(rows)
                    except Exception:
                        logger.exception(
                            "Failed to bulk upsert %d ADP rows from %s/%s",
                            len(rows),
                            self._provider_name(provider),
                            fmt,
                        )
                        errored += len(rows)

        await self.db.commit()
        logger.info(
            "ADP sync complete: synced=%d, skipped=%d, errored=%d",
            synced,
            skipped,
            errored,
        )
        return {"synced": synced, "skipped": skipped, "errored": errored}

    async def _build_sleeper_map(self) -> dict[str, "Player"]:
        result = await self.db.execute(
            select(Player).where(Player.sleeper_id.is_not(None))
        )
        return {p.sleeper_id: p for p in result.scalars().all()}  # type: ignore[misc]

    async def _build_name_position_map(self) -> dict[tuple[str, str | None], "Player"]:
        result = await self.db.execute(select(Player))
        mapping: dict[tuple[str, str | None], Player] = {}
        for p in result.scalars().all():
            pos_val = p.position.value if p.position else None
            key = (p.full_name.lower(), pos_val)
            mapping[key] = p
        return mapping

    def _match_player(
        self,
        record: ADPRecord,
        sleeper_map: dict[str, "Player"],
        name_map: dict[tuple[str, str | None], "Player"],
    ) -> "str | None":
        """Match an ADP record to a player. Returns player UUID or None."""
        # Priority 1: sleeper_id exact match
        if record.sleeper_id and record.sleeper_id in sleeper_map:
            return str(sleeper_map[record.sleeper_id].id)

        # Priority 2: name + position exact match
        key = (record.player_name.lower(), record.position)
        if key in name_map:
            return str(name_map[key].id)

        # No match
        return None

    async def _bulk_upsert(self, rows: list[dict]) -> None:
        """Bulk upsert ADP rows in a single INSERT ... ON CONFLICT statement."""
        insert_stmt = pg_insert(PlayerADP).values(rows)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["player_id", "source", "format", "season"],
            set_={
                "adp": insert_stmt.excluded.adp,
                "position_rank": insert_stmt.excluded.position_rank,
            },
        )
        await self.db.execute(stmt)

    @staticmethod
    def _provider_name(provider: ADPProvider) -> str:
        return type(provider).__name__.replace("ADPProvider", "").lower()
