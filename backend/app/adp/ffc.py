import logging

import httpx

from app.adp.base import ADPProvider, ADPRecord
from app.models.enums import ADPFormat

logger = logging.getLogger(__name__)

BASE_URL = "https://fantasyfootballcalculator.com"

_FORMAT_MAP: dict[ADPFormat, str] = {
    ADPFormat.standard: "standard",
    ADPFormat.half_ppr: "half-ppr",
    ADPFormat.ppr: "ppr",
    ADPFormat.dynasty: "dynasty",
    ADPFormat.superflex: "superflex",
    ADPFormat.two_qb: "2qb",
}


class FFCADPProvider(ADPProvider):
    """Fetches ADP data from Fantasy Football Calculator."""

    def supported_formats(self) -> list[ADPFormat]:
        return [
            ADPFormat.standard,
            ADPFormat.half_ppr,
            ADPFormat.ppr,
            ADPFormat.dynasty,
            ADPFormat.superflex,
            ADPFormat.two_qb,
        ]

    async def fetch_adp(self, season: int, format: ADPFormat) -> list[ADPRecord]:
        ffc_format = _FORMAT_MAP.get(format)
        if ffc_format is None:
            return []

        url = f"/api/v1/adp/{ffc_format}"
        params = {"teams": 12, "year": season}

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        players = data.get("players", [])
        records: list[ADPRecord] = []
        for p in players:
            name = p.get("name", "")
            if not name:
                continue

            records.append(
                ADPRecord(
                    player_name=name,
                    position=p.get("position"),
                    team=p.get("team"),
                    adp=float(p.get("adp", 0)),
                    position_rank=p.get("positionRank"),
                    source="ffc",
                    format=format,
                )
            )

        logger.info("FFC ADP: fetched %d records for %s/%d", len(records), format, season)
        return records
