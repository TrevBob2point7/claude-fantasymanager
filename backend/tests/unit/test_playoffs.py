"""Unit tests for playoff bracket helpers."""

from app.sync.playoffs import (
    detect_byes_mfl,
    detect_byes_sleeper,
    detect_champion_mfl,
    detect_champion_sleeper,
    get_consolation_by_round_mfl,
    get_consolation_pairings_sleeper,
)


class TestDetectChampionSleeper:
    def test_clear_winner(self):
        bracket = [
            {"r": 1, "m": 1, "t1": 1, "t2": 2, "w": 1, "l": 2},
            {"r": 1, "m": 2, "t1": 3, "t2": 4, "w": 3, "l": 4},
            {"r": 2, "m": 3, "t1": 1, "t2": 3, "w": 1, "l": 3},
        ]
        assert detect_champion_sleeper(bracket) == "1"

    def test_in_progress_no_winner(self):
        bracket = [
            {"r": 1, "m": 1, "t1": 1, "t2": 2, "w": 1, "l": 2},
            {"r": 1, "m": 2, "t1": 3, "t2": 4, "w": 3, "l": 4},
            {"r": 2, "m": 3, "t1": 1, "t2": 3, "w": None, "l": None},
        ]
        assert detect_champion_sleeper(bracket) is None

    def test_empty_bracket(self):
        assert detect_champion_sleeper([]) is None

    def test_none_bracket(self):
        assert detect_champion_sleeper(None) is None

    def test_single_round(self):
        bracket = [
            {"r": 1, "m": 1, "t1": 5, "t2": 6, "w": 6, "l": 5},
        ]
        assert detect_champion_sleeper(bracket) == "6"


class TestDetectChampionMFL:
    def test_clear_winner(self):
        rounds = [
            {
                "playoffGame": [
                    {"home": {"franchise_id": "0001", "points": "110.5"},
                     "away": {"franchise_id": "0002", "points": "95.3"}},
                    {"home": {"franchise_id": "0003", "points": "88.0"},
                     "away": {"franchise_id": "0004", "points": "120.1"}},
                ],
            },
            {
                "playoffGame": {
                    "home": {"franchise_id": "0001", "points": "130.2"},
                    "away": {"franchise_id": "0004", "points": "115.8"},
                },
            },
        ]
        assert detect_champion_mfl(rounds) == "0001"

    def test_away_wins(self):
        rounds = [
            {
                "playoffGame": {
                    "home": {"franchise_id": "0001", "points": "90.0"},
                    "away": {"franchise_id": "0002", "points": "110.0"},
                },
            },
        ]
        assert detect_champion_mfl(rounds) == "0002"

    def test_no_scores(self):
        rounds = [
            {
                "playoffGame": {
                    "home": {"franchise_id": "0001", "points": "0"},
                    "away": {"franchise_id": "0002", "points": "0"},
                },
            },
        ]
        assert detect_champion_mfl(rounds) is None

    def test_empty_rounds(self):
        assert detect_champion_mfl([]) is None

    def test_none_rounds(self):
        assert detect_champion_mfl(None) is None

    def test_missing_points(self):
        rounds = [
            {
                "playoffGame": {
                    "home": {"franchise_id": "0001"},
                    "away": {"franchise_id": "0002"},
                },
            },
        ]
        assert detect_champion_mfl(rounds) is None


class TestConsolationPairingsSleeper:
    def test_extracts_pairings(self):
        losers = [
            {"r": 1, "m": 1, "t1": 5, "t2": 6, "w": 5, "l": 6},
            {"r": 2, "m": 2, "t1": 5, "t2": 7, "w": 5, "l": 7},
        ]
        result = get_consolation_pairings_sleeper(losers)
        assert ("5", "6") in result
        assert ("5", "7") in result
        assert len(result) == 2

    def test_empty_bracket(self):
        assert get_consolation_pairings_sleeper([]) == []

    def test_missing_t2_excluded(self):
        losers = [{"r": 1, "m": 1, "t1": 3, "t2": None}]
        assert get_consolation_pairings_sleeper(losers) == []

    def test_missing_t1_excluded(self):
        losers = [{"r": 1, "m": 1, "t1": None, "t2": 4}]
        assert get_consolation_pairings_sleeper(losers) == []

    def test_pairing_order_matches_bracket(self):
        """Pairings use (t1, t2) order from bracket data."""
        losers = [{"r": 1, "m": 1, "t1": 8, "t2": 3, "w": 3, "l": 8}]
        result = get_consolation_pairings_sleeper(losers)
        assert result == [("8", "3")]


class TestDetectByesSleeper:
    def test_six_team_bracket_two_byes(self):
        """Seeds 1 & 2 have byes — they appear in round 2 but not round 1."""
        bracket = [
            {"r": 1, "m": 1, "t1": 3, "t2": 6, "w": 3, "l": 6},
            {"r": 1, "m": 2, "t1": 4, "t2": 5, "w": 4, "l": 5},
            {"r": 2, "m": 3, "t1": 1, "t2": 4, "w": 1, "l": 4},
            {"r": 2, "m": 4, "t1": 2, "t2": 3, "w": 2, "l": 3},
            {"r": 3, "m": 5, "t1": 1, "t2": 2, "w": 1, "l": 2},
        ]
        assert detect_byes_sleeper(bracket) == {"1", "2"}

    def test_four_team_bracket_no_byes(self):
        bracket = [
            {"r": 1, "m": 1, "t1": 1, "t2": 4, "w": 1, "l": 4},
            {"r": 1, "m": 2, "t1": 2, "t2": 3, "w": 2, "l": 3},
            {"r": 2, "m": 3, "t1": 1, "t2": 2, "w": 1, "l": 2},
        ]
        assert detect_byes_sleeper(bracket) == set()

    def test_empty_bracket(self):
        assert detect_byes_sleeper([]) == set()


class TestDetectByesMFL:
    def test_six_team_bracket_two_byes(self):
        """Seeds 1 & 2 have byes — they appear in round 2 but not round 1."""
        rounds = [
            {
                "week": "15",
                "playoffGame": [
                    {"home": {"franchise_id": "0003", "seed": "3"},
                     "away": {"franchise_id": "0006", "seed": "6"}},
                    {"home": {"franchise_id": "0004", "seed": "4"},
                     "away": {"franchise_id": "0005", "seed": "5"}},
                ],
            },
            {
                "week": "16",
                "playoffGame": [
                    {"home": {"franchise_id": "0001", "seed": "1"},
                     "away": {"franchise_id": "0005"}},
                    {"home": {"franchise_id": "0002", "seed": "2"},
                     "away": {"franchise_id": "0003"}},
                ],
            },
            {
                "week": "17",
                "playoffGame": {
                    "home": {"franchise_id": "0001"},
                    "away": {"franchise_id": "0002"},
                },
            },
        ]
        assert detect_byes_mfl(rounds) == {"0001", "0002"}

    def test_four_team_bracket_no_byes(self):
        rounds = [
            {
                "week": "15",
                "playoffGame": [
                    {"home": {"franchise_id": "0001"},
                     "away": {"franchise_id": "0004"}},
                    {"home": {"franchise_id": "0002"},
                     "away": {"franchise_id": "0003"}},
                ],
            },
            {
                "week": "16",
                "playoffGame": {
                    "home": {"franchise_id": "0001"},
                    "away": {"franchise_id": "0002"},
                },
            },
        ]
        assert detect_byes_mfl(rounds) == set()

    def test_empty_rounds(self):
        assert detect_byes_mfl([]) == set()


class TestConsolationByRoundMFL:
    def test_groups_by_week(self):
        rounds = [
            {
                "week": "16",
                "playoffGame": {
                    "home": {"franchise_id": "0005"},
                    "away": {"franchise_id": "0006"},
                },
            },
            {
                "week": "17",
                "playoffGame": {
                    "home": {"franchise_id": "0005"},
                    "away": {"franchise_id": "0007"},
                },
            },
        ]
        # playoff_start_week=15 -> week 16 = round 2, week 17 = round 3
        result = get_consolation_by_round_mfl(rounds, playoff_start_week=15)
        assert 2 in result
        assert 3 in result
        assert result[2] == {"0005", "0006"}
        assert result[3] == {"0005", "0007"}

    def test_empty_rounds(self):
        assert get_consolation_by_round_mfl([], playoff_start_week=15) == {}

    def test_single_game_dict(self):
        """MFL returns single game as dict, not list."""
        rounds = [
            {
                "week": "17",
                "playoffGame": {
                    "home": {"franchise_id": "0001"},
                    "away": {"franchise_id": "0002"},
                },
            },
        ]
        result = get_consolation_by_round_mfl(rounds, playoff_start_week=15)
        assert result[3] == {"0001", "0002"}

    def test_week_before_playoffs_skipped(self):
        rounds = [
            {
                "week": "14",
                "playoffGame": {
                    "home": {"franchise_id": "0001"},
                    "away": {"franchise_id": "0002"},
                },
            },
        ]
        result = get_consolation_by_round_mfl(rounds, playoff_start_week=15)
        assert result == {}
