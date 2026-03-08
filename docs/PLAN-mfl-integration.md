# Plan: MFL Integration

## Overview

Integrate MFL (MyFantasyLeague) as the second platform adapter, following the existing patterns established by Sleeper. This includes the adapter, player import, auth flow, frontend linking UI, cross-platform league grouping, and tests.

**Reference:** See [MFL_INTEGRATION.md](MFL_INTEGRATION.md) for API details, response formats, and data mapping.

---

## Phase 1: Foundation — Adapter + Auth

### 1.1 MFL Adapter (`backend/app/platforms/mfl.py`)

**New file.** Implements `PlatformAdapter` ABC with all 7 methods.

**Constructor change:** Unlike `SleeperAdapter()` which takes no args, `MFLAdapter` needs credentials for authenticated endpoints. Accept `credentials_json: dict | None = None` and `year: int | None = None` in the constructor.

```python
class MFLAdapter(PlatformAdapter):
    BASE_URL = "https://api.myfantasyleague.com"

    def __init__(self, credentials_json: dict | None = None, year: int | None = None):
        self.year = year or current_nfl_season()
        self.cookie = credentials_json.get("cookie") if credentials_json else None
        self._client = httpx.AsyncClient(timeout=30)
```

**Methods to implement:**

| Method | MFL Endpoint(s) | Notes |
|--------|-----------------|-------|
| `get_user(username)` | `POST /login` | Login with username/password, return cookie + user info. MFL has no "lookup user" — login _is_ user resolution. `username` param could be repurposed or we add a `login()` class method. |
| `get_leagues(user_id, season)` | `GET myleagues` | Requires auth cookie. `user_id` param unused (cookie identifies user). |
| `get_league(league_id)` | `GET league` | Public endpoint. Map `starters.position` limits to `roster_positions` list. |
| `get_league_users(league_id)` | `GET league` | Same endpoint — extract `franchises.franchise[]` as `PlatformLeagueUser` list. |
| `get_rosters(league_id)` | `GET rosters` | Map `player.status` to starters/taxi/IR lists. No starters info here. |
| `get_matchups(league_id, week)` | `GET schedule` + `GET weeklyResults` | Two calls needed: `schedule` for pairings, `weeklyResults` for starters/scores. |
| `get_transactions(league_id, week)` | `GET transactions` | Parse pipe/comma-delimited strings. Filter out `FP_*` draft pick IDs. |

**Helper methods:**

- `_request(endpoint, params)` — wraps HTTP calls with cookie header, rate limiting (`asyncio.sleep(1)` between calls), and error handling for 429s
- `_parse_league(data)` — normalizes MFL league JSON to `PlatformLeague` (similar to Sleeper's `_parse_league()`)
- `_expand_roster_positions(starters_config)` — converts MFL's limit ranges (e.g., QB "1-2", RB "1-6") into a flat `roster_positions` list
- `_detect_scoring_type(league_id)` — calls `GET rules` endpoint to determine PPR/half-PPR/standard
- `_detect_league_type(league_data)` — infers from `draftPlayerPool` ("Rookie" → dynasty, "Both" → redraft/keeper)

**MFL-specific considerations:**

- **Season in URL path:** MFL uses `/{year}/export` — the year must be part of every URL
- **History as previous_league_id:** MFL keeps the same `league_id` across seasons. For `previous_league_id`, store the same `league_id` for the prior year's season. The sync engine can detect "same league_id, different season" to avoid re-fetching the same league metadata.
- **Rate limiting:** 1 req/sec. Use a simple timestamp tracker in `_request()` with `asyncio.sleep()` to enforce.

### 1.2 Update Adapter Registry (`backend/app/platforms/registry.py`)

Modify `get_adapter()` to accept optional kwargs and pass them through:

```python
def get_adapter(platform_type: PlatformType, **kwargs) -> PlatformAdapter:
    adapters = {
        PlatformType.sleeper: SleeperAdapter,
        PlatformType.mfl: MFLAdapter,
    }
    adapter_cls = adapters.get(platform_type)
    if not adapter_cls:
        raise ValueError(f"No adapter for {platform_type}")
    return adapter_cls(**kwargs)
```

`SleeperAdapter.__init__` already accepts `**kwargs` (or add `**kwargs` to ignore extras).

### 1.3 MFL Login Endpoint (`backend/app/api/platforms.py`)

MFL requires username + password to get a cookie. The current `POST /api/platforms/accounts` flow sends `platform_username` but no password.

**Option A (recommended):** Add an MFL-specific login step:

```
POST /api/platforms/accounts/mfl/login
Body: { "username": "...", "password": "..." }
```

- Calls MFL login API to get cookie
- Creates `PlatformAccount` with `platform_type=mfl`, `platform_username`, `credentials_json={"cookie": "MFL_USER_ID=..."}`
- Returns the created account (same as existing flow)

The generic `POST /api/platforms/accounts` still works for platforms that don't need auth (Sleeper).

**Schema addition** (`backend/app/platforms/schemas.py` or `backend/app/schemas/`):

```python
class MFLLoginRequest(BaseModel):
    username: str
    password: str
```

### 1.4 Adapter Tests (`backend/tests/test_mfl_adapter.py`)

**New file.** Follow `test_sleeper_adapter.py` patterns with `respx` mocks.

Test cases:
- `test_get_leagues` — mock `myleagues` response, verify `PlatformLeague` list
- `test_get_league` — mock `league` response, verify metadata mapping
- `test_get_league_roster_positions` — verify limit range expansion (QB "1-2" etc.)
- `test_get_league_users` — verify franchise extraction
- `test_get_rosters` — mock `rosters`, verify player/taxi/IR categorization
- `test_get_matchups` — mock both `schedule` + `weeklyResults`, verify pairing + scores
- `test_get_transactions` — mock various types (FREE_AGENT, TRADE, BBID_WAIVER), verify parsing
- `test_detect_scoring_type` — mock `rules` endpoint
- `test_detect_league_type` — dynasty vs redraft detection
- `test_rate_limiting` — verify 1-second delays between requests
- `test_empty_responses` — handle empty/null responses gracefully
- `test_api_error` — handle 429, 500 responses

---

## Phase 2: Player Identity

### 2.1 MFL Player Import (`backend/app/sync/player_import.py`)

Add `get_or_create_player_by_mfl_id()` following the existing Sleeper pattern:

```python
async def get_or_create_player_by_mfl_id(
    db: AsyncSession, mfl_id: str, full_name: str,
    position: str | None = None, team: str | None = None,
) -> Player:
    # Same upsert pattern as get_or_create_player_by_sleeper_id
    # but conflicts on mfl_id instead of sleeper_id
```

### 2.2 MFL Players Bulk Import

Add a function to fetch and cache MFL's full player database:

```python
async def import_mfl_players(db: AsyncSession, adapter: MFLAdapter) -> dict[str, Player]:
    """Fetch MFL players API and upsert into players table. Returns {mfl_id: Player} map."""
```

- Calls `GET players?DETAILS=1&JSON=1`
- Upserts each player by `mfl_id`
- If `DETAILS=1` includes `sleeper_id` or other cross-platform IDs, populate those too
- Returns lookup dict for roster/matchup sync

### 2.3 Sync Engine Player Map (`backend/app/sync/engine.py`)

The sync engine currently builds a `players_map` keyed by Sleeper ID. Make this platform-aware:

```python
# Current (Sleeper-specific):
players_map[sleeper_id] = player

# Updated (platform-aware):
if platform_type == PlatformType.sleeper:
    players_map = await build_sleeper_players_map(db, adapter)
elif platform_type == PlatformType.mfl:
    players_map = await import_mfl_players(db, adapter)
```

The rest of the sync engine (roster creation, matchup starters) uses this map to resolve platform player IDs → internal `Player.id`.

---

## Phase 3: Sync Engine Adjustments

### 3.1 Week Count (`backend/app/sync/engine.py`)

Sleeper stores current week in `settings_json["leg"]`. MFL uses different fields:
- `startWeek` / `endWeek` / `lastRegularSeasonWeek` from league response
- Store these in `settings_json` during league sync
- Update week iteration: `range(1, settings_json.get("endWeek", settings_json.get("leg", 17)) + 1)`

### 3.2 Historical Season Walking

MFL keeps the same `league_id` across years. The existing chain-walking logic follows `previous_league_id` to find past seasons. For MFL:

- `previous_league_id` stores the same league ID (e.g., "40750") for the prior season
- The sync engine needs to also vary the `year` parameter when fetching historical data
- Adapter method calls need to use the correct year: `MFLAdapter(credentials_json=creds, year=2023)`

**Implementation:** In `sync_historical_seasons()`, when `platform_type == PlatformType.mfl`, create a new adapter instance with the historical year:

```python
if platform_type == PlatformType.mfl:
    hist_adapter = get_adapter(platform_type, credentials_json=creds, year=past_season)
    past_league = await hist_adapter.get_league(prev_league_id)
```

### 3.3 Standings Sync

MFL provides standings directly via `leagueStandings` endpoint (W/L/T, PF). Currently, `sync_standings()` computes standings from matchup data. For MFL, optionally pull from the API directly for accuracy:

- Add `get_standings(league_id)` to the adapter ABC (optional method with default implementation that returns `None`)
- If adapter returns standings, use them; otherwise fall back to computing from matchups

### 3.4 Credentials Propagation

The sync engine calls `get_adapter(platform_type)` with no credentials. Update `sync_all()` to pass credentials from the `PlatformAccount`:

```python
adapter = get_adapter(
    account.platform_type,
    credentials_json=account.credentials_json,
    year=season,
)
```

This also requires updating `sync_all()`'s callers (the sync API endpoint) to pass the account object or credentials.

---

## Phase 4: Cross-Platform League Grouping

### 4.1 Add `league_group_id` Column

**Model change** (`backend/app/models/league.py`):
```python
league_group_id: Mapped[uuid.UUID | None] = mapped_column(sa.Uuid, nullable=True, index=True)
```

**Migration** (`backend/alembic/`):
1. Add nullable `league_group_id` column
2. Backfill: walk existing `previous_league_id` chains and assign a shared UUID to each chain
3. For leagues with no chain, assign a unique UUID to each

### 4.2 Auto-Assign During Sync (`backend/app/sync/engine.py`)

When syncing a league chain:
- If any league in the chain already has a `league_group_id`, use it for all
- Otherwise generate a new UUID and set it on all leagues in the chain
- Apply during both `sync_leagues()` and `sync_historical_seasons()`

### 4.3 Link/Unlink API Endpoints (`backend/app/api/leagues.py`)

**Link:**
```
POST /api/leagues/{league_id}/link
Body: { "target_league_id": "uuid" }
```
- Validate both leagues belong to requesting user (via `user_leagues`)
- Get both `league_group_id` values
- Update all leagues with target's group ID to use source's group ID
- Return updated season list

**Unlink:**
```
POST /api/leagues/{league_id}/unlink
Body: { "platform_type": "mfl" }
```
- Find all leagues in the group with the specified `platform_type`
- Assign them a new `league_group_id`
- Return updated season list

### 4.4 Simplify Season Chain Query (`backend/app/api/leagues.py`)

Replace the current `_get_season_chain()` function (which walks `previous_league_id` forward and backward) with a simple query:

```python
async def _get_season_chain(db, league):
    group_id = league.league_group_id
    if not group_id:
        return [league]
    result = await db.execute(
        select(League).where(League.league_group_id == group_id).order_by(League.season.desc())
    )
    return list(result.scalars().all())
```

### 4.5 Simplify Dashboard Dedup (`backend/app/api/leagues.py`)

Replace the correlated subquery in `GET /api/leagues?latest=true` with:

```sql
SELECT DISTINCT ON (league_group_id) *
FROM leagues
WHERE league_group_id IN (user's leagues)
ORDER BY league_group_id, season DESC
```

This naturally returns the most recent season per group, regardless of platform.

### 4.6 Frontend Season Selector Labels

When a league group spans multiple platforms, show the platform in the season selector:

```
2025  (Sleeper)
2024  (Sleeper)
2023  (MFL)
```

If all seasons are the same platform, omit the label (no change from current behavior).

**Files:** `frontend/src/pages/LeagueDetailPage.tsx`, league seasons API response (add `platform_type` to each season entry).

---

## Phase 5: Frontend — MFL Account Linking

### 5.1 Platform Selector (`frontend/src/pages/LinkAccountsPage.tsx`)

Replace the hardcoded "Link Sleeper Account" form with a platform picker:

- Tab bar or dropdown: `Sleeper | MFL`
- Sleeper tab: existing username-only form (unchanged)
- MFL tab: username + password form → calls `POST /api/platforms/accounts/mfl/login`
- After linking, discovery + sync flow is identical (platform-agnostic)

### 5.2 League Linking UI (`frontend/src/pages/LeagueDetailPage.tsx`)

Add "Link to another league" action in the league header (only shown when user has leagues on 2+ platforms):

- Opens modal with list of other league groups (filtered to exclude current group)
- Shows suggested matches first (same/similar name, same team count, same type)
- Confirm dialog explains what linking does
- Calls `POST /api/leagues/{id}/link`
- Season selector refreshes with merged history

See [MFL_INTEGRATION.md Section 5](MFL_INTEGRATION.md#5-cross-platform-league-linking) for detailed UI wireframes.

---

## Phase 6: Testing

### 6.1 Unit Tests — MFL Adapter
Already covered in Phase 1.4.

### 6.2 Integration Tests — Sync Engine with MFL

Add tests to `backend/tests/test_sync_engine.py`:
- `test_sync_mfl_league` — mock MFL adapter, verify full sync creates correct DB records
- `test_sync_mfl_historical_seasons` — verify year-based chain walking
- `test_sync_mfl_credentials_propagation` — verify adapter gets credentials from account

### 6.3 API Tests — MFL Login + Discovery

Add tests to `backend/tests/test_platform_accounts.py`:
- `test_mfl_login` — mock MFL login endpoint, verify cookie stored
- `test_mfl_login_invalid_credentials` — verify error handling

Add tests to `backend/tests/test_leagues_api.py`:
- `test_discover_mfl_leagues` — mock adapter, verify discovery
- `test_league_group_link` — link two league groups, verify merged season chain
- `test_league_group_unlink` — unlink by platform, verify split

### 6.4 Frontend Tests

- `LinkAccountsPage` — test MFL form renders, submits correctly
- `LeagueDetailPage` — test season selector with mixed platforms

---

## Execution Strategy

This plan is split into 4 PRs, executed sequentially. Each PR uses parallel agents where possible.

---

### PR 1: MFL Adapter + Player Import (Phases 1 + 2)

Core MFL adapter, login endpoint, player import, and tests. This is the foundation everything else builds on.

**Wave 1 — 3 parallel agents:**

| Agent | Work | Files |
|-------|------|-------|
| **Agent A: MFL Adapter** | Phase 1.1 — `MFLAdapter` class with all 7 ABC methods, helper methods, rate limiting | **Create** `backend/app/platforms/mfl.py` |
| **Agent B: Player Import** | Phase 2.1 — `get_or_create_player_by_mfl_id()` + Phase 2.2 bulk import function | Modify `backend/app/sync/player_import.py` |
| **Agent C: MFL Login Endpoint** | Phase 1.3 — `POST /api/platforms/accounts/mfl/login`, `MFLLoginRequest` schema | Modify `backend/app/api/platforms.py` |

**Wave 2 — 1 agent (sequential, depends on Wave 1):**

| Agent | Work | Files |
|-------|------|-------|
| **Agent D: Integration + Tests + Docs** | Phase 1.2 registry update, Phase 1.4 adapter tests, Phase 2.3 sync engine player map, doc updates | Modify `backend/app/platforms/registry.py`, **Create** `backend/tests/test_mfl_adapter.py`, Modify `backend/app/sync/engine.py`, Modify `docs/PRODUCT.md` |

**PR 1 total: 4 agents (3 parallel + 1 sequential)**

---

### PR 2: Sync Engine Adjustments (Phase 3)

Adapt the sync engine to handle MFL's differences — week counting, year-based history walking, standings API, credentials propagation.

**Single agent — changes are tightly coupled:**

| Files | Changes |
|-------|---------|
| `backend/app/sync/engine.py` | Week count logic, historical season walking with year param, credentials propagation |
| `backend/app/platforms/base.py` | Optional `get_standings()` method on ABC |
| `backend/app/platforms/mfl.py` | Implement `get_standings()` |
| `backend/app/api/sync.py` | Pass account credentials to adapter |
| `backend/tests/test_sync_engine.py` | MFL sync integration tests |

**PR 2 total: 1 agent**

---

### PR 3: Cross-Platform League Grouping (Phase 4)

`league_group_id` column, link/unlink API, simplified season chain and dashboard dedup queries.

**Wave 1 — 2 parallel agents:**

| Agent | Work | Files |
|-------|------|-------|
| **Agent A: Schema + Migration + Docs** | Phase 4.1 — add `league_group_id` column, migration with backfill, Phase 4.2 auto-assign in sync, update data model docs | Modify `backend/app/models/league.py`, **Create** migration, Modify `backend/app/sync/engine.py`, Modify `docs/DATA_MODEL.md` |
| **Agent B: API + Tests** | Phase 4.3-4.5 — link/unlink endpoints, simplified season chain query, dashboard dedup | Modify `backend/app/api/leagues.py`, Modify `backend/tests/test_leagues_api.py` |

Note: Agent B can write against the model change from Agent A — both agents know the column name and semantics. Merge conflicts (if any) will be trivial.

**PR 3 total: 2 agents (parallel)**

---

### PR 4: Frontend (Phase 5)

Platform selector on LinkAccounts, MFL login form, league linking UI, and frontend tests.

**Wave 1 — 2 parallel agents:**

| Agent | Work | Files |
|-------|------|-------|
| **Agent A: Platform Selector** | Phase 5.1 — tab bar (Sleeper/MFL), MFL username+password form, API client for MFL login | Modify `frontend/src/pages/LinkAccountsPage.tsx`, Modify `frontend/src/api/` |
| **Agent B: League Linking UI** | Phase 5.2 — "Link to another league" modal, confirm dialog, unlink action, season selector labels | Modify `frontend/src/pages/LeagueDetailPage.tsx`, Modify `frontend/src/api/` |

**PR 4 total: 2 agents (parallel)**

---

### Summary

| PR | Agents | Parallel | Sequential | Total |
|----|--------|----------|------------|-------|
| PR 1: Adapter + Player Import | 4 | 3 (Wave 1) | 1 (Wave 2) | 4 |
| PR 2: Sync Engine | 1 | — | 1 | 1 |
| PR 3: League Grouping | 2 | 2 | — | 2 |
| PR 4: Frontend | 2 | 2 | — | 2 |
| **Total** | **9** | | | |

---

## Files Changed Summary

### PR 1 — Adapter + Player Import
| File | Action | Agent |
|------|--------|-------|
| `backend/app/platforms/mfl.py` | **Create** | A |
| `backend/app/sync/player_import.py` | Modify | B |
| `backend/app/api/platforms.py` | Modify | C |
| `backend/app/platforms/registry.py` | Modify | D |
| `backend/tests/test_mfl_adapter.py` | **Create** | D |
| `backend/app/sync/engine.py` | Modify | D |
| `docs/PRODUCT.md` | Modify (update MFL status) | D |

### PR 2 — Sync Engine
| File | Action |
|------|--------|
| `backend/app/sync/engine.py` | Modify |
| `backend/app/platforms/base.py` | Modify |
| `backend/app/platforms/mfl.py` | Modify |
| `backend/app/api/sync.py` | Modify |
| `backend/tests/test_sync_engine.py` | Modify |

### PR 3 — League Grouping
| File | Action | Agent |
|------|--------|-------|
| `backend/app/models/league.py` | Modify | A |
| `backend/alembic/versions/` | **Create** | A |
| `backend/app/sync/engine.py` | Modify | A |
| `docs/DATA_MODEL.md` | Modify | A |
| `backend/app/api/leagues.py` | Modify | B |
| `backend/tests/test_leagues_api.py` | Modify | B |
| `docs/DATA_MODEL.md` | Modify | A |

### PR 4 — Frontend
| File | Action | Agent |
|------|--------|-------|
| `frontend/src/pages/LinkAccountsPage.tsx` | Modify | A |
| `frontend/src/pages/LeagueDetailPage.tsx` | Modify | B |
| `frontend/src/api/` | Modify | A + B |

