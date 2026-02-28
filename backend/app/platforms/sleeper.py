import httpx

from app.platforms.base import PlatformAdapter
from app.platforms.schemas import (
    PlatformLeague,
    PlatformMatchup,
    PlatformRosterEntry,
    PlatformTransaction,
    PlatformUser,
)

BASE_URL = "https://api.sleeper.app/v1"
_CLIENT_TIMEOUT = 30.0


class SleeperAdapter(PlatformAdapter):
    async def get_players_map(self) -> dict[str, dict]:
        """Fetch all NFL players from Sleeper."""
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
            resp = await client.get("/players/nfl")
            resp.raise_for_status()
            return resp.json()

    async def get_user(self, username: str) -> PlatformUser:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=_CLIENT_TIMEOUT) as client:
            resp = await client.get(f"/user/{username}")
            resp.raise_for_status()
            data = resp.json()
            if not data:
                raise ValueError(f"User '{username}' not found on Sleeper")
            return PlatformUser(
                user_id=str(data["user_id"]),
                username=data.get("username", username),
                display_name=data.get("display_name"),
            )

    async def get_leagues(self, user_id: str, season: int) -> list[PlatformLeague]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=_CLIENT_TIMEOUT) as client:
            resp = await client.get(f"/user/{user_id}/leagues/nfl/{season}")
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []
            leagues = []
            for lg in data:
                scoring = lg.get("scoring_settings", {})
                scoring_type = "custom"
                rec_pts = scoring.get("rec", 0)
                if rec_pts == 1:
                    scoring_type = "ppr"
                elif rec_pts == 0.5:
                    scoring_type = "half_ppr"
                elif rec_pts == 0:
                    scoring_type = "standard"

                # Map Sleeper league type (0=redraft, 1=keeper, 2=dynasty)
                settings = lg.get("settings", {})
                type_code = settings.get("type", 0) if settings else 0
                league_type_map = {0: "redraft", 1: "keeper", 2: "dynasty"}
                league_type = league_type_map.get(type_code)

                leagues.append(
                    PlatformLeague(
                        league_id=str(lg["league_id"]),
                        name=lg.get("name", "Unnamed League"),
                        season=int(lg.get("season", season)),
                        roster_size=lg.get("roster_positions", None) and len(lg["roster_positions"]),
                        scoring_type=scoring_type,
                        league_type=league_type,
                        settings=lg.get("settings"),
                    )
                )
            return leagues

    async def get_rosters(self, league_id: str) -> list[PlatformRosterEntry]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=_CLIENT_TIMEOUT) as client:
            resp = await client.get(f"/league/{league_id}/rosters")
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []
            return [
                PlatformRosterEntry(
                    owner_id=str(r.get("owner_id", r.get("roster_id", ""))),
                    player_ids=[str(p) for p in (r.get("players") or [])],
                    starters=[str(p) for p in (r.get("starters") or [])],
                    taxi=[str(p) for p in (r.get("taxi") or [])],
                )
                for r in data
            ]

    async def get_matchups(self, league_id: str, week: int) -> list[PlatformMatchup]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=_CLIENT_TIMEOUT) as client:
            resp = await client.get(f"/league/{league_id}/matchups/{week}")
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []
            return [
                PlatformMatchup(
                    matchup_id=m.get("matchup_id", 0),
                    roster_id=str(m.get("roster_id", "")),
                    points=m.get("points"),
                    week=week,
                )
                for m in data
            ]

    async def get_transactions(self, league_id: str, week: int) -> list[PlatformTransaction]:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=_CLIENT_TIMEOUT) as client:
            resp = await client.get(f"/league/{league_id}/transactions/{week}")
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []
            transactions = []
            for t in data:
                if t.get("status") != "complete":
                    continue
                tx_type = t.get("type", "add")
                adds = t.get("adds") or {}
                drops = t.get("drops") or {}
                roster_ids = list({str(v) for v in [*adds.values(), *drops.values()] if v})
                transactions.append(
                    PlatformTransaction(
                        type=tx_type if tx_type in ("add", "drop", "trade", "waiver") else "add",
                        player_ids_added=list(adds.keys()),
                        player_ids_dropped=list(drops.keys()),
                        roster_ids=roster_ids,
                        timestamp=t.get("status_updated", 0),
                    )
                )
            return transactions
