"""Unit tests for _get_playoff_round() derivation logic."""

from unittest.mock import MagicMock

import pytest

from app.models.enums import PlatformType
from app.sync.engine import _get_playoff_round


def _make_league(
    platform_type: PlatformType,
    league_type: str | None = "redraft",
    settings_json: dict | None = None,
) -> MagicMock:
    league = MagicMock()
    league.platform_type = platform_type
    league.league_type = league_type
    league.settings_json = settings_json or {}
    return league


class TestSleeperPlayoffRound:
    def test_regular_season_returns_none(self):
        league = _make_league(PlatformType.sleeper, settings_json={"playoff_week_start": 15})
        assert _get_playoff_round(league, 14) is None

    def test_first_playoff_week(self):
        league = _make_league(PlatformType.sleeper, settings_json={"playoff_week_start": 15})
        assert _get_playoff_round(league, 15) == 1

    def test_second_playoff_round(self):
        league = _make_league(PlatformType.sleeper, settings_json={"playoff_week_start": 15})
        assert _get_playoff_round(league, 16) == 2

    def test_championship_round(self):
        league = _make_league(PlatformType.sleeper, settings_json={"playoff_week_start": 15})
        assert _get_playoff_round(league, 17) == 3

    def test_fallback_inference_6_teams(self):
        # 6 teams = 3 rounds, 17 total weeks -> playoffs start week 15
        league = _make_league(
            PlatformType.sleeper,
            settings_json={"playoff_teams": 6, "leg": 17},
        )
        assert _get_playoff_round(league, 14) is None
        assert _get_playoff_round(league, 15) == 1
        assert _get_playoff_round(league, 17) == 3

    def test_fallback_inference_4_teams(self):
        # 4 teams = 2 rounds, 17 total weeks -> playoffs start week 16
        league = _make_league(
            PlatformType.sleeper,
            settings_json={"playoff_teams": 4, "leg": 17},
        )
        assert _get_playoff_round(league, 15) is None
        assert _get_playoff_round(league, 16) == 1
        assert _get_playoff_round(league, 17) == 2

    def test_fallback_inference_8_teams(self):
        # 8 teams = 3 rounds, 17 total weeks -> playoffs start week 15
        league = _make_league(
            PlatformType.sleeper,
            settings_json={"playoff_teams": 8, "leg": 17},
        )
        assert _get_playoff_round(league, 14) is None
        assert _get_playoff_round(league, 15) == 1

    def test_no_playoff_settings_returns_none(self):
        league = _make_league(PlatformType.sleeper, settings_json={})
        assert _get_playoff_round(league, 15) is None

    def test_zero_playoff_teams_returns_none(self):
        league = _make_league(
            PlatformType.sleeper,
            settings_json={"playoff_teams": 0, "leg": 17},
        )
        assert _get_playoff_round(league, 15) is None


class TestMFLPlayoffRound:
    def test_regular_season_returns_none(self):
        league = _make_league(
            PlatformType.mfl,
            settings_json={"lastRegularSeasonWeek": "14"},
        )
        assert _get_playoff_round(league, 14) is None

    def test_first_playoff_week(self):
        league = _make_league(
            PlatformType.mfl,
            settings_json={"lastRegularSeasonWeek": "14"},
        )
        assert _get_playoff_round(league, 15) == 1

    def test_championship_week(self):
        league = _make_league(
            PlatformType.mfl,
            settings_json={"lastRegularSeasonWeek": "14"},
        )
        assert _get_playoff_round(league, 17) == 3

    def test_pre_2021_season(self):
        # Pre-2021: regular season weeks 1-13
        league = _make_league(
            PlatformType.mfl,
            settings_json={"lastRegularSeasonWeek": "13"},
        )
        assert _get_playoff_round(league, 13) is None
        assert _get_playoff_round(league, 14) == 1
        assert _get_playoff_round(league, 16) == 3

    def test_no_last_regular_season_week_returns_none(self):
        league = _make_league(PlatformType.mfl, settings_json={})
        assert _get_playoff_round(league, 15) is None


class TestLeagueTypeExclusions:
    def test_bestball_always_returns_none(self):
        league = _make_league(
            PlatformType.sleeper,
            league_type="bestball",
            settings_json={"playoff_week_start": 15},
        )
        assert _get_playoff_round(league, 15) is None
        assert _get_playoff_round(league, 17) is None

    def test_guillotine_always_returns_none(self):
        league = _make_league(
            PlatformType.sleeper,
            league_type="guillotine",
            settings_json={"playoff_week_start": 15},
        )
        assert _get_playoff_round(league, 15) is None

    def test_dynasty_has_playoffs(self):
        league = _make_league(
            PlatformType.sleeper,
            league_type="dynasty",
            settings_json={"playoff_week_start": 15},
        )
        assert _get_playoff_round(league, 15) == 1

    def test_redraft_has_playoffs(self):
        league = _make_league(
            PlatformType.sleeper,
            league_type="redraft",
            settings_json={"playoff_week_start": 15},
        )
        assert _get_playoff_round(league, 15) == 1

    def test_none_league_type_has_playoffs(self):
        # Unknown/NULL league type should still allow playoffs
        league = _make_league(
            PlatformType.sleeper,
            league_type=None,
            settings_json={"playoff_week_start": 15},
        )
        assert _get_playoff_round(league, 15) == 1


class TestEdgeCases:
    def test_week_1_regular_season(self):
        league = _make_league(
            PlatformType.sleeper,
            settings_json={"playoff_week_start": 15},
        )
        assert _get_playoff_round(league, 1) is None

    def test_empty_settings(self):
        league = _make_league(PlatformType.sleeper, settings_json=None)
        assert _get_playoff_round(league, 15) is None

    def test_unknown_platform(self):
        league = _make_league(PlatformType.espn, settings_json={"playoff_week_start": 15})
        assert _get_playoff_round(league, 15) is None
