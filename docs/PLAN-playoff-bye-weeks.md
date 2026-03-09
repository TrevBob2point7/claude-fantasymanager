# Plan: Playoff Bye Week Matchups

Show a "BYE" matchup row for teams that had a first-round playoff bye, so the matchup list clearly indicates the bye rather than skipping that week.

## Detection Logic

Both platforms encode byes implicitly — a team that appears in the bracket but NOT in round 1 had a bye.

**MFL:** Walk `playoffRound` entries. Collect all `franchise_id`s from round 1 games. Any franchise in round 2+ that wasn't in round 1 had a bye. The `seed` field on each entry confirms seeding.

**Sleeper:** Walk `winners_bracket` entries. Collect all `t1`/`t2` roster IDs from `r: 1` matches. Any roster ID in `r: 2`+ matches that wasn't in round 1 had a bye.

## Storage

Store detected bye franchise IDs in `league.settings_json["bracket_data"]["byes"]` as a dict of `{playoff_round: [franchise_ids]}` (round 1 initially, but keeps the door open for multi-round byes in unusual formats).

## Schema Changes

### Migration

- Make `away_user_league_id` nullable on `matchups` table (`ALTER COLUMN ... DROP NOT NULL`)

### Model (`backend/app/models/matchup.py`)

- Change `away_user_league_id` from `nullable=False` to `nullable=True`
- Update `Mapped[uuid.UUID]` to `Mapped[uuid.UUID | None]`

### Pydantic Schema (`backend/app/schemas/league.py`)

- Add `is_bye: bool = False` to `MatchupSummaryRead`

### Frontend Types (`frontend/src/api/types.ts`)

- Add `is_bye: boolean` to `MatchupSummary`

## Sync Changes (`backend/app/sync/engine.py`)

### New helper: `detect_byes_from_bracket()`

In `sync/playoffs.py`, add two functions:

```python
def detect_byes_sleeper(winners_bracket: list[dict]) -> set[str]:
    """Return roster_ids that had a first-round bye."""
    if not winners_bracket:
        return set()
    round_1_ids = set()
    all_ids = set()
    for m in winners_bracket:
        for key in ("t1", "t2"):
            val = m.get(key)
            if val is not None:
                all_ids.add(str(val))
                if m.get("r") == 1:
                    round_1_ids.add(str(val))
    return all_ids - round_1_ids

def detect_byes_mfl(winners_bracket_rounds: list[dict]) -> set[str]:
    """Return franchise_ids that had a first-round bye."""
    if not winners_bracket_rounds:
        return set()
    round_1_ids = set()
    all_ids = set()
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
```

### In `sync_playoff_brackets()`

After detecting champion and consolation data, also detect byes and store in `bracket_data["byes"]`:

```python
byes = detect_byes_sleeper(winners) if sleeper else detect_byes_mfl(winners)
settings["bracket_data"]["byes"] = {1: list(byes)}  # round 1 byes
```

### In `sync_matchups()`

After syncing real matchups for a week, check if this week corresponds to playoff round 1. If so, look up bye franchise IDs from `bracket_data["byes"]["1"]`, and for each bye franchise that maps to a `user_league`, create a matchup with:

- `home_user_league_id` = the bye team's user_league
- `away_user_league_id` = NULL
- `home_score` = NULL, `away_score` = NULL
- `playoff_round` = 1
- `is_consolation` = False

Upsert logic: check for existing bye matchup (away_user_league_id IS NULL, same league/week/home).

## API Changes (`backend/app/api/leagues.py`)

In the matchup summary endpoint, set `is_bye=True` when `away_user_league_id is None`:

```python
is_bye = m.away_user_league_id is None
```

Set `away_team_name = "BYE"` for display convenience (or leave null and let frontend handle it).

## Frontend Changes (`frontend/src/pages/LeagueDetailPage.tsx`)

In the matchup row rendering:

- If `is_bye`, show "{home_team_name} — BYE" with no score
- Style similarly to other playoff matchups (use the playoff round badge)
- Mark as `is_user_matchup` if the home team is the user's team

## Testing

- Unit tests for `detect_byes_sleeper` and `detect_byes_mfl` in `test_playoffs.py`
- Test with 6-team playoff bracket (2 byes) and 4-team bracket (0 byes)
- Verify bye matchups appear in correct week for Old Republic 2025 (seeds 1 & 2 should have week 15 byes)
