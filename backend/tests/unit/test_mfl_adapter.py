"""Unit tests for the MFL platform adapter with mocked HTTP via respx."""

from unittest.mock import patch

import httpx
import pytest
import respx
from app.platforms.mfl import MFLAdapter

BASE_URL = "https://api.myfantasyleague.com"
YEAR = 2025


def _url(path: str) -> str:
    return f"{BASE_URL}/{YEAR}{path}"


def _export_route(export_type: str, **extra_params: str):
    """Build a respx route matching an MFL export endpoint."""
    params = {"TYPE": export_type, "JSON": "1", **extra_params}
    return respx.get(_url("/export")).mock(
        side_effect=lambda req: (
            httpx.Response(200, json={}) if dict(req.url.params) != params else None
        )
    )


class TestGetLeagues:
    async def test_get_leagues(self):
        adapter = MFLAdapter(credentials_json={"cookie": "MFL_USER_ID=abc123"}, year=YEAR)
        mock_resp = {
            "leagues": {
                "league": [
                    {"league_id": "40750", "name": "Dynasty League"},
                    {"league_id": "12345", "name": "Redraft League"},
                ]
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            leagues = await adapter.get_leagues("testuser", YEAR)

        assert len(leagues) == 2
        assert leagues[0].league_id == "40750"
        assert leagues[0].name == "Dynasty League"
        assert leagues[0].season == YEAR
        assert leagues[1].league_id == "12345"

    async def test_get_leagues_single_league(self):
        """MFL returns a dict instead of a list for a single league."""
        adapter = MFLAdapter(credentials_json={"cookie": "MFL_USER_ID=abc123"}, year=YEAR)
        mock_resp = {"leagues": {"league": {"league_id": "40750", "name": "Only League"}}}
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            leagues = await adapter.get_leagues("testuser", YEAR)

        assert len(leagues) == 1
        assert leagues[0].league_id == "40750"

    async def test_get_leagues_empty(self):
        adapter = MFLAdapter(credentials_json={"cookie": "MFL_USER_ID=abc123"}, year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json={"leagues": {}}))
            leagues = await adapter.get_leagues("testuser", YEAR)

        assert leagues == []


class TestGetLeague:
    async def test_get_league(self):
        """get_league calls league + rules endpoints and returns full metadata."""
        adapter = MFLAdapter(year=YEAR)

        league_resp = {
            "league": {
                "id": "40750",
                "name": "Welcome! Everything is Fine.",
                "rosterSize": "21",
                "taxiSquad": "14",
                "injuredReserve": "5",
                "starters": {
                    "count": "9",
                    "position": [
                        {"name": "QB", "limit": "1"},
                        {"name": "RB", "limit": "2"},
                        {"name": "WR", "limit": "2"},
                        {"name": "TE", "limit": "1"},
                    ],
                },
                "draftPlayerPool": "Rookie",
                "startWeek": "1",
                "endWeek": "17",
                "lastRegularSeasonWeek": "14",
            }
        }
        rules_resp = {
            "rules": {
                "positionRules": [
                    {
                        "rule": [
                            {"event": "CC", "points": "1"},
                        ]
                    }
                ]
            }
        }

        call_count = 0

        async def mock_handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            params = dict(request.url.params)
            if params.get("TYPE") == "league":
                return httpx.Response(200, json=league_resp)
            elif params.get("TYPE") == "rules":
                return httpx.Response(200, json=rules_resp)
            return httpx.Response(404)

        async with respx.mock:
            respx.get(_url("/export")).mock(side_effect=mock_handler)
            league = await adapter.get_league("40750")

        assert league.league_id == "40750"
        assert league.name == "Welcome! Everything is Fine."
        assert league.season == YEAR
        assert league.roster_size == 40  # 21 + 14 + 5
        assert league.scoring_type == "ppr"
        assert league.league_type == "dynasty"
        # Two API calls: league + rules
        assert call_count == 2

    async def test_get_league_roster_positions(self):
        """Verify _expand_roster_positions handles limit ranges correctly."""
        adapter = MFLAdapter(year=YEAR)

        # QB 1-2, RB 1-6, WR 1-6, TE 1-6 with count=9
        starters_config = {
            "count": "9",
            "position": [
                {"name": "QB", "limit": "1-2"},
                {"name": "RB", "limit": "1-6"},
                {"name": "WR", "limit": "1-6"},
                {"name": "TE", "limit": "1-6"},
            ],
        }
        positions = adapter._expand_roster_positions(starters_config)

        assert positions is not None
        assert len(positions) == 9
        # Min slots: QB=1, RB=1, WR=1, TE=1 = 4 fixed, 5 FLEX
        assert positions.count("QB") == 1
        assert positions.count("RB") == 1
        assert positions.count("WR") == 1
        assert positions.count("TE") == 1
        assert positions.count("FLEX") == 5

    async def test_get_league_roster_positions_no_flex(self):
        """When min slots exactly fill count, no FLEX is added."""
        adapter = MFLAdapter(year=YEAR)
        starters_config = {
            "count": "4",
            "position": [
                {"name": "QB", "limit": "1"},
                {"name": "RB", "limit": "2"},
                {"name": "WR", "limit": "1"},
            ],
        }
        positions = adapter._expand_roster_positions(starters_config)

        assert positions == ["QB", "RB", "RB", "WR"]

    async def test_get_league_roster_positions_none(self):
        adapter = MFLAdapter(year=YEAR)
        assert adapter._expand_roster_positions(None) is None
        assert adapter._expand_roster_positions({}) is None
        assert adapter._expand_roster_positions({"count": "0"}) is None


class TestGetLeagueUsers:
    async def test_get_league_users(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "league": {
                "franchises": {
                    "franchise": [
                        {"id": "0001", "name": "Team Alpha", "owner_name": "Alice"},
                        {"id": "0002", "name": "Team Beta", "owner_name": "Bob"},
                    ]
                }
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            users = await adapter.get_league_users("40750")

        assert len(users) == 2
        assert users[0].user_id == "0001"
        assert users[0].display_name == "Alice"
        assert users[0].team_name == "Team Alpha"
        assert users[1].user_id == "0002"

    async def test_get_league_users_empty(self):
        adapter = MFLAdapter(year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json={"league": {}}))
            users = await adapter.get_league_users("40750")

        assert users == []


class TestGetRosters:
    async def test_get_rosters(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "rosters": {
                "franchise": [
                    {
                        "id": "0001",
                        "player": [
                            {"id": "14777", "status": "ROSTER"},
                            {"id": "15331", "status": "TAXI_SQUAD"},
                            {"id": "13590", "status": "INJURED_RESERVE"},
                        ],
                    },
                    {
                        "id": "0002",
                        "player": [
                            {"id": "10700", "status": "ROSTER"},
                            {"id": "16150", "status": "ROSTER"},
                        ],
                    },
                ]
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            rosters = await adapter.get_rosters("40750")

        assert len(rosters) == 2
        # First franchise: 14777 + 13590 in player_ids (ROSTER and IR), 15331 in taxi
        assert rosters[0].owner_id == "0001"
        assert "14777" in rosters[0].player_ids
        assert "13590" in rosters[0].player_ids
        assert rosters[0].taxi == ["15331"]
        assert rosters[0].starters == []
        # Second franchise
        assert len(rosters[1].player_ids) == 2
        assert rosters[1].taxi == []

    async def test_get_rosters_empty(self):
        adapter = MFLAdapter(year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json={"rosters": {}}))
            rosters = await adapter.get_rosters("40750")

        assert rosters == []


class TestGetMatchups:
    async def test_get_matchups(self):
        adapter = MFLAdapter(year=YEAR)

        schedule_resp = {
            "schedule": {
                "weeklySchedule": {
                    "week": "1",
                    "matchup": [
                        {
                            "franchise": [
                                {"id": "0001", "isHome": "1"},
                                {"id": "0002", "isHome": "0"},
                            ]
                        },
                        {
                            "franchise": [
                                {"id": "0003", "isHome": "1"},
                                {"id": "0004", "isHome": "0"},
                            ]
                        },
                    ],
                }
            }
        }
        results_resp = {
            "weeklyResults": {
                "franchise": [
                    {
                        "id": "0001",
                        "score": "120.50",
                        "starters": "14777,15331",
                        "player": [
                            {"id": "14777", "status": "starter", "score": "25.3"},
                            {"id": "15331", "status": "starter", "score": "18.7"},
                        ],
                    },
                    {
                        "id": "0002",
                        "score": "98.20",
                        "starters": "10700",
                        "player": [
                            {"id": "10700", "status": "starter", "score": "30.0"},
                        ],
                    },
                    {
                        "id": "0003",
                        "score": "110.00",
                        "starters": "",
                        "player": [],
                    },
                    {
                        "id": "0004",
                        "score": "105.75",
                        "starters": "",
                        "player": [],
                    },
                ]
            }
        }

        async def mock_handler(request: httpx.Request):
            params = dict(request.url.params)
            if params.get("TYPE") == "schedule":
                return httpx.Response(200, json=schedule_resp)
            elif params.get("TYPE") == "weeklyResults":
                return httpx.Response(200, json=results_resp)
            return httpx.Response(404)

        async with respx.mock:
            respx.get(_url("/export")).mock(side_effect=mock_handler)
            matchups = await adapter.get_matchups("40750", 1)

        assert len(matchups) == 4

        # Verify matchup IDs group correctly
        team_0001 = next(m for m in matchups if m.roster_id == "0001")
        team_0002 = next(m for m in matchups if m.roster_id == "0002")
        assert team_0001.matchup_id == team_0002.matchup_id

        team_0003 = next(m for m in matchups if m.roster_id == "0003")
        team_0004 = next(m for m in matchups if m.roster_id == "0004")
        assert team_0003.matchup_id == team_0004.matchup_id
        assert team_0001.matchup_id != team_0003.matchup_id

        # Verify scores
        assert team_0001.points == 120.50
        assert team_0002.points == 98.20
        assert team_0001.week == 1

        # Verify starters
        assert team_0001.starters == ["14777", "15331"]
        assert team_0001.starters_points["14777"] == 25.3
        assert team_0001.starters_points["15331"] == 18.7

    async def test_get_matchups_empty(self):
        adapter = MFLAdapter(year=YEAR)

        async def mock_handler(request: httpx.Request):
            return httpx.Response(200, json={})

        async with respx.mock:
            respx.get(_url("/export")).mock(side_effect=mock_handler)
            matchups = await adapter.get_matchups("40750", 1)

        assert matchups == []


class TestGetTransactions:
    async def test_free_agent(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "transactions": {
                "transaction": {
                    "type": "FREE_AGENT",
                    "franchise": "0003",
                    "transaction": "16641,|15289,",
                    "timestamp": "1700000",
                }
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            txns = await adapter.get_transactions("40750", 1)

        assert len(txns) == 1
        assert txns[0].type == "add"
        assert txns[0].player_ids_added == ["16641"]
        assert txns[0].player_ids_dropped == ["15289"]
        assert txns[0].roster_ids == ["0003"]
        assert txns[0].timestamp == 1700000000  # seconds * 1000

    async def test_trade(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "transactions": {
                "transaction": {
                    "type": "TRADE",
                    "franchise": "0001",
                    "franchise2": "0003",
                    "franchise1_gave_up": "14777,FP_0001_2025_3",
                    "franchise2_gave_up": "15331,13590",
                    "timestamp": "1700000",
                }
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            txns = await adapter.get_transactions("40750", 1)

        assert len(txns) == 1
        assert txns[0].type == "trade"
        # FP_ draft picks should be filtered out
        assert txns[0].player_ids_added == ["14777"]
        assert txns[0].player_ids_dropped == ["15331", "13590"]
        assert "0001" in txns[0].roster_ids
        assert "0003" in txns[0].roster_ids

    async def test_bbid_waiver(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "transactions": {
                "transaction": {
                    "type": "BBID_WAIVER",
                    "franchise": "0005",
                    "transaction": "13940,|0.00|",
                    "timestamp": "1700000",
                }
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            txns = await adapter.get_transactions("40750", 1)

        assert len(txns) == 1
        assert txns[0].type == "waiver"
        assert txns[0].player_ids_added == ["13940"]

    async def test_transactions_empty(self):
        adapter = MFLAdapter(year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(
                return_value=httpx.Response(200, json={"transactions": {}})
            )
            txns = await adapter.get_transactions("40750", 1)

        assert txns == []


class TestDetectScoringType:
    async def test_ppr(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {"rules": {"positionRules": [{"rule": [{"event": "CC", "points": "1"}]}]}}
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            result = await adapter._detect_scoring_type("40750")

        assert result == "ppr"

    async def test_half_ppr(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {"rules": {"positionRules": [{"rule": [{"event": "CC", "points": "0.5"}]}]}}
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            result = await adapter._detect_scoring_type("40750")

        assert result == "half_ppr"

    async def test_standard(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {"rules": {"positionRules": [{"rule": [{"event": "CC", "points": "0"}]}]}}
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            result = await adapter._detect_scoring_type("40750")

        assert result == "standard"

    async def test_no_reception_rule(self):
        """No CC rule in any position group -> standard."""
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {"rules": {"positionRules": [{"rule": [{"event": "PC", "points": "0.04"}]}]}}
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            result = await adapter._detect_scoring_type("40750")

        assert result == "standard"

    async def test_nested_event_format(self):
        """MFL may nest event in a dict with $t key."""
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "rules": {
                "positionRules": [
                    {
                        "rule": [
                            {
                                "event": {"$t": "CC"},
                                "points": {"$t": "0.5"},
                            }
                        ]
                    }
                ]
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            result = await adapter._detect_scoring_type("40750")

        assert result == "half_ppr"


class TestDetectLeagueType:
    def test_dynasty_rookie_pool(self):
        adapter = MFLAdapter(year=YEAR)
        assert adapter._detect_league_type({"draftPlayerPool": "Rookie"}) == "dynasty"

    def test_dynasty_veteran_pool(self):
        adapter = MFLAdapter(year=YEAR)
        assert adapter._detect_league_type({"draftPlayerPool": "Veteran"}) == "dynasty"

    def test_keeper(self):
        adapter = MFLAdapter(year=YEAR)
        result = adapter._detect_league_type(
            {
                "draftPlayerPool": "Both",
                "keeperCount": "5",
            }
        )
        assert result == "keeper"

    def test_redraft(self):
        adapter = MFLAdapter(year=YEAR)
        assert adapter._detect_league_type({"draftPlayerPool": "Both"}) == "redraft"
        assert adapter._detect_league_type({}) == "redraft"


class TestEmptyResponses:
    async def test_empty_league(self):
        adapter = MFLAdapter(year=YEAR)
        rules_resp = {"rules": {}}

        async def mock_handler(request: httpx.Request):
            params = dict(request.url.params)
            if params.get("TYPE") == "league":
                return httpx.Response(200, json={"league": {}})
            elif params.get("TYPE") == "rules":
                return httpx.Response(200, json=rules_resp)
            return httpx.Response(404)

        async with respx.mock:
            respx.get(_url("/export")).mock(side_effect=mock_handler)
            league = await adapter.get_league("40750")

        assert league.league_id == "40750"
        assert league.name == "Unnamed League"
        assert league.roster_positions is None

    async def test_empty_rosters(self):
        adapter = MFLAdapter(year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json={"rosters": {}}))
            rosters = await adapter.get_rosters("40750")

        assert rosters == []

    async def test_empty_matchups(self):
        adapter = MFLAdapter(year=YEAR)

        async def mock_handler(request: httpx.Request):
            return httpx.Response(200, json={})

        async with respx.mock:
            respx.get(_url("/export")).mock(side_effect=mock_handler)
            matchups = await adapter.get_matchups("40750", 1)

        assert matchups == []

    async def test_empty_transactions(self):
        adapter = MFLAdapter(year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(
                return_value=httpx.Response(200, json={"transactions": {}})
            )
            txns = await adapter.get_transactions("40750", 1)

        assert txns == []


class TestRateLimiting:
    async def test_rate_limiting_enforces_delay(self):
        """Verify that requests are delayed when called too quickly."""
        adapter = MFLAdapter(year=YEAR)
        adapter._last_request_time = 0.0

        sleep_calls = []

        async def mock_sleep(duration):
            sleep_calls.append(duration)

        # Simulate a recent request by setting _last_request_time
        with (
            patch("time.monotonic", side_effect=[100.5, 100.5, 101.0]),
            patch("asyncio.sleep", side_effect=mock_sleep),
        ):
            adapter._last_request_time = 100.0
            async with respx.mock:
                respx.get(_url("/export")).mock(
                    return_value=httpx.Response(200, json={"leagues": {}})
                )
                await adapter.get_leagues("testuser", YEAR)

        # Should have slept for the remaining time
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == pytest.approx(0.5, abs=0.01)

    async def test_no_rate_limit_delay_when_enough_time_elapsed(self):
        """No sleep when enough time has passed since last request."""
        adapter = MFLAdapter(year=YEAR)

        sleep_calls = []

        async def mock_sleep(duration):
            sleep_calls.append(duration)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            # Default _last_request_time is 0.0, so monotonic() will always be > 1s ahead
            async with respx.mock:
                respx.get(_url("/export")).mock(
                    return_value=httpx.Response(200, json={"leagues": {}})
                )
                await adapter.get_leagues("testuser", YEAR)

        assert len(sleep_calls) == 0


class TestGetPlayersMap:
    async def test_get_players_map(self):
        adapter = MFLAdapter(year=YEAR)
        mock_resp = {
            "players": {
                "player": [
                    {
                        "id": "14777",
                        "name": "Allen, Josh",
                        "position": "QB",
                        "team": "BUF",
                    },
                    {
                        "id": "13604",
                        "name": "McCaffrey, Christian",
                        "position": "RB",
                        "team": "SF",
                    },
                ]
            }
        }
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json=mock_resp))
            players = await adapter.get_players_map()

        assert len(players) == 2
        assert players["14777"]["name"] == "Allen, Josh"
        assert players["14777"]["position"] == "QB"
        assert players["13604"]["team"] == "SF"

    async def test_get_players_map_empty(self):
        adapter = MFLAdapter(year=YEAR)
        async with respx.mock:
            respx.get(_url("/export")).mock(return_value=httpx.Response(200, json={"players": {}}))
            players = await adapter.get_players_map()

        assert players == {}


class TestTransactionParsing:
    """Test static helper methods for transaction string parsing."""

    def test_parse_transaction_string(self):
        added, dropped = MFLAdapter._parse_transaction_string("16641,|15289,")
        assert added == ["16641"]
        assert dropped == ["15289"]

    def test_parse_transaction_string_multiple(self):
        added, dropped = MFLAdapter._parse_transaction_string("100,200,|300,400,")
        assert added == ["100", "200"]
        assert dropped == ["300", "400"]

    def test_parse_transaction_string_empty(self):
        added, dropped = MFLAdapter._parse_transaction_string("")
        assert added == []
        assert dropped == []

    def test_parse_transaction_string_bbid(self):
        """BBID waiver has extra pipe segment for bid amount."""
        added, dropped = MFLAdapter._parse_transaction_string("13940,|15289,|25.00")
        assert added == ["13940"]
        assert dropped == ["15289"]

    def test_parse_transaction_string_filters_draft_picks(self):
        added, dropped = MFLAdapter._parse_transaction_string("14777,FP_0001_2025_3,|15331,")
        assert added == ["14777"]
        assert dropped == ["15331"]

    def test_parse_player_ids(self):
        result = MFLAdapter._parse_player_ids("14777,FP_0001_2025_3,15331")
        assert result == ["14777", "15331"]

    def test_parse_player_ids_empty(self):
        assert MFLAdapter._parse_player_ids("") == []
