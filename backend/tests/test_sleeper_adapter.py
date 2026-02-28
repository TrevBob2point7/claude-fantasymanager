"""Unit tests for the Sleeper platform adapter with mocked HTTP via respx."""

import httpx
import pytest
import respx
from app.platforms.sleeper import BASE_URL, SleeperAdapter

NULL_JSON_RESPONSE = httpx.Response(
    200, content=b"null", headers={"content-type": "application/json"}
)


class TestGetUser:
    async def test_get_user_success(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/user/testuser").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "user_id": "123456",
                        "username": "testuser",
                        "display_name": "Test User",
                    },
                )
            )
            adapter = SleeperAdapter()
            user = await adapter.get_user("testuser")
        assert user.user_id == "123456"
        assert user.username == "testuser"
        assert user.display_name == "Test User"

    async def test_get_user_not_found(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/user/nobody").mock(
                return_value=NULL_JSON_RESPONSE
            )
            adapter = SleeperAdapter()
            with pytest.raises(ValueError, match="not found"):
                await adapter.get_user("nobody")

    async def test_get_user_api_error(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/user/baduser").mock(
                return_value=httpx.Response(500)
            )
            adapter = SleeperAdapter()
            with pytest.raises(httpx.HTTPStatusError):
                await adapter.get_user("baduser")


class TestGetLeagues:
    async def test_get_leagues_success(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/user/123/leagues/nfl/2025").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "league_id": "lg1",
                            "name": "Dynasty League",
                            "season": "2025",
                            "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"],
                            "scoring_settings": {"rec": 1},
                            "settings": {"leg": 5},
                        },
                        {
                            "league_id": "lg2",
                            "name": "Redraft League",
                            "season": "2025",
                            "roster_positions": ["QB", "RB", "WR"],
                            "scoring_settings": {"rec": 0.5},
                            "settings": {},
                        },
                    ],
                )
            )
            adapter = SleeperAdapter()
            leagues = await adapter.get_leagues("123", 2025)
        assert len(leagues) == 2
        assert leagues[0].league_id == "lg1"
        assert leagues[0].name == "Dynasty League"
        assert leagues[0].season == 2025
        assert leagues[0].roster_size == 7
        assert leagues[0].scoring_type == "ppr"
        assert leagues[1].scoring_type == "half_ppr"

    async def test_get_leagues_standard_scoring(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/user/123/leagues/nfl/2025").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "league_id": "lg3",
                            "name": "Standard",
                            "season": "2025",
                            "scoring_settings": {"rec": 0},
                        }
                    ],
                )
            )
            adapter = SleeperAdapter()
            leagues = await adapter.get_leagues("123", 2025)
        assert leagues[0].scoring_type == "standard"

    async def test_get_leagues_empty(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/user/123/leagues/nfl/2025").mock(
                return_value=NULL_JSON_RESPONSE
            )
            adapter = SleeperAdapter()
            leagues = await adapter.get_leagues("123", 2025)
        assert leagues == []


class TestGetRosters:
    async def test_get_rosters_success(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/rosters").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "owner_id": "user1",
                            "roster_id": 1,
                            "players": ["1234", "5678", "9012"],
                            "starters": ["1234", "5678"],
                        },
                        {
                            "owner_id": "user2",
                            "roster_id": 2,
                            "players": ["3456"],
                            "starters": ["3456"],
                        },
                    ],
                )
            )
            adapter = SleeperAdapter()
            rosters = await adapter.get_rosters("lg1")
        assert len(rosters) == 2
        assert rosters[0].owner_id == "user1"
        assert rosters[0].player_ids == ["1234", "5678", "9012"]
        assert rosters[0].starters == ["1234", "5678"]

    async def test_get_rosters_empty(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/rosters").mock(
                return_value=NULL_JSON_RESPONSE
            )
            adapter = SleeperAdapter()
            rosters = await adapter.get_rosters("lg1")
        assert rosters == []


class TestGetMatchups:
    async def test_get_matchups_success(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/matchups/1").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {"matchup_id": 1, "roster_id": 1, "points": 120.5},
                        {"matchup_id": 1, "roster_id": 2, "points": 115.3},
                        {"matchup_id": 2, "roster_id": 3, "points": 98.0},
                        {"matchup_id": 2, "roster_id": 4, "points": 105.7},
                    ],
                )
            )
            adapter = SleeperAdapter()
            matchups = await adapter.get_matchups("lg1", 1)
        assert len(matchups) == 4
        assert matchups[0].matchup_id == 1
        assert matchups[0].roster_id == "1"
        assert matchups[0].points == 120.5
        assert matchups[0].week == 1

    async def test_get_matchups_empty(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/matchups/1").mock(
                return_value=NULL_JSON_RESPONSE
            )
            adapter = SleeperAdapter()
            matchups = await adapter.get_matchups("lg1", 1)
        assert matchups == []


class TestGetTransactions:
    async def test_get_transactions_success(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/transactions/1").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "status": "complete",
                            "type": "waiver",
                            "adds": {"9999": 1},
                            "drops": {"8888": 1},
                            "status_updated": 1700000000000,
                        },
                        {
                            "status": "failed",
                            "type": "add",
                            "adds": {"7777": 2},
                            "drops": {},
                            "status_updated": 1700000001000,
                        },
                    ],
                )
            )
            adapter = SleeperAdapter()
            txns = await adapter.get_transactions("lg1", 1)
        # Only completed transactions
        assert len(txns) == 1
        assert txns[0].type == "waiver"
        assert txns[0].player_ids_added == ["9999"]
        assert txns[0].player_ids_dropped == ["8888"]
        assert txns[0].timestamp == 1700000000000

    async def test_get_transactions_empty(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/transactions/1").mock(
                return_value=NULL_JSON_RESPONSE
            )
            adapter = SleeperAdapter()
            txns = await adapter.get_transactions("lg1", 1)
        assert txns == []

    async def test_get_transactions_trade(self):
        async with respx.mock:
            respx.get(f"{BASE_URL}/league/lg1/transactions/1").mock(
                return_value=httpx.Response(
                    200,
                    json=[
                        {
                            "status": "complete",
                            "type": "trade",
                            "adds": {"1111": 1, "2222": 2},
                            "drops": {"3333": 2, "4444": 1},
                            "status_updated": 1700000002000,
                        }
                    ],
                )
            )
            adapter = SleeperAdapter()
            txns = await adapter.get_transactions("lg1", 1)
        assert len(txns) == 1
        assert txns[0].type == "trade"
        assert len(txns[0].player_ids_added) == 2
        assert len(txns[0].player_ids_dropped) == 2
