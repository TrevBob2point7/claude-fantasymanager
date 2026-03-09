"""Playoff bracket helpers for champion detection and consolation identification."""

from __future__ import annotations


def detect_champion_sleeper(winners_bracket: list[dict]) -> str | None:
    """Return the roster_id of the championship winner from Sleeper bracket data.

    Sleeper bracket entries have: r (round), m (match_id), t1, t2, w (winner), l (loser).
    """
    if not winners_bracket:
        return None
    final_round = max(m["r"] for m in winners_bracket)
    finals = [m for m in winners_bracket if m["r"] == final_round]
    if finals and finals[0].get("w"):
        return str(finals[0]["w"])
    return None


def detect_champion_mfl(winners_bracket_rounds: list[dict]) -> str | None:
    """Return the franchise_id of the championship winner from MFL bracket rounds.

    MFL bracket rounds are ordered; the last round is the championship.
    Each round has playoffGame(s) with home/away franchise_id and points.
    """
    if not winners_bracket_rounds:
        return None
    final_round = winners_bracket_rounds[-1]
    games = final_round.get("playoffGame", [])
    if isinstance(games, dict):
        games = [games]
    if not games:
        return None
    game = games[0]
    home = game.get("home", {})
    away = game.get("away", {})
    try:
        home_pts = float(home.get("points", 0) or 0)
        away_pts = float(away.get("points", 0) or 0)
    except (ValueError, TypeError):
        return None
    if home_pts > away_pts:
        return home.get("franchise_id")
    elif away_pts > home_pts:
        return away.get("franchise_id")
    return None


def get_consolation_by_round_sleeper(losers_bracket: list[dict]) -> dict[int, set[str]]:
    """Extract roster_ids per round from the Sleeper losers bracket.

    Returns {round_number: set_of_roster_ids} so we can match consolation
    status to specific playoff rounds, not just franchise identity.
    """
    by_round: dict[int, set[str]] = {}
    for m in losers_bracket:
        r = m.get("r")
        if r is None:
            continue
        ids = by_round.setdefault(r, set())
        for key in ("t1", "t2", "w", "l"):
            val = m.get(key)
            if val is not None:
                ids.add(str(val))
    return by_round


def get_consolation_by_round_mfl(
    consolation_rounds: list[dict], playoff_start_week: int,
) -> dict[int, set[str]]:
    """Extract franchise_ids per playoff round from MFL consolation bracket rounds.

    Each MFL round has a week attribute; we convert to playoff_round number
    using playoff_start_week. Returns {playoff_round: set_of_franchise_ids}.
    """
    by_round: dict[int, set[str]] = {}
    for rnd in consolation_rounds:
        week = int(rnd.get("week", 0))
        if not week:
            continue
        playoff_round = week - playoff_start_week + 1
        if playoff_round < 1:
            continue
        ids = by_round.setdefault(playoff_round, set())
        games = rnd.get("playoffGame", [])
        if isinstance(games, dict):
            games = [games]
        for game in games:
            for side in ("home", "away"):
                fid = game.get(side, {}).get("franchise_id")
                if fid:
                    ids.add(fid)
    return by_round
