import logging

import httpx

from app.adp.base import ADPProvider, ADPRecord
from app.models.enums import ADPFormat

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sleeper.app/v1"


class SleeperADPProvider(ADPProvider):
    """Fetches ADP data from Sleeper's player database using search_rank."""

    def supported_formats(self) -> list[ADPFormat]:
        return [ADPFormat.standard, ADPFormat.half_ppr, ADPFormat.ppr, ADPFormat.dynasty]

    async def fetch_adp(self, season: int, format: ADPFormat) -> list[ADPRecord]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
            resp = await client.get("/players/nfl")
            resp.raise_for_status()
            players = resp.json()

        records: list[ADPRecord] = []
        for sleeper_id, data in players.items():
            if not isinstance(data, dict):
                continue

            # Skip inactive/non-NFL players
            if data.get("active") is not True:
                continue

            position = data.get("position")
            if position not in ("QB", "RB", "WR", "TE", "K", "DEF"):
                continue

            rank = data.get("search_rank")
            if rank is None or rank <= 0:
                continue

            full_name = (
                f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                or data.get("full_name", "Unknown")
            )

            records.append(
                ADPRecord(
                    player_name=full_name,
                    position=position,
                    team=data.get("team"),
                    adp=float(rank),
                    sleeper_id=sleeper_id,
                    source="sleeper",
                    format=format,
                )
            )

        records.sort(key=lambda r: r.adp)
        logger.info("Sleeper ADP: fetched %d records for %s", len(records), format)
        return records
