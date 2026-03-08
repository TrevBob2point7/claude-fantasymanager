import asyncio
import contextlib
import time
from datetime import datetime
from xml.etree import ElementTree

import httpx

from app.platforms.base import PlatformAdapter
from app.platforms.schemas import (
    PlatformLeague,
    PlatformLeagueUser,
    PlatformMatchup,
    PlatformRosterEntry,
    PlatformStanding,
    PlatformTransaction,
    PlatformUser,
)

_CLIENT_TIMEOUT = 30.0


def _current_nfl_season() -> int:
    """Return the current NFL season year. Season rolls over in March."""
    now = datetime.now()
    return now.year if now.month >= 3 else now.year - 1


def _is_player_id(val: str) -> bool:
    """Return True if val looks like an MFL player ID (non-empty, all digits)."""
    return bool(val) and val.isdigit()


def _ensure_list(val: object) -> list:
    """MFL returns a single dict instead of a list when there's only one item."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


class MFLAdapter(PlatformAdapter):
    BASE_URL = "https://api.myfantasyleague.com"

    def __init__(
        self,
        credentials_json: dict | None = None,
        year: int | None = None,
        **kwargs: object,
    ):
        self.year = year or _current_nfl_season()
        self._credentials = credentials_json or {}
        self.cookie = self._credentials.get("cookie")
        self._last_request_time: float = 0.0

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        use_auth: bool = False,
        year: int | None = None,
    ) -> httpx.Response:
        """Make a rate-limited HTTP request to MFL API."""
        # Enforce 1 req/sec rate limit
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)

        effective_year = year or self.year
        url = f"{self.BASE_URL}/{effective_year}{path}"

        headers: dict[str, str] = {}
        if use_auth and self.cookie:
            headers["Cookie"] = self.cookie

        async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT) as client:
            self._last_request_time = time.monotonic()
            resp = await client.request(method, url, params=params, headers=headers)
            resp.raise_for_status()
            return resp

    async def _api_get(
        self,
        export_type: str,
        *,
        params: dict | None = None,
        use_auth: bool = False,
        year: int | None = None,
    ) -> dict:
        """GET from /export with TYPE and JSON=1, return parsed JSON body."""
        all_params = {"TYPE": export_type, "JSON": "1"}
        if params:
            all_params.update(params)
        resp = await self._request(
            "GET", "/export", params=all_params, use_auth=use_auth, year=year
        )
        return resp.json()

    # ── Public API methods ─────────────────────────────────────────────

    async def get_user(self, username: str) -> PlatformUser:
        """Login to MFL and return user info + auth cookie.

        ``username`` is expected to be the MFL username.  The password must
        be provided via ``credentials_json["password"]`` passed to the
        constructor.  On success the adapter's ``self.cookie`` is updated so
        subsequent calls are authenticated.
        """
        # Enforce rate limit
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)

        url = f"{self.BASE_URL}/{self.year}/login"
        password = self._credentials.get("password", "")

        async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT) as client:
            self._last_request_time = time.monotonic()
            resp = await client.post(
                url,
                data={"USERNAME": username, "PASSWORD": password, "XML": "1"},
            )
            resp.raise_for_status()

        # Response is XML: <status cookie_name="MFL_USER_ID" cookie_value="..."/>
        root = ElementTree.fromstring(resp.text)
        status_el = root if root.tag == "status" else root.find("status")
        if status_el is None:
            raise ValueError("MFL login failed: no status element in response")

        cookie_name = status_el.get("cookie_name", "MFL_USER_ID")
        cookie_value = status_el.get("cookie_value", "")
        if not cookie_value:
            raise ValueError("MFL login failed: empty cookie value")

        self.cookie = f"{cookie_name}={cookie_value}"

        return PlatformUser(
            user_id=username,
            username=username,
            display_name=None,
        )

    async def get_leagues(self, user_id: str, season: int) -> list[PlatformLeague]:
        """Get all leagues for the authenticated user in a given season."""
        data = await self._api_get(
            "myleagues", params={"YEAR": str(season)}, use_auth=True, year=season
        )
        leagues_wrapper = data.get("leagues") or {}
        raw_leagues = _ensure_list(leagues_wrapper.get("league"))
        if not raw_leagues:
            return []

        results: list[PlatformLeague] = []
        for lg in raw_leagues:
            results.append(
                PlatformLeague(
                    league_id=str(lg.get("league_id", "")),
                    name=lg.get("name", "Unnamed League"),
                    season=season,
                )
            )
        return results

    async def get_league(self, league_id: str) -> PlatformLeague:
        """Get full league metadata including roster positions and scoring."""
        data = await self._api_get("league", params={"L": league_id})
        league_data = data.get("league") or {}

        roster_positions = self._expand_roster_positions(league_data.get("starters"))
        roster_size_raw = league_data.get("rosterSize")
        roster_size = int(roster_size_raw) if roster_size_raw else None

        # Taxi and IR add to total roster size
        taxi_raw = league_data.get("taxiSquad")
        ir_raw = league_data.get("injuredReserve")
        if roster_size is not None:
            if taxi_raw:
                roster_size += int(taxi_raw)
            if ir_raw:
                roster_size += int(ir_raw)

        scoring_type = await self._detect_scoring_type(league_id)
        league_type = self._detect_league_type(league_data)

        # Build previous_league_id from history
        history = league_data.get("history") or {}
        history_entries = _ensure_list(history.get("league"))
        previous_league_id: str | None = None
        if history_entries:
            years = sorted(
                [int(h["year"]) for h in history_entries if h.get("year")],
                reverse=True,
            )
            current_year_idx = None
            for i, y in enumerate(years):
                if y == self.year:
                    current_year_idx = i
                    break
            if current_year_idx is not None and current_year_idx + 1 < len(years):
                # Same league_id for previous year
                previous_league_id = league_id

        # Store MFL-specific settings for the sync engine
        settings: dict = {
            "startWeek": league_data.get("startWeek", "1"),
            "endWeek": league_data.get("endWeek", "17"),
            "lastRegularSeasonWeek": league_data.get("lastRegularSeasonWeek", "14"),
            "h2h": league_data.get("h2h", ""),
            "bestLineup": league_data.get("bestLineup", ""),
            "draftPlayerPool": league_data.get("draftPlayerPool", ""),
            "taxiSquad": league_data.get("taxiSquad", "0"),
            "injuredReserve": league_data.get("injuredReserve", "0"),
        }

        return PlatformLeague(
            league_id=league_id,
            name=league_data.get("name", "Unnamed League"),
            season=self.year,
            roster_size=roster_size,
            scoring_type=scoring_type,
            league_type=league_type,
            settings=settings,
            previous_league_id=previous_league_id,
            roster_positions=roster_positions,
        )

    async def get_league_users(self, league_id: str) -> list[PlatformLeagueUser]:
        """Extract franchise owners from league metadata."""
        data = await self._api_get("league", params={"L": league_id})
        league_data = data.get("league") or {}
        franchises_wrapper = league_data.get("franchises") or {}
        franchises = _ensure_list(franchises_wrapper.get("franchise"))

        return [
            PlatformLeagueUser(
                user_id=str(f.get("id", "")),
                display_name=f.get("owner_name"),
                team_name=f.get("name"),
            )
            for f in franchises
        ]

    async def get_rosters(self, league_id: str) -> list[PlatformRosterEntry]:
        """Get all team rosters with player status categorization."""
        data = await self._api_get("rosters", params={"L": league_id})
        rosters_wrapper = data.get("rosters") or {}
        franchises = _ensure_list(rosters_wrapper.get("franchise"))

        results: list[PlatformRosterEntry] = []
        for franchise in franchises:
            franchise_id = str(franchise.get("id", ""))
            players = _ensure_list(franchise.get("player"))

            player_ids: list[str] = []
            taxi: list[str] = []

            for p in players:
                pid = str(p.get("id", ""))
                if not pid:
                    continue
                status = p.get("status", "ROSTER")
                if status == "TAXI_SQUAD":
                    taxi.append(pid)
                else:
                    # ROSTER and INJURED_RESERVE both go in main player_ids
                    player_ids.append(pid)

            results.append(
                PlatformRosterEntry(
                    owner_id=franchise_id,
                    roster_id=franchise_id,
                    player_ids=player_ids,
                    starters=[],  # MFL doesn't provide starters in roster endpoint
                    taxi=taxi,
                )
            )
        return results

    async def get_matchups(self, league_id: str, week: int) -> list[PlatformMatchup]:
        """Get matchup pairings and scores for a given week.

        Requires two API calls: ``schedule`` for pairings and
        ``weeklyResults`` for starters/scores.
        """
        # Fetch schedule for pairings
        sched_data = await self._api_get("schedule", params={"L": league_id, "W": str(week)})
        schedule = sched_data.get("schedule") or {}
        weekly_schedule = schedule.get("weeklySchedule") or {}
        matchups_raw = _ensure_list(weekly_schedule.get("matchup"))

        # Build matchup_id -> franchise pairings
        # Each franchise in a matchup gets the same matchup_id
        franchise_matchup_map: dict[str, int] = {}
        for idx, matchup in enumerate(matchups_raw):
            franchises = _ensure_list(matchup.get("franchise"))
            for f in franchises:
                fid = str(f.get("id", ""))
                if fid:
                    franchise_matchup_map[fid] = idx

        # Fetch weekly results for starters and scores
        results_data = await self._api_get("weeklyResults", params={"L": league_id, "W": str(week)})
        weekly_results = results_data.get("weeklyResults") or {}
        result_franchises = _ensure_list(weekly_results.get("franchise"))

        results: list[PlatformMatchup] = []
        for franchise in result_franchises:
            franchise_id = str(franchise.get("id", ""))

            # Parse total points
            points_raw = franchise.get("score")
            points = float(points_raw) if points_raw else None

            # Parse starters from comma-separated string
            starters_str = franchise.get("starters", "")
            starters = [s for s in starters_str.split(",") if s] if starters_str else []

            # Parse individual player scores
            players = _ensure_list(franchise.get("player"))
            starters_points: dict[str, float] = {}
            for p in players:
                pid = str(p.get("id", ""))
                p_status = p.get("status", "")
                p_score = p.get("score")
                if pid and p_status == "starter" and p_score is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        starters_points[pid] = float(p_score)

            matchup_id = franchise_matchup_map.get(franchise_id, 0)

            results.append(
                PlatformMatchup(
                    matchup_id=matchup_id,
                    roster_id=franchise_id,
                    points=points,
                    week=week,
                    starters=starters,
                    starters_points=starters_points,
                )
            )
        return results

    async def get_transactions(self, league_id: str, week: int) -> list[PlatformTransaction]:
        """Get transactions for a given week, parsing MFL's delimited format."""
        data = await self._api_get("transactions", params={"L": league_id, "W": str(week)})
        tx_wrapper = data.get("transactions") or {}
        raw_txs = _ensure_list(tx_wrapper.get("transaction"))

        results: list[PlatformTransaction] = []
        for tx in raw_txs:
            mfl_type = tx.get("type", "")
            timestamp_raw = tx.get("timestamp", "0")
            try:
                timestamp = int(timestamp_raw) * 1000  # MFL uses seconds, convert to ms
            except (ValueError, TypeError):
                timestamp = 0

            if mfl_type == "TRADE":
                added = self._parse_player_ids(tx.get("franchise1_gave_up", ""))
                dropped = self._parse_player_ids(tx.get("franchise2_gave_up", ""))
                roster_ids = []
                f1 = tx.get("franchise")
                f2 = tx.get("franchise2")
                if f1:
                    roster_ids.append(str(f1))
                if f2:
                    roster_ids.append(str(f2))
                results.append(
                    PlatformTransaction(
                        type="trade",
                        player_ids_added=added,
                        player_ids_dropped=dropped,
                        roster_ids=roster_ids,
                        timestamp=timestamp,
                    )
                )
            elif mfl_type in ("FREE_AGENT", "WAIVER", "BBID_WAIVER"):
                tx_str = tx.get("transaction", "")
                added, dropped = self._parse_transaction_string(tx_str)
                franchise_id = tx.get("franchise", "")
                tx_type = "waiver" if "WAIVER" in mfl_type else "add"
                results.append(
                    PlatformTransaction(
                        type=tx_type,
                        player_ids_added=added,
                        player_ids_dropped=dropped,
                        roster_ids=[str(franchise_id)] if franchise_id else [],
                        timestamp=timestamp,
                    )
                )
            elif mfl_type in ("IR", "TAXI"):
                # Roster moves — treat as adds (internal roster movement)
                tx_str = tx.get("transaction", "")
                added, dropped = self._parse_transaction_string(tx_str)
                franchise_id = tx.get("franchise", "")
                results.append(
                    PlatformTransaction(
                        type="add",
                        player_ids_added=added,
                        player_ids_dropped=dropped,
                        roster_ids=[str(franchise_id)] if franchise_id else [],
                        timestamp=timestamp,
                    )
                )

        return results

    async def get_standings(self, league_id: str) -> list[PlatformStanding] | None:
        """Fetch league standings from MFL."""
        data = await self._api_get("leagueStandings", params={"L": league_id})
        standings_wrapper = data.get("leagueStandings") or {}
        franchises = _ensure_list(standings_wrapper.get("franchise"))
        if not franchises:
            return None

        results: list[PlatformStanding] = []
        for f in franchises:
            franchise_id = str(f.get("id", ""))
            if not franchise_id:
                continue
            wins = int(f.get("h2hw", 0))
            losses = int(f.get("h2hl", 0))
            ties = int(f.get("h2ht", 0))
            pf = float(f.get("pf", 0))
            pa = float(f.get("pa", 0))
            results.append(
                PlatformStanding(
                    franchise_id=franchise_id,
                    wins=wins,
                    losses=losses,
                    ties=ties,
                    points_for=pf,
                    points_against=pa,
                )
            )
        return results

    async def get_players_map(self) -> dict[str, dict]:
        """Fetch all MFL players with details. Returns {mfl_id: player_dict}."""
        data = await self._api_get("players", params={"DETAILS": "1"})
        players_wrapper = data.get("players") or {}
        raw_players = _ensure_list(players_wrapper.get("player"))

        result: dict[str, dict] = {}
        for p in raw_players:
            pid = p.get("id", "")
            if pid:
                result[pid] = p
        return result

    # ── Helper methods ─────────────────────────────────────────────────

    def _expand_roster_positions(self, starters_config: dict | None) -> list[str] | None:
        """Convert MFL starter position limits to a flat roster_positions list.

        MFL format: ``{"count": "9", "position": [{"name": "QB", "limit": "1-2"}, ...]}``

        The limit range ``"1-2"`` means 1 guaranteed slot, up to 2 max.  We
        allocate the minimum for each position, then fill the remaining
        starter slots with ``FLEX``.
        """
        if not starters_config:
            return None

        total_starters = int(starters_config.get("count", "0"))
        if total_starters == 0:
            return None

        positions = _ensure_list(starters_config.get("position"))
        if not positions:
            return None

        result: list[str] = []
        for pos in positions:
            name = pos.get("name", "").upper()
            limit = pos.get("limit", "0")

            # Parse limit: can be "2", "1-2", etc.
            min_slots = int(limit.split("-")[0]) if "-" in str(limit) else int(limit)

            result.extend([name] * min_slots)

        # Fill remaining slots with FLEX
        remaining = total_starters - len(result)
        if remaining > 0:
            result.extend(["FLEX"] * remaining)

        return result

    async def _detect_scoring_type(self, league_id: str) -> str:
        """Call the rules endpoint to determine PPR / half-PPR / standard."""
        data = await self._api_get("rules", params={"L": league_id})
        rules_wrapper = data.get("rules") or {}
        position_rules = _ensure_list(rules_wrapper.get("positionRules"))

        # Look for reception points in any position group
        for pos_group in position_rules:
            rules = _ensure_list(pos_group.get("rule"))
            for rule in rules:
                event = rule.get("event") or {}
                event_name = event if isinstance(event, str) else event.get("$t", "")
                points_raw = rule.get("points") or {}
                points_val = (
                    points_raw if isinstance(points_raw, str) else points_raw.get("$t", "0")
                )

                if event_name == "CC":  # CC = Catch/Reception in MFL
                    try:
                        rec_pts = float(points_val)
                    except (ValueError, TypeError):
                        continue
                    scoring_map = {1.0: "ppr", 0.5: "half_ppr", 0.0: "standard"}
                    return scoring_map.get(rec_pts, "custom")

        # No reception rule found — likely standard scoring
        return "standard"

    def _detect_league_type(self, league_data: dict) -> str | None:
        """Infer league type from draftPlayerPool and other settings."""
        draft_pool = league_data.get("draftPlayerPool", "")
        keeper_count = league_data.get("keeperCount", "0")

        if draft_pool in ("Rookie", "Veteran"):
            return "dynasty"
        elif keeper_count and int(keeper_count) > 0:
            return "keeper"
        else:
            # "Both" or empty = redraft
            return "redraft"

    @staticmethod
    def _parse_transaction_string(tx_str: str) -> tuple[list[str], list[str]]:
        """Parse MFL's pipe-delimited transaction string.

        Format: ``"added_id1,added_id2,|dropped_id1,dropped_id2,"``
        The pipe separates added players from dropped players.
        BBID waivers may have an extra pipe segment for bid amount.
        """
        if not tx_str:
            return [], []

        parts = tx_str.split("|")
        added_str = parts[0] if len(parts) > 0 else ""
        dropped_str = parts[1] if len(parts) > 1 else ""

        added = [pid for pid in added_str.split(",") if _is_player_id(pid)]
        dropped = [pid for pid in dropped_str.split(",") if _is_player_id(pid)]
        return added, dropped

    @staticmethod
    def _parse_player_ids(ids_str: str) -> list[str]:
        """Parse a comma-separated list of player IDs, filtering out draft picks."""
        if not ids_str:
            return []
        return [pid for pid in ids_str.split(",") if _is_player_id(pid)]
