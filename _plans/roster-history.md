# Roster History

## Problem

Rosters are stored as a current-state snapshot (delete-and-rebuild on each sync). There's no way to view what your team looked like in a previous week or season.

## Proposed Approach

Add a `roster_snapshot` table to capture weekly roster state:

```
roster_snapshot
  id             UUID PK
  user_league_id UUID FK -> user_leagues
  player_id      UUID FK -> players
  week           INT
  season         INT
  slot           VARCHAR (nullable)
  created_at     TIMESTAMP
  UNIQUE(user_league_id, player_id, week, season)
```

During `sync_rosters()`, in addition to rebuilding the current `roster` table, insert/upsert into `roster_snapshot` for the current week. This preserves a historical record without changing the existing current-roster behavior.

## API Surface

- `GET /api/leagues/{id}/roster?week=5&season=2024` — return snapshot for a specific week
- Default (no params) continues to return the current roster

## UI

- Week selector on the Roster tab to browse historical rosters
- Visual diff showing adds/drops between weeks (stretch goal)

## Notes

- Backfilling historical data depends on platform API availability (Sleeper keeps past seasons accessible)
- Storage scales linearly with roster_size x weeks x seasons — likely fine for fantasy football volumes
- Could batch-insert snapshots during initial full sync of past seasons
