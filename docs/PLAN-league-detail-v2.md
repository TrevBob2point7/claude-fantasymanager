# Implementation Plan: League Detail v2

> Overview tab, historical sync, slot inference, bye weeks, and dashboard deduplication.
>
> **Spec source:** [UI.md — League Detail](UI.md#league-detail-leaguesleagueid) and [DATA_MODEL.md](DATA_MODEL.md)

---

## Team

| Agent | Role | Phases | Description |
|---|---|---|---|
| **lead** | Coordinator | — | Orchestrates tasks, runs migrations, reviews, unblocks |
| **backend-sync** | Platform adapters & sync engine | 0.1, 1.1, 2, 3, 4 | Owns the adapter layer, slot inference, and historical sync. Writes contract tests first, then implements. |
| **backend-data** | Data modules & API layer | 0.2, 1.2, 5, 6 | Owns bye week integration and all API endpoint changes. Writes contract tests first, then implements. |
| **frontend** | React UI | 7, 8 | Owns all frontend changes. Starts early with TypeScript types and component scaffolding using mock data. Wires up to real API once phase 6 lands. |
| **qa-docs** | Quality assurance & documentation | 9 | Validates each phase's output: runs tests, checks integration contracts between agents, updates project documentation. Activates at natural checkpoints between phases. |

### Parallelism Timeline

```
Time →

backend-sync:  [0.1 tests] → [1.1 migration] → [2 adapter] → [3 slot inference] → [4 historical sync] ── done
backend-data:  [0.2 tests] → [1.2 migration] → [5 bye weeks] ──── wait ──── → [6 API changes] ────────── done
frontend:      ──────────── [7.8 types] → [7.1-7.5 scaffold] ──── wait ──── → [7.6-7.9 wire up] → [8] ── done
qa-docs:           ▲ QA-0           ▲ QA-1          ▲ QA-2                       ▲ QA-3            ▲ QA-4
                  tests          migrations      sync+bye                        API              final
```

**Key handoff points:**
- Phase 0 tests are written first by both backend agents in parallel — qa-docs validates they run (all failing) at QA-0
- backend-data waits for backend-sync to finish phases 3-4 before starting phase 6 (API needs slot + sync changes in place)
- frontend waits for backend-data to finish phase 6 before wiring up components to real endpoints
- frontend CAN scaffold all components and update types in parallel with backend work
- qa-docs activates at 5 checkpoints between phases to validate work and update docs

---

## Phase 0: Test-First Contracts

Write failing tests that define the expected behavior for each phase. These serve as executable specs — agents implement until tests pass. All tests should be runnable (but failing) before any implementation begins.

### Task 0.1: Adapter & Sync Engine Tests
**Owner: backend-sync**

File: `backend/tests/test_sleeper_adapter.py` (extend existing)

**`get_league()` tests:**
- `test_get_league_returns_platform_league` — mock Sleeper `GET /league/{id}` response, verify `PlatformLeague` has `previous_league_id` and `roster_positions` populated
- `test_get_league_missing_previous_league_id` — response without `previous_league_id` → field is `None`
- `test_get_leagues_includes_new_fields` — verify existing `get_leagues()` also extracts `previous_league_id` and `roster_positions`

File: `backend/tests/test_sync_engine.py` (extend existing)

**Slot inference tests:**
- `test_sync_rosters_assigns_slot_labels` — given `roster_positions=["QB","RB","RB","WR","WR","TE","FLEX","BN","BN","IR"]` and `starters=["p1","p2","p3","p4","p5","p6","p7"]`, verify slots are `QB, RB, RB, WR, WR, TE, FLEX` (not `"STARTER"`)
- `test_sync_rosters_empty_roster_positions` — when `roster_positions` is absent from `settings_json`, fall back to `"STARTER"` for backward compatibility
- `test_sync_rosters_starter_count_mismatch` — fewer starters than starter slots → only assign slots for available starters, rest get `None`

**Historical sync tests:**
- `test_sync_historical_walks_chain` — mock adapter with 2 past leagues chained via `previous_league_id`, verify all 3 seasons end up in DB
- `test_sync_historical_skips_existing` — if a past season league already exists in DB, skip it and stop walking
- `test_sync_historical_handles_no_previous` — league with `previous_league_id=None` → no historical sync attempted

### Task 0.2: Bye Week & API Contract Tests
**Owner: backend-data**

File: `backend/tests/test_bye_weeks.py` (new)

**Bye week sync tests:**
- `test_sync_bye_weeks_parses_espn_response` — mock ESPN API response with 2-3 teams, verify `team_bye_weeks` rows are created with correct `season`, `team` (uppercased), `bye_week`
- `test_sync_bye_weeks_normalizes_team_abbrev` — ESPN returns `"Atl"`, DB stores `"ATL"`
- `test_sync_bye_weeks_skips_fa_entry` — FA team with `byeWeek=0` is excluded
- `test_sync_bye_weeks_upserts_on_conflict` — running sync twice for same season updates existing rows
- `test_sync_bye_weeks_handles_espn_failure` — HTTP error from ESPN raises gracefully (doesn't crash caller)

File: `backend/tests/test_leagues_api.py` (extend existing)

**API contract tests:**
- `test_league_detail_includes_roster_status` — roster entries include `status` field (from player model)
- `test_league_detail_includes_bye_week` — roster entries include `bye_week` field (joined from `team_bye_weeks`)
- `test_league_detail_includes_current_week` — response includes `current_week` field
- `test_league_detail_roster_has_slot_labels` — roster entries have slot values like `"QB"`, `"FLEX"` (not `"STARTER"`)
- `test_get_league_seasons_returns_chain` — new endpoint returns `[{season, league_id}]` sorted by season desc
- `test_get_league_seasons_single_season` — league with no `previous_league_id` returns single-entry list
- `test_list_leagues_filters_current_season` — `GET /api/leagues` only returns leagues matching current year

---

## Phase 1: Data Model & Migrations

All backend schema changes. No API or frontend changes yet.

### Task 1.1: Add `previous_league_id` to leagues table
**Owner: backend-sync**

**Alembic migration** to add:
```sql
ALTER TABLE leagues ADD COLUMN previous_league_id VARCHAR(100);
```

**Update SQLAlchemy model** (`backend/app/models/league.py`):
- Add `previous_league_id: Mapped[str | None] = mapped_column(sa.String(100), nullable=True)`

### Task 1.2: Create `team_bye_weeks` table
**Owner: backend-data**

**Alembic migration** to create:
```sql
CREATE TABLE team_bye_weeks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    season INTEGER NOT NULL,
    team VARCHAR(10) NOT NULL,
    bye_week INTEGER NOT NULL,
    UNIQUE (season, team)
);
```

**Create SQLAlchemy model** (`backend/app/models/team_bye_week.py`):
- Standard model with `season`, `team`, `bye_week`
- Add to `backend/app/models/__init__.py` exports

---

## Phase 2: Platform Adapter Changes
**Owner: backend-sync**

### Task 2.1: Update `PlatformLeague` schema

File: `backend/app/platforms/schemas.py`

Add to `PlatformLeague`:
```python
previous_league_id: str | None = None
roster_positions: list[str] | None = None
```

### Task 2.2: Add `get_league()` to adapter base class

File: `backend/app/platforms/base.py`

Add abstract method:
```python
@abstractmethod
async def get_league(self, league_id: str) -> PlatformLeague: ...
```

### Task 2.3: Implement Sleeper `get_league()` and update `get_leagues()`

File: `backend/app/platforms/sleeper.py`

- **`get_league(league_id)`**: Call `GET /league/{league_id}`, parse response into `PlatformLeague` with `previous_league_id` and `roster_positions`
- **`get_leagues()`**: Extract `previous_league_id` (from `lg.get("previous_league_id")`) and `roster_positions` (from `lg.get("roster_positions")`) into the `PlatformLeague` — both fields are on the league response already, just not extracted

### Task 2.4: Store `roster_positions` in `settings_json`

Currently `settings_json` stores `lg.get("settings")` which is the `settings` sub-object. But `roster_positions` is a **top-level** field on the Sleeper league response, not inside `settings`.

**Approach:** Merge it into `settings_json` during sync: `settings_json = {**lg.get("settings", {}), "roster_positions": lg.get("roster_positions")}`. This keeps the schema simple — `roster_positions` is read from `settings_json` when needed.

---

## Phase 3: Sync Engine — Slot Inference
**Owner: backend-sync**

### Task 3.1: Update roster sync to assign actual slot labels

File: `backend/app/sync/engine.py` — `sync_rosters()`

Current:
```python
if player_id_str in pr.starters:
    slot = "STARTER"
```

New logic:
```python
# Get roster_positions from league settings_json
roster_positions = league.settings_json.get("roster_positions", []) if league.settings_json else []
starter_slots = [pos for pos in roster_positions if pos not in ("BN", "IR")]

# Build starter → slot mapping
starter_slot_map = {}
for i, player_id in enumerate(pr.starters):
    if i < len(starter_slots):
        starter_slot_map[player_id] = starter_slots[i]

# In the player loop:
if player_id_str in starter_slot_map:
    slot = starter_slot_map[player_id_str]
elif player_id_str in pr.taxi:
    slot = "TAXI"
else:
    slot = None
```

**Note:** `sync_rosters()` takes a `league` parameter — it needs access to `league.settings_json` which should already have `roster_positions` merged in after task 2.4.

---

## Phase 4: Sync Engine — Historical Season Walk
**Owner: backend-sync**

### Task 4.1: Extract `previous_league_id` during league sync

File: `backend/app/sync/engine.py` — `sync_leagues()`

When upserting leagues, include `previous_league_id` from `PlatformLeague.previous_league_id`. Add it to both the `.values()` and `.on_conflict_do_update()` calls.

### Task 4.2: Add `sync_historical_seasons()` to SyncEngine

New method that:
1. Takes a league that was just synced
2. Reads its `previous_league_id`
3. Checks if that league already exists in our DB (by `platform_type` + `platform_league_id`)
4. If not, calls `adapter.get_league(previous_league_id)` to get the past season's league data
5. Upserts the league record (including `previous_league_id` and merged `settings_json`)
6. Creates `user_league` entries (using same `owner_id` matching logic)
7. Calls `sync_rosters()`, `sync_matchups()` (for all weeks up to `settings.leg`), `sync_transactions()`, `sync_standings()`
8. Recurses on that league's `previous_league_id`
9. Adds a small courtesy delay (50-100ms) between API calls via `asyncio.sleep(0.05)`

### Task 4.3: Wire historical sync into `sync_all()`

After syncing all current-season leagues (and their rosters/matchups/standings/transactions), call `sync_historical_seasons()` for each league that has a `previous_league_id`.

---

## Phase 5: Bye Week Data
**Owner: backend-data**

### Task 5.1: Create bye week sync module

New file: `backend/app/sync/bye_weeks.py`

```python
async def sync_bye_weeks(db: AsyncSession, season: int) -> None:
    """Fetch bye weeks from ESPN and upsert into team_bye_weeks table."""
    url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}?view=proTeamSchedules_wl"
    # Fetch, parse settings.proTeams
    # Filter out FA entry (byeWeek == 0)
    # Normalize abbrev to uppercase (.upper())
    # Upsert into team_bye_weeks
```

### Task 5.2: Trigger bye week sync

Call `sync_bye_weeks()` during `sync_all()` if no bye week data exists for the current season. Wrap in try/except — don't let ESPN failures block the main sync.

---

## Phase 6: API Changes
**Owner: backend-data**

> **Blocked by:** backend-sync completing phases 3 and 4

### Task 6.1: Update `RosterEntryRead` schema

File: `backend/app/schemas/league.py`

Add:
```python
status: str | None = None      # Player injury status
bye_week: int | None = None    # Player's team bye week for this season
```

### Task 6.2: Update `LeagueDetailRead` schema

Add:
```python
current_week: int | None = None
```

### Task 6.3: Update league detail endpoint to populate new fields

File: `backend/app/api/leagues.py` — `get_league_detail()`

- Populate `status` from `r.player.status.value` (already on Player model)
- Query `team_bye_weeks` for this season, build a `team → bye_week` map, populate `bye_week` from player's team
- Populate `current_week` from `league.settings_json.get("leg")`

### Task 6.4: Add `/api/leagues/{league_id}/seasons` endpoint

File: `backend/app/api/leagues.py`

New endpoint that walks the `previous_league_id` chain to find all seasons:
1. Load the given league
2. Walk backward via `previous_league_id` — find leagues in our DB matching `(platform_type, platform_league_id)`
3. Walk forward — find any league whose `previous_league_id == current league's platform_league_id`
4. Return `[{ season, league_id }]` sorted by season descending

### Task 6.5: Update `GET /api/leagues` for dashboard deduplication

Only return leagues with `season == current_year`. This is simpler than chain-walking for deduplication — since we only show active leagues, just filter by season.

If a user has a league that exists in 2024 but not 2025 (they left or it folded), it won't appear on the dashboard. This matches the spec ("only show active leagues").

---

## Phase 7: Frontend — League Detail Restructure
**Owner: frontend**

> **Tasks 7.8 and 7.1-7.5** can start immediately (scaffolding with mock data).
> **Tasks 7.6, 7.7, 7.9** are blocked by phase 6 (need real API responses).

### Task 7.8: Update TypeScript types (START HERE)

File: `frontend/src/api/types.ts`

- Add `status: string | null` and `bye_week: number | null` to `RosterPlayer`
- Add `current_week: number | null` to `LeagueDetail`
- Add new `LeagueSeason` type: `{ season: number; league_id: string }`

File: `frontend/src/api/leagues.ts`

- Add `getLeagueSeasons(leagueId: string): Promise<{ seasons: LeagueSeason[] }>`

### Task 7.1: Add Overview tab as default

File: `frontend/src/pages/LeagueDetailPage.tsx`

- Add "overview" to the `Tab` type and `tabs` array as the first entry
- Set `activeTab` default to `"overview"`
- Create `OverviewTab` component that composes the sub-components below

### Task 7.2: Build Record & Matchup card component

New component within `LeagueDetailPage.tsx` (or extract to `frontend/src/components/`):
- Takes standings + matchups data
- Shows W-L-T, rank, PF, PA
- Shows last completed matchup (W/L indicator, score, opponent)
- Shows next matchup (opponent, week) if current season

### Task 7.3: Build Roster Alerts component

- Takes roster entries (starters only) + current_week
- Filters for alerts: player status != active, or bye_week == current_week
- Sorts by severity (OUT/IR/Suspended → Doubtful → BYE → Questionable)
- Only renders for current season
- Empty state: hidden or "No roster alerts"

### Task 7.4: Build Starting Lineup table

- Takes roster entries where slot is not null and not "TAXI"
- Displays Slot, Player, Pos, Team, ADP columns
- Orders by slot position (maintain original order from API, which mirrors roster_positions)
- ADP clickable (reuses existing PlayerADPModal)

### Task 7.5: Build Recent Activity component

- Takes last 5 transactions
- Shows type badge (color-coded), player name + position, from/to teams
- Relative timestamps (use `Intl.RelativeTimeFormat` or a small helper)

### Task 7.6: Restructure Roster tab into Starters / Bench / Taxi sections

Update `RosterTab`:
- **Starters**: `roster.filter(p => p.slot && p.slot !== "TAXI")` — shows Slot column, ordered by slot position
- **Bench**: `roster.filter(p => !p.slot)` — no Slot column, sorted by position group + ADP
- **Taxi Squad**: unchanged (existing filter)
- Each section gets a header and its own `RosterTable`

### Task 7.7: Add season selector to header

- Dropdown in the header, right-aligned
- Fetch seasons list via `getLeagueSeasons()` when the page loads
- On change, navigate to `/leagues/{selectedLeagueId}`
- Only show dropdown if more than one season exists

### Task 7.9: Past season adaptation

When `current_week == 0` or `league.season < currentYear`:
- Hide Roster Alerts section
- Hide "Next" matchup line in Record card
- Hide Recent Activity (or show with note "Final season activity")

---

## Phase 8: Dashboard Update
**Owner: frontend**

### Task 8.1: Filter dashboard to current season only

Update `DashboardPage.tsx` and/or the `getLeagues()` API call to pass `season=currentYear`. Remove the "Past Seasons" collapsed section.

---

## Phase 9: QA & Documentation
**Owner: qa-docs**

QA runs at five checkpoints between phases. Each checkpoint validates the preceding work, runs tests, and updates documentation.

### Checkpoint QA-0: After Test Scaffolding (phases 0.1, 0.2 complete)

- Run `make test-backend` — all new tests should **fail** (they test unimplemented features)
- Verify no existing tests broke — only the new Phase 0 tests should fail
- Review test names and assertions against the plan spec for completeness
- Confirm test files are organized correctly (new file for bye weeks, extensions to existing files)
- Run `make lint` — tests should be clean even if failing

### Checkpoint QA-1: After Migrations (phases 1.1, 1.2 complete)

- Run `make migrate` — verify both migrations apply cleanly
- Verify models match DATA_MODEL.md:
  - `previous_league_id` on `leagues` table
  - `team_bye_weeks` table exists with correct schema
- Run `make test-backend` — ensure existing tests still pass
- Run `make lint` — catch any formatting issues

### Checkpoint QA-2: After Sync + Bye Weeks (phases 2, 3, 4, 5 complete)

- Run `make test-backend` — all Phase 0.1 tests (adapter, slot inference, historical sync) and Phase 0.2 bye week tests should now **pass**
- **Contract validation** — verify the adapter → sync → DB chain:
  - `PlatformLeague` has `previous_league_id` and `roster_positions`
  - `get_league()` exists on base class and Sleeper implementation
  - `sync_rosters()` produces actual slot labels (QB, RB, FLEX) not "STARTER"
  - `sync_historical_seasons()` handles chain walking and skip-if-exists
  - `settings_json` includes `roster_positions` after sync
- **Bye weeks contract:**
  - `sync_bye_weeks()` fetches from ESPN, normalizes abbreviations to uppercase
  - `team_bye_weeks` table populates correctly
  - ESPN failures don't crash the main sync
- Update PRODUCT.md if any known gaps were resolved (e.g., slot inference)
- Update ROADMAP.md to reflect completed items

### Checkpoint QA-3: After API Changes (phase 6 complete)

- Run `make test-backend` — **all** Phase 0 tests should now pass (0.1 adapter/sync + 0.2 API contracts)
- **API contract validation** — verify response shapes match frontend expectations:
  - `RosterEntryRead` includes `status`, `bye_week`, and slot labels
  - `LeagueDetailRead` includes `current_week`
  - `GET /api/leagues/{id}/seasons` returns correct chain of seasons
  - `GET /api/leagues` filters to current season only
- **Integration test** — manually hit the API (or write a quick test):
  - Sync a league → verify `slot` values are position labels
  - Verify `bye_week` populates on roster entries
  - Verify `/seasons` endpoint walks the chain correctly
- Run `make lint`
- Update DATA_MODEL.md if any schema details changed during implementation

### Checkpoint QA-4: Final Validation (phases 7, 8 complete)

- Run `make test-frontend` — all frontend tests pass
- Run `make typecheck` — no TypeScript errors
- Run `make lint` — backend + frontend clean
- **Frontend contract validation:**
  - TypeScript types match API response shapes exactly
  - No `any` types or missing fields
- **End-to-end smoke test** (manual or Playwright):
  - Login → Dashboard shows one card per league (current season only)
  - Click league card → Overview tab is default
  - Overview shows: Record card, Roster Alerts, Starting Lineup with slot labels, Recent Activity
  - Starting Lineup shows actual slot names (QB, RB, FLEX) not "STARTER"
  - Roster tab shows Starters / Bench / Taxi sections
  - Season selector appears (if historical data exists), switching seasons loads correct data
  - Past season hides Roster Alerts and "Next" matchup
- **Documentation sweep:**
  - DATA_MODEL.md matches actual schema (new table, new columns)
  - PRODUCT.md known gaps updated (remove resolved items)
  - ROADMAP.md reflects completed features
  - UI.md matches implemented behavior (correct any spec-vs-reality drift)
  - ARCHITECTURE.md updated if needed (bye week data source, historical sync pattern)

---

## Execution Order & Dependencies

```
                    ┌────────────────────────────────────────────────────────────┐
                    │                   backend-sync                             │
                    │                                                            │
                    │  [0.1 tests] → [1.1 migration] → [2 adapter] → [3 slots] → [4 history]
                    │                                                            │
                    └───────┬───────────────────────────────────────────┬────────┘
                            │                                           │ done signal
                    ┌───────┼───────────────────────────────────────────▼────────┐
                    │       │          backend-data                              │
                    │       │                                                    │
                    │  [0.2 tests] → [1.2 migration] → [5 bye weeks] → wait → [6 API]
                    │                                                            │
                    └───────┬───────────────────────────────────────────┬────────┘
                            │                                           │ done signal
                    ┌───────┼───────────────────────────────────────────▼────────┐
                    │       │           frontend                                 │
                    │       │                                                    │
                    │  [7.8 types] → [7.1-7.5 scaffold] → [7.6-7.9] → [8]      │
                    │                                                            │
                    └───────┬───────────────────────────────────────────┬────────┘
                            │                                           │
                    ┌───────▼───────────────────────────────────────────▼────────┐
                    │                    qa-docs                                 │
                    │                                                            │
                    │  [QA-0] ── [QA-1] ── [QA-2] ──────────── [QA-3] ── [QA-4] │
                    │  tests    migrations  sync+bye             API     final   │
                    │                                                            │
                    └────────────────────────────────────────────────────────────┘
```

**Summary:**
- Phase 0 runs first — both backend agents write failing tests in parallel, qa-docs validates at QA-0
- backend-sync and backend-data then start migrations simultaneously
- qa-docs runs QA-1 once both migrations land
- backend-data finishes bye weeks early, then waits for backend-sync
- qa-docs runs QA-2 once sync + bye weeks are done — Phase 0 adapter/sync/bye tests should now pass
- frontend starts types + scaffolding immediately, waits for API to wire up
- qa-docs runs QA-3 once API changes land — all Phase 0 tests should pass
- qa-docs runs QA-4 after frontend finishes
- All four agents can be active from the start — just with different levels of blocking
