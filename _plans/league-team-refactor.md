# Refactor: Separate LeagueTeam from UserLeague

## Problem

`UserLeague` currently serves two roles:
1. **User membership** — "this user participates in this league"
2. **Team identity** — "a team in this league with a platform_team_id, team_name, roster, standings, matchups"

The unique constraint `(user_id, league_id)` means only one record per user per league. The sync engine tries to create stub `UserLeague` rows for every other team in the league (to store their rosters, matchups, standings), but the `on_conflict_do_update` just overwrites `platform_team_id` on the single existing row. Result: only the last-processed team has a valid mapping; all other teams' rosters/matchups/standings are orphaned or missing.

## Proposed Solution

Introduce a `LeagueTeam` model representing "a team in a league" (one per roster slot), independent of app users. `UserLeague` becomes purely "this user watches/participates in this league" with a FK to their specific `LeagueTeam`.

### New model: `league_teams`

```
league_teams
  id                UUID PK
  league_id         UUID FK -> leagues (NOT NULL)
  platform_team_id  VARCHAR(100)         -- e.g. Sleeper owner_id
  team_name         VARCHAR(200)         -- display name (nullable, populated from platform)
  created_at        TIMESTAMP
  updated_at        TIMESTAMP
  UNIQUE(league_id, platform_team_id)
```

### Modified model: `user_leagues`

```
user_leagues
  id                UUID PK
  user_id           UUID FK -> users (NOT NULL)
  league_id         UUID FK -> leagues (NOT NULL)
  league_team_id    UUID FK -> league_teams (nullable) -- which team is "mine"
  created_at        TIMESTAMP
  updated_at        TIMESTAMP
  UNIQUE(user_id, league_id)
```

Drop `team_name` and `platform_team_id` from `user_leagues` (moved to `league_teams`).

### FK migrations on dependent tables

All existing `user_league_id` FKs should point to `league_teams` instead:

| Table | Column | Currently | New |
|-------|--------|-----------|-----|
| `rosters` | `user_league_id` | FK -> user_leagues | **`league_team_id`** FK -> league_teams |
| `standings` | `user_league_id` | FK -> user_leagues | **`league_team_id`** FK -> league_teams |
| `matchups` | `home_user_league_id` | FK -> user_leagues | **`home_league_team_id`** FK -> league_teams |
| `matchups` | `away_user_league_id` | FK -> user_leagues | **`away_league_team_id`** FK -> league_teams |
| `transactions` | `from_user_league_id` | FK -> user_leagues | **`from_league_team_id`** FK -> league_teams |
| `transactions` | `to_user_league_id` | FK -> user_leagues | **`to_league_team_id`** FK -> league_teams |

## Files to modify

### Backend models
- `backend/app/models/league_team.py` — **New file**: LeagueTeam model
- `backend/app/models/user_league.py` — Remove `team_name`, `platform_team_id`; add `league_team_id` FK
- `backend/app/models/roster.py` — Rename `user_league_id` -> `league_team_id`
- `backend/app/models/standing.py` — Rename `user_league_id` -> `league_team_id`
- `backend/app/models/matchup.py` — Rename `home_user_league_id`/`away_user_league_id` -> `home_league_team_id`/`away_league_team_id`
- `backend/app/models/transaction.py` — Rename `from_user_league_id`/`to_user_league_id` -> `from_league_team_id`/`to_league_team_id`
- `backend/app/models/__init__.py` — Export `LeagueTeam`

### Sync engine
- `backend/app/sync/engine.py` — Major rewrite:
  - `sync_leagues`: Upsert `LeagueTeam` rows (one per platform roster) instead of UserLeague stubs
  - `sync_rosters`: Look up `LeagueTeam` by `platform_team_id` instead of `UserLeague`
  - `sync_matchups`: Same — map via `LeagueTeam`
  - `sync_standings`: Same
  - `sync_transactions`: Same
  - `sync_all`: Remove the broken "create user_league stubs" block; replace with `LeagueTeam` upsert logic

### API layer
- `backend/app/api/leagues.py` — Update queries:
  - `list_leagues`: Join through `UserLeague` -> `LeagueTeam` for `team_name`
  - `get_league_detail`: Build team name map from `LeagueTeam` instead of `UserLeague`; get user's roster via `UserLeague.league_team_id`

### Schemas
- `backend/app/schemas/league.py` — No structural changes needed (response shapes stay the same; `team_name` still comes through, just from a different join)

### Migration
- `backend/alembic/versions/xxx_add_league_teams.py` — Alembic migration:
  1. Create `league_teams` table
  2. Migrate existing data: insert into `league_teams` from distinct `(league_id, platform_team_id, team_name)` in `user_leagues`
  3. Add `league_team_id` FK to `user_leagues`, backfill from migrated data
  4. Add `league_team_id` columns to `rosters`, `standings`, `matchups`, `transactions`
  5. Backfill new FKs by joining through old `user_league_id` -> `user_leagues.platform_team_id` -> `league_teams`
  6. Drop old FK columns and constraints
  7. Drop `team_name` and `platform_team_id` from `user_leagues`

## Benefits

- Each team in a league has exactly one `LeagueTeam` row — no duplication, no overwriting
- `UserLeague` is cleanly scoped to "user membership" — enables multi-user support (two app users in the same league each link to their own `LeagueTeam`)
- All team-level data (rosters, standings, matchups, transactions) correctly references the team, not the user
- Platform sync creates/updates `LeagueTeam` rows freely without unique constraint conflicts

## Risks / Notes

- This is a breaking migration — existing data must be carefully migrated
- If the DB has already accumulated corrupt data from the current bug (multiple syncs overwriting `platform_team_id`), the migration needs to handle that gracefully
- Frontend types and components don't need changes (API response shapes are unchanged)
- Tests that reference `user_league_id` will need updating
