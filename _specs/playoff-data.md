# Feature: Playoff Data & Championship Detection

**Branch:** `feat/playoff-data`
**Spec:** `docs/SPEC-playoff-data.md`

---

## Overview

Add playoff metadata to matchups so the app can distinguish regular season from playoff matchups, identify championship winners, and separate winners bracket from consolation. This is a prerequisite for the franchise history page.

---

## PR Breakdown

### PR 1: Schema + Playoff Round Detection

#### 1.1 Alembic Migration

Add two columns to the `matchups` table:

```python
# New columns
playoff_round: Integer, nullable=True        # NULL=regular season, 1=wildcard, 2=semis, 3=finals
is_consolation: Boolean, nullable=False, server_default="false"
```

**Files:**
- `backend/alembic/versions/xxxx_add_playoff_columns.py` — new migration

#### 1.2 SQLAlchemy Model Update

**File:** `backend/app/models/matchup.py`

Add to `Matchup` class:
```python
playoff_round: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
is_consolation: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
```

#### 1.3 Platform Schema Update

**File:** `backend/app/platforms/schemas.py`

Add fields to `PlatformMatchup` dataclass:
```python
playoff_round: int | None = None
is_consolation: bool = False
```

#### 1.4 Playoff Round Derivation Logic

**File:** `backend/app/sync/engine.py` — modify `sync_matchups()`

Add a helper to compute playoff_round from league settings:

```python
def _get_playoff_round(league: League, week: int) -> int | None:
    """Derive playoff round from league settings and week number.

    Returns None for regular season, 1+ for playoff rounds.
    Skips best ball and guillotine leagues (no playoffs).
    """
    if league.league_type in ("bestball", "guillotine"):
        return None

    settings = league.settings_json or {}

    if league.platform_type == PlatformType.sleeper:
        playoff_start = settings.get("playoff_week_start")
        if not playoff_start:
            # Fallback: infer from total weeks and playoff_teams
            playoff_teams = settings.get("playoff_teams", 0)
            if not playoff_teams:
                return None
            import math
            num_rounds = math.ceil(math.log2(playoff_teams))
            total_weeks = settings.get("leg", 17)  # leg = current/total week
            playoff_start = total_weeks - num_rounds + 1
        playoff_start = int(playoff_start)
    elif league.platform_type == PlatformType.mfl:
        last_reg = settings.get("lastRegularSeasonWeek")
        if not last_reg:
            return None
        playoff_start = int(last_reg) + 1
    else:
        return None

    if week >= playoff_start:
        return week - playoff_start + 1
    return None
```

In `sync_matchups()`, after building the `Matchup` object, set:
```python
matchup.playoff_round = _get_playoff_round(league, week)
```

#### 1.5 Pydantic Response Schemas

**File:** `backend/app/schemas/league.py`

Add to `MatchupRead`:
```python
playoff_round: int | None = None
is_consolation: bool = False
```

Add to `MatchupSummaryRead`:
```python
playoff_round: int | None = None
is_consolation: bool = False
```

#### 1.6 API Response Construction

**File:** `backend/app/api/leagues.py`

Update all `MatchupRead(...)` and `MatchupSummaryRead(...)` constructions to pass through the new fields:
```python
playoff_round=m.playoff_round,
is_consolation=m.is_consolation,
```

There are 3 locations:
- `get_league_detail()` (~line 252) — `MatchupRead` for recent_matchups
- `get_matchup_summary()` (~line 627) — `MatchupSummaryRead`
- `get_matchup_detail()` (~line 699) — `MatchupRead`

#### 1.7 Frontend Types

**File:** `frontend/src/api/types.ts`

Add to `Matchup` interface:
```typescript
playoff_round: number | null;
is_consolation: boolean;
```

Add to `MatchupSummary` interface:
```typescript
playoff_round: number | null;
is_consolation: boolean;
```

#### 1.8 Frontend UI — Playoff Badges

**File:** `frontend/src/pages/LeagueDetailPage.tsx`

In the `LazyMatchupsTab`, add a badge next to the week label for playoff matchups:

Display logic:
- `playoff_round === null` → no badge (regular season)
- `is_consolation === true` → gray "Consolation" badge
- `playoff_round === 1` → "Round 1" badge
- `playoff_round === 2` → "Semis" badge
- `playoff_round === max_round` → "Championship" badge (determine max from all summaries)

#### 1.9 Data Model Docs

**File:** `docs/DATA_MODEL.md`

Add `playoff_round` and `is_consolation` to the `matchups` table documentation.

#### 1.10 Tests

**File:** `backend/tests/unit/test_playoff_round.py`

Unit tests for `_get_playoff_round()`:
- Sleeper league with `playoff_week_start=15` → week 14 returns None, week 15 returns 1, week 17 returns 3
- Sleeper fallback inference: `playoff_teams=6`, no `playoff_week_start` → correctly infers start week
- MFL league with `lastRegularSeasonWeek="14"` → week 14 returns None, week 15 returns 1
- Best ball league → always returns None
- Guillotine league → always returns None
- Missing settings → returns None

---

### PR 2: Bracket Data + Championship Detection

#### 2.1 Platform Adapter ABC Update

**File:** `backend/app/platforms/base.py`

Add optional bracket methods to `PlatformAdapter` ABC (with default no-op implementations):
```python
async def get_winners_bracket(self, league_id: str) -> list[dict]:
    return []

async def get_losers_bracket(self, league_id: str) -> list[dict]:
    return []
```

#### 2.2 Sleeper Adapter — Bracket Methods

**File:** `backend/app/platforms/sleeper.py`

Add two methods:
```python
async def get_winners_bracket(self, league_id: str) -> list[dict]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.get(f"/league/{league_id}/winners_bracket")
        resp.raise_for_status()
        return resp.json()

async def get_losers_bracket(self, league_id: str) -> list[dict]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        resp = await client.get(f"/league/{league_id}/losers_bracket")
        resp.raise_for_status()
        return resp.json()
```

#### 2.3 MFL Adapter — Bracket Methods

**File:** `backend/app/platforms/mfl.py`

Add two methods:
```python
async def get_playoff_brackets(self, league_id: str) -> list[dict]:
    """Fetch all playoff bracket summaries for a league."""
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

Override the ABC bracket methods to delegate through MFL's bracket API:
```python
async def get_winners_bracket(self, league_id: str) -> list[dict]:
    """Get the championship bracket detail as a list of round dicts."""
    brackets = await self.get_playoff_brackets(league_id)
    if not brackets:
        return []
    # Championship bracket = most teams involved
    champ = max(brackets, key=lambda b: int(b.get("teamsInvolved", 0)))
    detail = await self.get_playoff_bracket(league_id, champ["id"])
    return _ensure_list(detail.get("playoffRound", []))

async def get_losers_bracket(self, league_id: str) -> list[dict]:
    """Get consolation bracket franchise IDs."""
    brackets = await self.get_playoff_brackets(league_id)
    if len(brackets) <= 1:
        return []
    champ_id = max(brackets, key=lambda b: int(b.get("teamsInvolved", 0)))["id"]
    consolation_franchise_ids = set()
    for bracket in brackets:
        if bracket["id"] == champ_id:
            continue
        detail = await self.get_playoff_bracket(league_id, bracket["id"])
        for rnd in _ensure_list(detail.get("playoffRound", [])):
            for game in _ensure_list(rnd.get("playoffGame", [])):
                for side in ("home", "away"):
                    fid = game.get(side, {}).get("franchise_id")
                    if fid:
                        consolation_franchise_ids.add(fid)
    return [{"franchise_ids": list(consolation_franchise_ids)}]
```

#### 2.4 Championship Detection Helpers

**File:** `backend/app/sync/playoffs.py` (new file)

```python
def detect_champion_sleeper(winners_bracket: list[dict]) -> str | None:
    """Return the roster_id of the championship winner from Sleeper bracket data."""
    if not winners_bracket:
        return None
    final_round = max(m["r"] for m in winners_bracket)
    finals = [m for m in winners_bracket if m["r"] == final_round]
    if finals and finals[0].get("w"):
        return str(finals[0]["w"])
    return None

def detect_champion_mfl(bracket_detail: dict) -> str | None:
    """Return the franchise_id of the championship winner from MFL bracket data."""
    rounds = _ensure_list(bracket_detail.get("playoffRound", []))
    if not rounds:
        return None
    final_round = rounds[-1]
    games = _ensure_list(final_round.get("playoffGame", []))
    if not games:
        return None
    game = games[0]
    home = game.get("home", {})
    away = game.get("away", {})
    home_pts = float(home.get("points", 0))
    away_pts = float(away.get("points", 0))
    if home_pts > away_pts:
        return home.get("franchise_id")
    elif away_pts > home_pts:
        return away.get("franchise_id")
    return None

def get_consolation_roster_ids_sleeper(losers_bracket: list[dict]) -> set[str]:
    """Extract all roster_ids that appear in the losers bracket."""
    ids = set()
    for m in losers_bracket:
        for key in ("t1", "t2", "w", "l"):
            val = m.get(key)
            if val is not None:
                ids.add(str(val))
    return ids

def get_consolation_franchise_ids_mfl(consolation_data: list[dict]) -> set[str]:
    """Extract franchise_ids from MFL consolation bracket data."""
    if not consolation_data:
        return set()
    return set(consolation_data[0].get("franchise_ids", []))
```

#### 2.5 Sync Engine Integration — Bracket Fetching

**File:** `backend/app/sync/engine.py`

Add a new `sync_playoff_data()` method that:
1. Skips best ball and guillotine leagues
2. Fetches winners bracket and losers bracket via adapter
3. Detects the champion (store as champion_user_league_id somewhere — league.settings_json or a new field)
4. Builds consolation roster/franchise ID sets
5. Updates existing matchup rows where `playoff_round IS NOT NULL`:
   - Sets `is_consolation=True` for matchups involving consolation bracket teams

Call `sync_playoff_data()` from:
- `sync_all()` — after matchup data is available (for current season, matchups are lazy-loaded so bracket data may need to update matchups later)
- `_sync_historical_league_data()` — for historical seasons

**Important consideration:** Matchups are lazy-loaded, so bracket data may be fetched before matchup rows exist. The sync should:
1. Store bracket data in `league.settings_json` (under a `bracket_data` key) during initial sync
2. Apply `is_consolation` to matchup rows when they are later fetched/synced (check stored bracket data)

#### 2.6 Apply Consolation Flag During Lazy Matchup Sync

**File:** `backend/app/sync/engine.py` — modify `sync_matchups()`

After syncing matchups for a week, if the week is a playoff week:
1. Read stored bracket data from `league.settings_json`
2. Check if the matchup involves consolation bracket teams
3. Set `is_consolation=True` on those matchup rows

#### 2.7 Champion Endpoint

**File:** `backend/app/api/leagues.py`

Add to the `LeagueDetailRead` response schema (or create a separate endpoint):
```python
champion_team_name: str | None = None
```

Populate from stored bracket/champion data during league detail construction.

#### 2.8 Tests

**File:** `backend/tests/unit/test_playoffs.py`

- `test_detect_champion_sleeper` — bracket with clear winner, in-progress bracket (w=null)
- `test_detect_champion_mfl` — bracket with clear winner, single-game final round
- `test_consolation_roster_ids_sleeper` — extract from losers bracket
- `test_consolation_franchise_ids_mfl` — extract from multi-bracket response
- `test_no_brackets` — best ball league returns empty, guillotine returns empty
- `test_mfl_ensure_list` — single-game playoff round (object not array)

**File:** `backend/tests/unit/test_mfl_adapter.py` — add tests for new bracket methods
**File:** `backend/tests/unit/test_sleeper_adapter.py` — add tests for new bracket methods (if file exists, otherwise create)

### Backfill Strategy

After both PRs are merged, existing matchups can be updated by:
- **Re-syncing leagues** — the sync will populate `playoff_round` and `is_consolation`
- No separate migration backfill needed since re-sync is the intended path

---

## Files Changed Summary

### PR 1
| File | Change |
|------|--------|
| `backend/alembic/versions/xxxx_add_playoff_columns.py` | New migration |
| `backend/app/models/matchup.py` | Add `playoff_round`, `is_consolation` columns |
| `backend/app/platforms/schemas.py` | Add fields to `PlatformMatchup` |
| `backend/app/sync/engine.py` | Add `_get_playoff_round()`, call in `sync_matchups()` |
| `backend/app/schemas/league.py` | Add fields to `MatchupRead`, `MatchupSummaryRead` |
| `backend/app/api/leagues.py` | Pass through new fields in 3 response constructions |
| `frontend/src/api/types.ts` | Add fields to `Matchup`, `MatchupSummary` |
| `frontend/src/pages/LeagueDetailPage.tsx` | Playoff round badges in matchup rows |
| `docs/DATA_MODEL.md` | Document new columns |
| `backend/tests/unit/test_playoff_round.py` | New test file |

### PR 2
| File | Change |
|------|--------|
| `backend/app/platforms/base.py` | Add bracket ABC methods |
| `backend/app/platforms/sleeper.py` | Add `get_winners_bracket()`, `get_losers_bracket()` |
| `backend/app/platforms/mfl.py` | Add bracket methods (4 new methods) |
| `backend/app/sync/playoffs.py` | New file — champion detection + consolation helpers |
| `backend/app/sync/engine.py` | Add `sync_playoff_data()`, integrate into sync flow |
| `backend/app/schemas/league.py` | Add `champion_team_name` to `LeagueDetailRead` |
| `backend/app/api/leagues.py` | Populate champion in league detail |
| `backend/tests/unit/test_playoffs.py` | New test file |
| `backend/tests/unit/test_mfl_adapter.py` | Add bracket method tests |
