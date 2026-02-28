# ADP (Average Draft Position) Integration Plan

## Context

The app currently shows rosters with player name, position, team, and slot — but no sense of player value. Adding ADP data alongside roster entries lets users quickly gauge whether their players are high-value picks or deep sleepers. The user wants both redraft and dynasty ADP from multiple sources.

## Data Sources (3 providers)

1. **Sleeper** — Free, no auth. The `/players/nfl` endpoint returns ADP fields (`search_rank` and similar). Redraft only. Already used by the app for player data.
2. **Fantasy Football Calculator (FFC)** — Free REST API (`/api/v1/adp/{format}?teams=12&year={season}`). Covers redraft + dynasty + dynasty rookie. Requests attribution link. Historical data back to 2007.
3. **DynastyProcess** — Free CSV on GitHub. Dynasty-focused. Already used for player ID mapping.

## Implementation Steps

### Step 1: Data model + migration

**New enum** in `backend/app/models/enums.py`:
- `ADPFormat`: `redraft`, `dynasty`, `dynasty_rookie`
- `LeagueType`: `redraft`, `keeper`, `dynasty`
- Add `adp` to existing `DataType` enum

**New model** `backend/app/models/player_adp.py` — `PlayerADP` table:
- `id` (UUID PK), `player_id` (FK → players), `source` (str, e.g. "sleeper"/"ffc"/"dynastyprocess"), `format` (ADPFormat enum), `season` (int), `adp` (Numeric 8,2), `position_rank` (int, nullable), `updated_at`
- Unique constraint on `(player_id, source, format, season)` for upsert support

**Modify** `backend/app/models/player.py` — add `adp_entries` relationship back to `PlayerADP`

**Modify** `backend/app/models/league.py` — add `league_type` column (LeagueType, nullable)

**Register** in `backend/app/models/__init__.py`

**Generate Alembic migration** — purely additive, no existing tables modified

### Step 2: ADP provider abstraction

**New directory** `backend/app/adp/` with:

| File | Purpose |
|------|---------|
| `base.py` | `ADPProvider` ABC + `ADPRecord` dataclass |
| `sleeper.py` | Fetches from Sleeper `/players/nfl`, extracts ADP fields, returns `ADPRecord` list with `sleeper_id` for matching |
| `ffc.py` | Fetches from FFC REST API, returns records (matched by name+position). Supports historical data (2007+). |
| `dynastyprocess.py` | Fetches CSV from GitHub, returns dynasty ADP records (matched by sleeper_id) |
| `registry.py` | `get_adp_providers()` returns all providers |

`ADPProvider` interface:
- `async fetch_adp(season, format) → list[ADPRecord]`
- `supported_formats() → list[ADPFormat]`

`ADPRecord` fields: `player_name`, `position`, `team`, `adp`, `position_rank`, `sleeper_id` (optional), `source`, `format`

### Step 3: ADP sync service

**New file** `backend/app/adp/sync.py` — `ADPSyncService`:
- `sync_adp(season, sources=None)` — iterates providers, fetches ADP, upserts to `player_adp` table
- Player matching priority: (1) `sleeper_id` exact match, (2) `full_name` + `position` exact match, (3) skip with warning log
- Uses `pg_insert(...).on_conflict_do_update()` — same pattern as the existing sync engine

This is intentionally separate from `SyncEngine` because ADP is global/league-independent, not per-user.

**Scheduled sync:** Add an ADP sync job to the existing APScheduler in `backend/app/sync/scheduler.py`:
- New config: `ADP_SYNC_INTERVAL_HOURS: int = 24` in `backend/app/core/config.py`
- New config: `ADP_SYNC_ENABLED: bool = True` in `backend/app/core/config.py`
- Register a separate scheduled job `sync_adp_task` that calls `ADPSyncService.sync_adp()` for the current season
- Runs alongside the existing `sync_all_users` job on its own interval (default: daily)
- User can also manually trigger via `POST /api/adp/sync`

### Step 4: API endpoints

**New file** `backend/app/api/adp.py`:
- `POST /api/adp/sync` — triggers ADP sync. Requires auth. Params:
  - `season` (int, required) — any year from 2007+ supported via FFC; Sleeper limited to recent years
  - `sources` (list[str], optional) — filter to specific sources
- `GET /api/adp/players/{player_id}/history` — returns all ADP entries for a player across seasons
  - Params: `format` (optional, filter by redraft/dynasty)
  - Returns: list of `{ season, source, format, adp, position_rank }` sorted by season
- Register router in `backend/app/main.py`

**New file** `backend/app/schemas/adp.py`:
- `PlayerADPRead` response schema
- `ADPSyncResponse` with counts of synced/skipped/errored records
- `ADPSourceRead`: `source: str`, `adp: Decimal`

Historical ADP is supported out of the box — the `season` column in `PlayerADP` combined with the FFC API's `year` parameter (2007–present) enables pulling any past season's ADP data.

### Step 5: League type detection + ADP format selection

**Add `league_type` column** to `backend/app/models/league.py` — `LeagueType`, nullable, populated from platform data:
- Sleeper leagues return a top-level `type` field: `0` = redraft, `1` = keeper, `2` = dynasty
- Extract this in `SleeperAdapter.get_leagues()` and store in `PlatformLeague`
- Add `league_type: str | None` to `PlatformLeague` schema
- Sync engine maps it to `LeagueType` enum when upserting leagues

**ADP format auto-detection logic** in league detail endpoint:
- `dynasty` league → default to dynasty ADP
- `redraft` or `keeper` league → default to redraft ADP
- `null` league type → default to redraft ADP

### Step 6: Surface ADP in roster view

**Modify** `backend/app/schemas/league.py`:
- Add to `RosterEntryRead`: `adp: Decimal | None = None`, `adp_sources: list[ADPSourceRead] | None = None`
- Add to `LeagueDetailRead`: `league_type: str | None = None`, `adp_format: str` (the auto-detected default)

**Modify** `backend/app/api/leagues.py` — in `get_league_detail()` (lines 182-199):
- After fetching roster entries, batch-query `PlayerADP` for all player IDs on the roster
- Use the auto-detected ADP format based on `league.league_type`
- Accept optional `?adp_format=dynasty` query param to override the default
- For each player: compute average ADP across sources + include per-source breakdown
- Attach `adp` (aggregate) and `adp_sources` (per-source list) to each `RosterEntryRead`

**Modify** `frontend/src/api/types.ts`:
- Add `adp: string | null` and `adp_sources: { source: string; adp: string }[] | null` to `RosterPlayer`
- Add `league_type: string | null` and `adp_format: string` to `LeagueDetail`

**Modify** `frontend/src/pages/LeagueDetailPage.tsx` — `RosterTab`:
- Add "ADP" column to the roster table showing the aggregate ADP
- Display value formatted to 1 decimal, or "—" if null
- On hover, show a tooltip with per-source breakdown (e.g., "Sleeper: 12.5 | FFC: 14.2")
- Add a small toggle button above the table: "Redraft | Dynasty" that re-fetches league detail with `?adp_format=` override
- Highlight the currently active format

### Step 7: Player ADP history modal

**New frontend dependency**: `recharts` (install via `npm install recharts`)

**New component** `frontend/src/components/PlayerADPModal.tsx`:
- Modal overlay triggered by clicking a player name in the roster table
- Fetches ADP history from `/api/adp/players/{id}/history`
- Line chart (Recharts `LineChart`):
  - X-axis: seasons (e.g., 2020–2025)
  - Y-axis: ADP value (inverted — lower ADP = higher on chart = better)
  - One line per source (Sleeper, FFC, DynastyProcess) with distinct colors
  - Legend showing source names
- Player name + position + team in the modal header
- Close via X button or clicking outside

**Modify** `frontend/src/pages/LeagueDetailPage.tsx`:
- Make player names clickable in the roster table
- On click, open `PlayerADPModal` with the player's ID, name, position, team
- Track selected player in component state

### Step 8: Additional providers (FFC + DynastyProcess)

After Sleeper provider is working end-to-end, implement the FFC and DynastyProcess providers following the same pattern.

## New Dependencies
- `recharts` (npm) — React charting library for player ADP history line chart

## Files to Create
- `backend/app/models/player_adp.py`
- `backend/app/adp/__init__.py`
- `backend/app/adp/base.py`
- `backend/app/adp/sleeper.py`
- `backend/app/adp/ffc.py`
- `backend/app/adp/dynastyprocess.py`
- `backend/app/adp/registry.py`
- `backend/app/adp/sync.py`
- `backend/app/api/adp.py`
- `backend/app/schemas/adp.py`
- `backend/alembic/versions/xxx_add_player_adp_table.py` (auto-generated)
- `frontend/src/components/PlayerADPModal.tsx`

## Files to Modify
- `backend/app/models/enums.py` — add `ADPFormat`, `LeagueType` enums, add `adp` to `DataType`
- `backend/app/models/player.py` — add `adp_entries` relationship
- `backend/app/models/league.py` — add `league_type` column
- `backend/app/models/__init__.py` — register `PlayerADP`, `ADPFormat`, `LeagueType`
- `backend/app/main.py` — register ADP router
- `backend/app/platforms/schemas.py` — add `league_type` to `PlatformLeague`
- `backend/app/platforms/sleeper.py` — extract league `type` field into `PlatformLeague.league_type`
- `backend/app/sync/engine.py` — map `league_type` when upserting leagues
- `backend/app/sync/scheduler.py` — add scheduled ADP sync job
- `backend/app/core/config.py` — add `ADP_SYNC_INTERVAL_HOURS` and `ADP_SYNC_ENABLED` settings
- `backend/app/schemas/league.py` — add `adp` to `RosterEntryRead`, `league_type`/`adp_format` to `LeagueDetailRead`
- `backend/app/api/leagues.py` — batch-query ADP in `get_league_detail()`, accept `adp_format` query param
- `frontend/src/api/types.ts` — add ADP fields to `RosterPlayer` and `LeagueDetail`
- `frontend/src/api/leagues.ts` — pass `adp_format` query param
- `frontend/src/pages/LeagueDetailPage.tsx` — add ADP column + format toggle + clickable player names

## Team Structure (5 agents)

### Agent Roles

| Agent | Role | Responsibilities |
|-------|------|-----------------|
| **lead** | Coordinator | Creates tasks, assigns work, reviews PRs, resolves blockers, approves changes |
| **api-db** | API & Database | Models, enums, migrations, Pydantic schemas, API endpoints |
| **backend** | Backend Logic | ADP provider abstraction, sync service, player matching, scheduler integration |
| **frontend** | Frontend | TypeScript types, roster table ADP column, tooltip, format toggle, ADP history modal |
| **qa-test** | QA & Testing | Unit tests, integration tests, linting, type checking, E2E verification |

### Task List & Dependencies

```
Task 1: [api-db] Create data model + Alembic migration
  - ADPFormat, LeagueType enums in enums.py
  - PlayerADP model in models/player_adp.py
  - league_type column on League model
  - Player.adp_entries relationship
  - Register in models/__init__.py
  - Generate + review Alembic migration
  Files: enums.py, player_adp.py, player.py, league.py, __init__.py
  Blocked by: nothing

Task 2: [api-db] Create Pydantic schemas
  - PlayerADPRead, ADPSourceRead, ADPSyncResponse in schemas/adp.py
  - Add adp + adp_sources to RosterEntryRead
  - Add league_type + adp_format to LeagueDetailRead
  - Add league_type to PlatformLeague schema
  Files: schemas/adp.py, schemas/league.py, platforms/schemas.py
  Blocked by: Task 1

Task 3: [backend] Implement ADP provider abstraction
  - ADPProvider ABC + ADPRecord dataclass in adp/base.py
  - SleeperADPProvider in adp/sleeper.py
  - FFCADPProvider in adp/ffc.py
  - DynastyProcessADPProvider in adp/dynastyprocess.py
  - Provider registry in adp/registry.py
  Files: adp/__init__.py, adp/base.py, adp/sleeper.py, adp/ffc.py, adp/dynastyprocess.py, adp/registry.py
  Blocked by: Task 1 (needs ADPFormat enum)

Task 4: [backend] Implement ADP sync service
  - ADPSyncService in adp/sync.py
  - Player matching logic (sleeper_id → name+position → skip)
  - Upsert via pg_insert().on_conflict_do_update()
  Files: adp/sync.py
  Blocked by: Task 1, Task 3

Task 5: [api-db] Create ADP sync API endpoint
  - POST /api/adp/sync with season + sources params
  - Register router in main.py
  Files: api/adp.py, main.py
  Blocked by: Task 2, Task 4

Task 6: [backend] Add scheduled ADP sync
  - ADP_SYNC_INTERVAL_HOURS + ADP_SYNC_ENABLED config
  - sync_adp_task job in scheduler.py
  Files: core/config.py, sync/scheduler.py
  Blocked by: Task 4

Task 7: [backend] Extract league type from Sleeper
  - Map Sleeper type field (0/1/2) to LeagueType enum in sleeper.py
  - Store league_type when upserting leagues in engine.py
  Files: platforms/sleeper.py, sync/engine.py
  Blocked by: Task 1, Task 2

Task 8: [api-db] Add ADP to league detail endpoint
  - Batch-query PlayerADP in get_league_detail()
  - Auto-detect ADP format from league_type
  - Accept ?adp_format query param override
  - Compute aggregate + per-source breakdown
  Files: api/leagues.py
  Blocked by: Task 1, Task 2, Task 4

Task 9: [frontend] Add ADP to roster view
  - Update RosterPlayer type with adp + adp_sources
  - Update LeagueDetail type with league_type + adp_format
  - Add adp_format param to getLeagueDetail() API call
  - Add ADP column to RosterTab with hover tooltip
  - Add Redraft/Dynasty format toggle
  Files: api/types.ts, api/leagues.ts, pages/LeagueDetailPage.tsx
  Blocked by: Task 8

Task 10a: [api-db] Add player ADP history endpoint
  - GET /api/adp/players/{player_id}/history
  - Returns all ADP entries across seasons, optionally filtered by format
  Files: api/adp.py, schemas/adp.py
  Blocked by: Task 5

Task 10b: [frontend] Install recharts + build PlayerADPModal
  - npm install recharts
  - PlayerADPModal component with line chart (seasons x ADP, one line per source)
  - Inverted Y-axis (lower ADP = higher on chart)
  - Make player names clickable in RosterTab to open modal
  Files: components/PlayerADPModal.tsx, pages/LeagueDetailPage.tsx, package.json
  Blocked by: Task 9, Task 10a

Task 11: [qa-test] Write tests for ADP providers
  - Mock HTTP responses for Sleeper, FFC, DynastyProcess providers
  - Verify ADPRecord parsing from each source
  - Test supported_formats() returns
  Files: tests/test_adp_providers.py
  Blocked by: Task 3

Task 12: [qa-test] Write tests for ADP sync + API
  - Test ADPSyncService upsert behavior
  - Test player matching (sleeper_id, name+position, skip)
  - Test POST /api/adp/sync endpoint
  - Test ADP data in GET /api/leagues/{id} response
  - Test GET /api/adp/players/{id}/history endpoint
  Files: tests/test_adp_sync.py, tests/test_adp_api.py
  Blocked by: Task 4, Task 5, Task 8, Task 10a

Task 13: [qa-test] Run linting, typecheck, full test suite
  - make lint, make typecheck, make test
  - Fix any issues found
  Blocked by: Tasks 1-12
```

### Execution Timeline

**Phase 1** (parallel): Tasks 1, 3
**Phase 2** (parallel): Tasks 2, 4, 7, 11
**Phase 3** (parallel): Tasks 5, 6, 8, 10a
**Phase 4** (parallel): Tasks 9, 10b, 12
**Phase 5**: Task 13

## Verification

1. Run `make migrate` to apply the new migration
2. Start the app with `make up` or `make dev-backend`
3. `POST /api/adp/sync?season=2025` to pull ADP data from Sleeper
4. `GET /api/leagues/{id}` and confirm roster entries include `adp` values with per-source breakdown
5. Check the LeagueDetailPage in the browser — roster table should show ADP column with hover tooltip
6. Toggle between Redraft/Dynasty and verify the ADP values update
7. Click a player name — modal opens with Recharts line chart showing ADP across seasons
8. `make test-backend && make lint && make typecheck` — all pass
