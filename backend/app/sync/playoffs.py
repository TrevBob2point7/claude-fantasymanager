"""Playoff bracket helpers for champion detection and consolation identification."""

from __future__ import annotations


def detect_champion_sleeper(winners_bracket: list[dict] | None) -> str | None:
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


def detect_champion_mfl(winners_bracket_rounds: list[dict] | None) -> str | None:
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


def get_consolation_pairings_sleeper(losers_bracket: list[dict]) -> list[tuple[str, str]]:
    """Extract matchup pairings from the Sleeper losers bracket.

    Returns a list of (roster_id_a, roster_id_b) tuples — one per consolation
    matchup.  The caller can check whether a given matchup pairing appears in
    this list to decide ``is_consolation``.

    This avoids the round-mapping problem: Sleeper bracket round numbers (``r``)
    don't correspond 1-to-1 with ``playoff_round`` (derived from week number)
    because losers bracket round N plays during playoff week N+1 or later.
    Matching on exact pairings is unambiguous regardless of bracket structure
    or multi-week playoff rounds.
    """
    pairings: list[tuple[str, str]] = []
    for m in losers_bracket:
        t1 = m.get("t1")
        t2 = m.get("t2")
        if t1 is not None and t2 is not None:
            pairings.append((str(t1), str(t2)))
    return pairings


def detect_byes_sleeper(winners_bracket: list[dict] | None) -> set[str]:
    """Return roster_ids that had a first-round bye."""
    if not winners_bracket:
        return set()
    round_1_ids: set[str] = set()
    all_ids: set[str] = set()
    for m in winners_bracket:
        for key in ("t1", "t2"):
            val = m.get(key)
            if val is not None:
                all_ids.add(str(val))
                if m.get("r") == 1:
                    round_1_ids.add(str(val))
    return all_ids - round_1_ids


def detect_byes_mfl(winners_bracket_rounds: list[dict] | None) -> set[str]:
    """Return franchise_ids that had a first-round bye."""
    if not winners_bracket_rounds:
        return set()
    round_1_ids: set[str] = set()
    all_ids: set[str] = set()
    for i, rnd in enumerate(winners_bracket_rounds):
        games = rnd.get("playoffGame", [])
        if isinstance(games, dict):
            games = [games]
        for game in games:
            for side in ("home", "away"):
                fid = game.get(side, {}).get("franchise_id")
                if fid:
                    all_ids.add(fid)
                    if i == 0:
                        round_1_ids.add(fid)
    return all_ids - round_1_ids


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
