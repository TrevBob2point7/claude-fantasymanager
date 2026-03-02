import httpx
import respx
from app.adp.base import ADPRecord
from app.adp.dynastyprocess import DynastyProcessADPProvider
from app.adp.ffc import FFCADPProvider
from app.adp.registry import get_adp_providers
from app.adp.sleeper import SleeperADPProvider
from app.models.enums import ADPFormat


class TestSleeperADPProvider:
    """SleeperADPProvider.fetch_adp / supported_formats"""

    def test_supported_formats(self):
        provider = SleeperADPProvider()
        formats = provider.supported_formats()
        assert ADPFormat.standard in formats
        assert ADPFormat.ppr in formats
        assert ADPFormat.half_ppr in formats
        assert ADPFormat.dynasty in formats
        assert ADPFormat.superflex not in formats

    @respx.mock
    async def test_fetch_adp_parses_players(self):
        respx.get("https://api.sleeper.app/v1/players/nfl").mock(
            return_value=httpx.Response(
                200,
                json={
                    "4046": {
                        "active": True,
                        "first_name": "Tyreek",
                        "last_name": "Hill",
                        "full_name": "Tyreek Hill",
                        "position": "WR",
                        "team": "MIA",
                        "search_rank": 12,
                    },
                    "6794": {
                        "active": True,
                        "first_name": "Joe",
                        "last_name": "Burrow",
                        "full_name": "Joe Burrow",
                        "position": "QB",
                        "team": "CIN",
                        "search_rank": 25,
                    },
                },
            )
        )

        provider = SleeperADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.ppr)

        assert len(records) == 2
        assert all(isinstance(r, ADPRecord) for r in records)
        # Should be sorted by adp ascending
        assert records[0].adp < records[1].adp
        assert records[0].player_name == "Tyreek Hill"
        assert records[0].position == "WR"
        assert records[0].team == "MIA"
        assert records[0].sleeper_id == "4046"
        assert records[0].source == "sleeper"
        assert records[0].format == ADPFormat.ppr

    @respx.mock
    async def test_fetch_adp_skips_inactive_players(self):
        respx.get("https://api.sleeper.app/v1/players/nfl").mock(
            return_value=httpx.Response(
                200,
                json={
                    "1": {
                        "active": False,
                        "first_name": "Retired",
                        "last_name": "Player",
                        "position": "QB",
                        "team": "FA",
                        "search_rank": 5,
                    },
                },
            )
        )

        provider = SleeperADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.standard)
        assert len(records) == 0

    @respx.mock
    async def test_fetch_adp_skips_invalid_positions(self):
        respx.get("https://api.sleeper.app/v1/players/nfl").mock(
            return_value=httpx.Response(
                200,
                json={
                    "1": {
                        "active": True,
                        "first_name": "Test",
                        "last_name": "Coach",
                        "position": "HC",
                        "team": "NYJ",
                        "search_rank": 10,
                    },
                },
            )
        )

        provider = SleeperADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.standard)
        assert len(records) == 0

    @respx.mock
    async def test_fetch_adp_skips_zero_or_missing_rank(self):
        respx.get("https://api.sleeper.app/v1/players/nfl").mock(
            return_value=httpx.Response(
                200,
                json={
                    "1": {
                        "active": True,
                        "first_name": "No",
                        "last_name": "Rank",
                        "position": "RB",
                        "team": "CHI",
                        "search_rank": None,
                    },
                    "2": {
                        "active": True,
                        "first_name": "Zero",
                        "last_name": "Rank",
                        "position": "RB",
                        "team": "CHI",
                        "search_rank": 0,
                    },
                },
            )
        )

        provider = SleeperADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.standard)
        assert len(records) == 0

    @respx.mock
    async def test_fetch_adp_http_error(self):
        respx.get("https://api.sleeper.app/v1/players/nfl").mock(
            return_value=httpx.Response(500)
        )

        provider = SleeperADPProvider()
        import pytest

        with pytest.raises(httpx.HTTPStatusError):
            await provider.fetch_adp(2025, ADPFormat.standard)


class TestFFCADPProvider:
    """FFCADPProvider.fetch_adp / supported_formats"""

    def test_supported_formats(self):
        provider = FFCADPProvider()
        formats = provider.supported_formats()
        assert ADPFormat.standard in formats
        assert ADPFormat.ppr in formats
        assert ADPFormat.dynasty in formats
        assert ADPFormat.superflex in formats
        assert ADPFormat.two_qb in formats
        assert len(formats) == 6

    @respx.mock
    async def test_fetch_adp_parses_players(self):
        respx.get("https://fantasyfootballcalculator.com/api/v1/adp/ppr").mock(
            return_value=httpx.Response(
                200,
                json={
                    "players": [
                        {
                            "name": "CeeDee Lamb",
                            "position": "WR",
                            "team": "DAL",
                            "adp": 3.5,
                            "positionRank": 1,
                        },
                        {
                            "name": "Bijan Robinson",
                            "position": "RB",
                            "team": "ATL",
                            "adp": 1.2,
                            "positionRank": 1,
                        },
                    ]
                },
            )
        )

        provider = FFCADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.ppr)

        assert len(records) == 2
        assert records[0].player_name == "CeeDee Lamb"
        assert records[0].position == "WR"
        assert records[0].adp == 3.5
        assert records[0].position_rank == 1
        assert records[0].source == "ffc"
        assert records[0].format == ADPFormat.ppr

    @respx.mock
    async def test_fetch_adp_sends_correct_params(self):
        route = respx.get("https://fantasyfootballcalculator.com/api/v1/adp/half-ppr").mock(
            return_value=httpx.Response(200, json={"players": []})
        )

        provider = FFCADPProvider()
        await provider.fetch_adp(2025, ADPFormat.half_ppr)

        assert route.called
        request = route.calls[0].request
        assert "teams=12" in str(request.url)
        assert "year=2025" in str(request.url)

    @respx.mock
    async def test_fetch_adp_skips_empty_names(self):
        respx.get("https://fantasyfootballcalculator.com/api/v1/adp/standard").mock(
            return_value=httpx.Response(
                200,
                json={
                    "players": [
                        {"name": "", "position": "QB", "team": "NYJ", "adp": 50.0},
                    ]
                },
            )
        )

        provider = FFCADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.standard)
        assert len(records) == 0

    @respx.mock
    async def test_fetch_adp_format_mapping(self):
        """Verify the format string mapping for each ADPFormat."""
        route = respx.get("https://fantasyfootballcalculator.com/api/v1/adp/2qb").mock(
            return_value=httpx.Response(200, json={"players": []})
        )

        provider = FFCADPProvider()
        await provider.fetch_adp(2025, ADPFormat.two_qb)
        assert route.called


class TestDynastyProcessADPProvider:
    """DynastyProcessADPProvider.fetch_adp / supported_formats"""

    def test_supported_formats(self):
        provider = DynastyProcessADPProvider()
        formats = provider.supported_formats()
        assert formats == [ADPFormat.dynasty]

    @respx.mock
    async def test_fetch_adp_parses_csv(self):
        csv_content = (
            "player,pos,team,value_1qb,sleeper_id\n"
            "Ja'Marr Chase,WR,CIN,9500,7564\n"
            "Breece Hall,RB,NYJ,8800,8155\n"
            "Sam LaPorta,TE,DET,5000,9509\n"
        )
        respx.get(
            "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
        ).mock(return_value=httpx.Response(200, text=csv_content))

        provider = DynastyProcessADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.dynasty)

        assert len(records) == 3
        # Sorted by value descending (higher = better)
        assert records[0].player_name == "Ja'Marr Chase"
        assert records[0].adp == 9500.0
        assert records[0].sleeper_id == "7564"
        assert records[0].source == "dynastyprocess"
        assert records[0].format == ADPFormat.dynasty

    @respx.mock
    async def test_fetch_adp_assigns_position_ranks(self):
        csv_content = (
            "player,pos,team,value_1qb,sleeper_id\n"
            "Player A,WR,CIN,9500,1\n"
            "Player B,RB,NYJ,8800,2\n"
            "Player C,WR,DET,7000,3\n"
        )
        respx.get(
            "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
        ).mock(return_value=httpx.Response(200, text=csv_content))

        provider = DynastyProcessADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.dynasty)

        wr_records = [r for r in records if r.position == "WR"]
        assert wr_records[0].position_rank == 1
        assert wr_records[1].position_rank == 2

        rb_records = [r for r in records if r.position == "RB"]
        assert rb_records[0].position_rank == 1

    @respx.mock
    async def test_fetch_adp_non_dynasty_format_returns_empty(self):
        provider = DynastyProcessADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.ppr)
        assert records == []

    @respx.mock
    async def test_fetch_adp_skips_empty_values(self):
        csv_content = (
            "player,pos,team,value_1qb,sleeper_id\n"
            "Good Player,WR,CIN,9500,1\n"
            "No Value,RB,NYJ,,2\n"
            ",WR,DET,5000,3\n"
        )
        respx.get(
            "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
        ).mock(return_value=httpx.Response(200, text=csv_content))

        provider = DynastyProcessADPProvider()
        records = await provider.fetch_adp(2025, ADPFormat.dynasty)
        assert len(records) == 1
        assert records[0].player_name == "Good Player"


class TestADPRegistry:
    """get_adp_providers registry."""

    def test_returns_all_providers(self):
        providers = get_adp_providers()
        assert len(providers) == 3
        types = {type(p) for p in providers}
        assert types == {SleeperADPProvider, FFCADPProvider, DynastyProcessADPProvider}
