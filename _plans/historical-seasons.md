# Historical Seasons & Season Selector

## Problem

Currently the app only syncs the current season's leagues from Sleeper. Users cannot view past seasons' rosters, matchups, standings, or transactions. ADP data is also only synced for the current year, causing a mismatch with older leagues.

## Goals

- Import league history for multiple past seasons from Sleeper
- Allow users to browse leagues by season in the dashboard
- Add a season selector within the league detail view to switch between years
- Sync ADP data for past seasons where provider data is available

## Backend Changes

### 1. Multi-season league discovery & sync

- **`SleeperAdapter.get_leagues()`** already accepts a `season` param — no adapter changes needed
- **`SyncEngine.sync_all()`** currently takes a single `season` arg. Add a `seasons` list option (e.g., `[2023, 2024, 2025]`) that iterates and syncs each year
- **`POST /api/sync/{account_id}`** — add optional `seasons` query param (defaults to current year only for backward compat)

### 2. Historical sync endpoint

- New endpoint: `POST /api/sync/{account_id}/history` that syncs all available seasons (Sleeper keeps data back to ~2018)
- Should be a heavier operation — consider background task or at least a longer timeout
- Could auto-detect available seasons by trying each year and stopping when Sleeper returns empty

### 3. ADP historical data

- **`POST /api/adp/sync`** already accepts a `season` param
- Add a `POST /api/adp/sync/historical` endpoint or allow a `seasons` list param
- Provider availability varies — DynastyProcess has multi-year data, Sleeper ADP may only have current year
- The season-mismatch fallback (closest available ADP season) already handles gaps

### 4. League detail API season awareness

- The league detail endpoint currently returns data for a single league row (which is already per-season due to the unique constraint on `platform_type + platform_league_id + season`)
- Add `GET /api/leagues/{league_id}/seasons` — returns list of available seasons for leagues sharing the same `platform_league_id` and `platform_type`
- Frontend can use this to populate the season dropdown

## Frontend Changes

### 1. Dashboard season filter

- Add a season dropdown/pill selector to the dashboard (above league cards)
- `GET /api/leagues?season=2024` already works — just needs UI

### 2. League detail season selector

- Add season dropdown in the league detail header
- On season change, look up the league ID for that season (same `platform_league_id`, different `season`) and navigate to it
- Needs the `/api/leagues/{league_id}/seasons` endpoint to know which years are available

### 3. Historical sync trigger

- Add a "Sync History" button on the Link Accounts page (alongside existing "Sync" button)
- Should show progress or at least a message about how many seasons were synced
- Consider a confirmation dialog since it's a heavier operation

## Data Model Considerations

- No schema changes needed — leagues are already keyed by `(platform_type, platform_league_id, season)`
- Multiple season rows for the same Sleeper league will naturally coexist
- Rosters, matchups, standings, and transactions are all tied to a specific league row (and therefore season)

## Migration Path

- Existing users can trigger historical sync at their discretion
- No breaking changes to existing API contracts
- The dashboard defaults to showing the latest season (current behavior)

## Open Questions

- How far back should we auto-sync? All available years, or let the user pick?
- Should historical sync be a background job with status polling?
- Do we want a "compare seasons" view (e.g., roster diff year-over-year)?
