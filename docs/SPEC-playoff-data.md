# Spec: Playoff Data & Championship Detection

## Problem

The app currently treats all matchup weeks identically — there is no distinction between regular season and playoff matchups. This means we cannot:

- Identify championship winners
- Show playoff brackets or playoff record
- Differentiate regular season record from overall record
- Calculate franchise history stats like "years won the championship"

## Goal

Add playoff metadata to matchups so we can determine:

1. Whether a matchup is regular season or playoff
2. What playoff round a matchup belongs to (wildcard, semis, finals)
3. Whether a team won the championship in a given season
4. Whether a matchup is winners bracket vs consolation/losers bracket

---

## Platform-Specific Playoff Data

### Sleeper

**League settings** (stored in `league.settings_json` as part of the raw Sleeper settings dict):
- `playoff_week_start` — week number when playoffs begin (e.g., `15`). **May not be present** in all leagues — see fallback below.
- `playoff_teams` — number of teams in playoffs (e.g., `6`)
- `playoff_round_type` — bracket type (0 = one week per round, 1 = two weeks per round)

**Fallback for missing `playoff_week_start`:** Infer from total weeks and bracket size. For a league with `playoff_teams=6`, you need 3 rounds (6→4→2→1). If the season has 17 total weeks, playoffs start at week 15. Formula: `playoff_week_start = total_weeks - num_playoff_rounds + 1`, where `num_playoff_rounds = ceil(log2(playoff_teams))`.

**Bracket endpoints** (not currently fetched):
- `GET /league/{league_id}/winners_bracket` — championship bracket
- `GET /league/{league_id}/losers_bracket` — consolation bracket

**Bracket response format:**
```json
[
  {
    "r": 1,
    "m": 1,
    "t1": 3,
    "t2": 6,
    "w": 3,
    "l": 6,
    "t1_from": { "w": null, "l": null },
    "t2_from": { "w": null, "l": null }
  }
]
```

Fields:
- `r` — round number (1 = first round, 2 = semis, 3 = finals)
- `m` — matchup ID within the round
- `t1`, `t2` — roster IDs of the two teams
- `w`, `l` — winner and loser roster IDs (null if not yet played)
- `t1_from`, `t2_from` — seeding source (which prior matchup winner/loser fed in)

**Championship detection:** The matchup with the highest `r` value in `winners_bracket` where `w` is set — that's the champion's `roster_id`.

### MFL

**League settings** (already stored in `league.settings_json`):
- `lastRegularSeasonWeek` — e.g., `"14"`. Weeks after this are playoffs.
- `startWeek` — first week (typically `"1"`)
- `endWeek` — final week including playoffs (e.g., `"17"`)

**Bracket API endpoints:**

1. `GET /export?TYPE=playoffBrackets&L={league_id}&JSON=1` — lists all brackets for a league:

```json
{
  "playoffBrackets": {
    "playoffBracket": [
      {
        "id": "1",
        "name": "Spartan League Playoffs",
        "bracketWinnerTitle": "Spartan League Champion",
        "startWeek": "15",
        "teamsInvolved": "6",
        "startWeekGames": "2"
      },
      {
        "id": "2",
        "name": "3rd Place Game",
        "bracketWinnerTitle": "3rd Place",
        "startWeek": "17",
        "teamsInvolved": "2",
        "startWeekGames": "1"
      }
    ]
  }
}
```

Fields:
- `id` — bracket ID (used to fetch detail)
- `name` — bracket name
- `bracketWinnerTitle` — title awarded to winner (e.g., "Spartan League Champion")
- `startWeek` — first week of this bracket
- `teamsInvolved` — number of teams in the bracket
- `startWeekGames` — number of games in the first round

2. `GET /export?TYPE=playoffBracket&L={league_id}&BRACKET_ID={id}&JSON=1` — full bracket detail:

```json
{
  "playoffBracket": {
    "bracket_id": "1",
    "playoffRound": [
      {
        "week": "15",
        "playoffGame": [
          {
            "game_id": "1",
            "home": { "franchise_id": "0008", "seed": "3", "points": "152.34" },
            "away": { "franchise_id": "0004", "seed": "6", "points": "108.28" }
          },
          {
            "game_id": "2",
            "home": { "franchise_id": "0012", "seed": "4", "points": "144.94" },
            "away": { "franchise_id": "0010", "seed": "5", "points": "146.44" }
          }
        ]
      },
      {
        "week": "16",
        "playoffGame": [
          {
            "game_id": "3",
            "home": { "franchise_id": "0009", "seed": "2", "points": "145.28" },
            "away": { "franchise_id": "0008", "winner_of_game": "1", "points": "176.02" }
          },
          {
            "game_id": "4",
            "home": { "franchise_id": "0011", "seed": "1", "points": "178.32" },
            "away": { "franchise_id": "0010", "winner_of_game": "2", "points": "102.26" }
          }
        ]
      },
      {
        "week": "17",
        "playoffGame": {
          "game_id": "5",
          "home": { "franchise_id": "0011", "winner_of_game": "4", "points": "202.36" },
          "away": { "franchise_id": "0008", "winner_of_game": "3", "points": "145.17" }
        }
      }
    ]
  }
}
```

Fields per `playoffRound`:
- `week` — NFL week number
- `playoffGame[]` — array of games in this round (single game returns as object, not array — use `_ensure_list`)

Fields per `playoffGame`:
- `game_id` — unique game identifier within the bracket
- `home` / `away` — team entries with `franchise_id`, `seed` (first round), `points`, and optionally `winner_of_game` (references a prior `game_id`)

**Championship detection:** The championship bracket is identifiable by `bracketWinnerTitle` containing "Champion" (or simply the bracket with the most `teamsInvolved`). The final round's game winner is the champion — compare `points` for home vs away in the last `playoffRound`.

**Consolation detection:** Non-championship brackets (e.g., "3rd Place Game") are consolation. Any matchup whose `franchise_id` appears in a non-championship bracket is consolation.

**Notes:**
- A league may have multiple brackets (championship + consolation/3rd-place)
- `playoffGame` can be a single object instead of an array when there's only one game in a round (standard MFL pattern)
- Byes in the first round: top seeds appear in later rounds with `seed` set but no `winner_of_game`

### NFL Regular Season Week History

The number of regular season fantasy weeks has changed over time:

| Years | NFL Regular Season | Typical Fantasy Regular Season | Typical Fantasy Playoffs |
|-------|-------------------|-------------------------------|------------------------|
| Pre-2021 | 16 games | Weeks 1-13 | Weeks 14-16 |
| 2021+ | 17 games | Weeks 1-14 | Weeks 15-17 |

Individual leagues can configure their own playoff start week, so always use league settings rather than hardcoding.

### League Types with Playoffs

Only **dynasty** and **redraft** leagues have playoffs. Best ball and guillotine leagues do not — they should be excluded from all playoff/bracket data fetching and championship detection.

### Two-Week Playoff Rounds (Deferred)

Sleeper supports `playoff_round_type=1` where scores accumulate across two weeks per round. **This is deferred** — none of the current leagues use two-week rounds. When implemented, both weeks would share the same `playoff_round` value and scores would need to be summed for win/loss determination.

---

## Data Model Changes

### Matchup model — add `playoff_round` column

```python
# backend/app/models/matchup.py
playoff_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Values:
- `NULL` — regular season matchup
- `1` — first playoff round (wildcard)
- `2` — second round (semis)
- `3` — third round (finals / championship)
- Higher values possible for leagues with more playoff rounds

### Matchup model — add `is_consolation` column

```python
is_consolation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
```

Distinguishes winners bracket from consolation/losers bracket matchups. Reliably set for both Sleeper (via bracket data) and MFL (via `playoffBrackets` API — non-championship brackets are consolation).

### Migration

Single Alembic migration adding both nullable columns with defaults:
- `playoff_round` — nullable, no default
- `is_consolation` — non-nullable, default `false`

No backfill needed at migration time. Existing matchups get `playoff_round=NULL` and `is_consolation=false`. A backfill command or sync re-run will populate them.

---

## Implementation Plan

### PR 1: Schema + Playoff Round Detection

**Backend changes:**

1. **Alembic migration** — add `playoff_round` and `is_consolation` to matchups table

2. **Platform schemas** — add fields to `PlatformMatchup`:
   ```python
   playoff_round: int | None = None
   is_consolation: bool = False
   ```

3. **Derive playoff_round during matchup sync** (`sync_matchups` in engine.py):
   - Skip for best ball and guillotine leagues (no playoffs)
   - Read `playoff_week_start` (Sleeper — with fallback inference) or `lastRegularSeasonWeek` (MFL) from `league.settings_json`
   - If `week >= playoff_week_start`: `playoff_round = week - playoff_week_start + 1`
   - If `week > lastRegularSeasonWeek` (MFL): `playoff_round = week - lastRegularSeasonWeek`
   - Otherwise: `playoff_round = NULL`

4. **Store on Matchup model** — pass through from sync to DB

5. **Update API schemas** — add `playoff_round` and `is_consolation` to matchup response schemas (`MatchupSummary`, `Matchup`)

6. **Frontend** — show playoff round badge on matchup rows (e.g., "R1", "Semis", "Championship")

### PR 2: Bracket Data + Championship Detection (Both Platforms)

**Backend changes:**

1. **Sleeper adapter** — add `get_winners_bracket()` and `get_losers_bracket()` methods:
   ```python
   async def get_winners_bracket(self, league_id: str) -> list[dict]:
       async with httpx.AsyncClient(base_url=BASE_URL) as client:
           resp = await client.get(f"/league/{league_id}/winners_bracket")
           resp.raise_for_status()
           return resp.json()
   ```

2. **MFL adapter** — add `get_playoff_brackets()` and `get_playoff_bracket()` methods:
   ```python
   async def get_playoff_brackets(self, league_id: str) -> list[dict]:
       """Fetch all playoff brackets for a league."""
       data = await self._api_get("playoffBrackets", params={"L": league_id}, use_auth=True)
       brackets = data.get("playoffBrackets", {}).get("playoffBracket", [])
       return _ensure_list(brackets)

   async def get_playoff_bracket(self, league_id: str, bracket_id: str) -> dict:
       """Fetch detailed bracket with rounds and game results."""
       data = await self._api_get(
           "playoffBracket", params={"L": league_id, "BRACKET_ID": bracket_id}, use_auth=True
       )
       return data.get("playoffBracket", {})
   ```

3. **Consolation detection (both platforms):**
   - **Sleeper:** Fetch losers bracket → build set of roster_ids → mark those matchups as `is_consolation=true`
   - **MFL:** Fetch `playoffBrackets` → the championship bracket is the one with the most `teamsInvolved` (or whose `bracketWinnerTitle` contains "Champion"). All other brackets are consolation. Build franchise_id sets from non-championship bracket details → mark those matchups as `is_consolation=true`.

4. **Championship detection helpers:**

   Sleeper:
   ```python
   def detect_champion_sleeper(winners_bracket: list[dict]) -> str | None:
       """Return the roster_id of the championship winner."""
       final_round = max(m["r"] for m in winners_bracket)
       finals = [m for m in winners_bracket if m["r"] == final_round]
       if finals and finals[0].get("w"):
           return str(finals[0]["w"])
       return None
   ```

   MFL:
   ```python
   def detect_champion_mfl(bracket_detail: dict) -> str | None:
       """Return the franchise_id of the championship winner."""
       rounds = _ensure_list(bracket_detail.get("playoffRound", []))
       if not rounds:
           return None
       final_round = rounds[-1]  # last round is the championship
       games = _ensure_list(final_round.get("playoffGame", []))
       if not games:
           return None
       game = games[0]  # championship is a single game
       home = game.get("home", {})
       away = game.get("away", {})
       home_pts = float(home.get("points", 0))
       away_pts = float(away.get("points", 0))
       if home_pts > away_pts:
           return home.get("franchise_id")
       elif away_pts > home_pts:
           return away.get("franchise_id")
       return None  # tie — shouldn't happen in playoffs
   ```

5. **Fetch bracket data during league sync** — integrate bracket fetching into `sync_all()` / `sync_historical_seasons()` in the sync engine:
   - Skip for best ball and guillotine leagues
   - For Sleeper: call `get_winners_bracket()` and `get_losers_bracket()`
   - For MFL: call `get_playoff_brackets()` then `get_playoff_bracket()` for each bracket
   - Use bracket data to set `is_consolation` on existing matchup rows and detect the season champion
   - Store champion `user_league_id` on the league (or standings) for quick access

6. **New endpoint** — `GET /api/leagues/{league_id}/champion`:
   Returns `{ champion_team_name: str | null, champion_user_league_id: str | null }` for a given season. Or include this in the league detail response.

### Backfill Strategy

For existing synced matchups that don't have `playoff_round` set:

- **Option A (preferred):** Re-sync matchups for affected leagues. Since we already have the league settings with playoff week info, a re-sync will populate the new fields.
- **Option B:** One-time backfill script that reads `league.settings_json` and updates matchup rows based on week number.

---

## Testing

- Unit tests for playoff_round derivation logic (both platforms)
- Unit tests for championship detection from bracket data (Sleeper and MFL)
- Unit tests for consolation detection (multi-bracket MFL, losers bracket Sleeper)
- Test edge cases:
  - League with no playoffs configured
  - Best ball / guillotine leagues excluded from playoff detection
  - Sleeper fallback inference when `playoff_week_start` is missing
  - MFL leagues where `lastRegularSeasonWeek` is missing
  - Seasons still in progress (bracket `w` is null / points are "0")
  - MFL single-game playoff round (object instead of array — `_ensure_list`)
  - MFL league with multiple brackets (championship + 3rd place + consolation)
  - MFL bracket with first-round byes (top seeds appear in round 2)

---

## Out of Scope

- Head-to-head playoff bracket visualization (future feature)
- Playoff odds / projections
- Draft pick implications from playoff seeding
