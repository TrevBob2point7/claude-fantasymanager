import csv
import io
import logging

import httpx

from app.adp.base import ADPProvider, ADPRecord
from app.models.enums import ADPFormat

logger = logging.getLogger(__name__)

CSV_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
)


class DynastyProcessADPProvider(ADPProvider):
    """Fetches dynasty player values from DynastyProcess GitHub CSV data."""

    def supported_formats(self) -> list[ADPFormat]:
        return [ADPFormat.dynasty]

    async def fetch_adp(self, season: int, format: ADPFormat) -> list[ADPRecord]:
        if format != ADPFormat.dynasty:
            return []

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(CSV_URL)
            resp.raise_for_status()
            text = resp.text

        reader = csv.DictReader(io.StringIO(text))
        records: list[ADPRecord] = []
        for row in reader:
            name = row.get("player", "")
            if not name:
                continue

            # Use value_1qb as ADP proxy
            value_str = row.get("value_1qb", "")
            if not value_str:
                continue

            try:
                value = float(value_str)
            except ValueError:
                continue

            sleeper_id = row.get("sleeper_id", "") or None

            records.append(
                ADPRecord(
                    player_name=name,
                    position=row.get("pos"),
                    team=row.get("team"),
                    adp=value,
                    sleeper_id=sleeper_id,
                    source="dynastyprocess",
                    format=format,
                )
            )

        records.sort(key=lambda r: r.adp, reverse=True)  # Higher value = better
        # Assign position rank after sorting
        pos_counts: dict[str, int] = {}
        for r in records:
            if r.position:
                pos_counts[r.position] = pos_counts.get(r.position, 0) + 1
                r.position_rank = pos_counts[r.position]

        logger.info("DynastyProcess ADP: fetched %d records", len(records))
        return records
