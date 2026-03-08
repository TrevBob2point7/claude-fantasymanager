# MFL Integration Spec

This document covers the MFL (MyFantasyLeague) API, data mapping, auth flow, and implementation considerations for integrating MFL as the second platform adapter after Sleeper.

## 1. MFL API Overview

- **Base URL:** `https://api.myfantasyleague.com/{year}/export?TYPE={type}&JSON=1`
- **Auth:** Cookie-based. Login returns `MFL_USER_ID=cookie_value`, sent as `Cookie` header on subsequent requests.
- **Rate limits:** 1 request/second recommended. Registered clients get ~2.5x higher limits. HTTP 429 on throttle.
- **Player IDs:** 4-5 digit numbers as strings (IDs under 1000 need leading zero, e.g. "0531" for Baltimore DEF).
- **Franchise IDs:** 4-digit zero-padded strings ("0001" through "0014" etc.) — these are team identifiers within a league.
- **Case sensitivity:** Endpoint names and parameter names are case-sensitive.
- **League IDs persist across seasons** (unlike Sleeper). The `history` field in league response lists all years.

## 2. Authentication Flow

**Login endpoint:**
```
POST https://api.myfantasyleague.com/{year}/login
  ?USERNAME={username}&PASSWORD={password}&XML=1
```
- Response contains `<status cookie_name="MFL_USER_ID" cookie_value="..."/>`
- Cookie sent on all subsequent requests: `Cookie: MFL_USER_ID={cookie_value}`
- No logout needed — discard cookie to end session
- Cookie stored in `PlatformAccount.credentials_json` as `{"cookie": "MFL_USER_ID=..."}`
- API key alternative exists (tied to user/franchise/league combo) but cookies are simpler for multi-league access

**Design concern:** Current `get_adapter()` creates adapters with no constructor args. MFL adapter needs credentials. Solution deferred to implementation — document the problem.

## 3. API Endpoints & Response Formats

### 3a. `myleagues` — Discover user's leagues (requires auth)
```
GET /export?TYPE=myleagues&YEAR={year}&FRANCHISE_NAMES=1&JSON=1
```
Response: `{ "leagues": { "league": [...] } }` — list of league objects with IDs and names. Empty `{}` if not authenticated.

**Caveat:** `FRANCHISE_NAMES=1` can timeout for users with many leagues. Fetch without it first, then get franchise names from individual league calls.

### 3b. `league` — League metadata
```
GET /export?TYPE=league&L={league_id}&JSON=1
```
Response (key fields):
```json
{
  "league": {
    "id": "40750",
    "name": "Welcome! Everything is Fine.",
    "rosterSize": "21",
    "taxiSquad": "14",
    "injuredReserve": "50",
    "h2h": "YES",
    "bestLineup": "No",
    "lastRegularSeasonWeek": "14",
    "startWeek": "1",
    "endWeek": "17",
    "draftPlayerPool": "Rookie",
    "starters": {
      "count": "9",
      "position": [
        { "name": "QB", "limit": "1-2" },
        { "name": "RB", "limit": "1-6" },
        { "name": "WR", "limit": "1-6" },
        { "name": "TE", "limit": "1-6" }
      ]
    },
    "franchises": {
      "count": "14",
      "franchise": [
        { "id": "0001", "name": "Team Name", "bbidAvailableBalance": "90.00" }
      ]
    },
    "history": {
      "league": [
        { "year": "2024", "url": "https://www46.myfantasyleague.com/2024/home/40750" },
        { "year": "2023", "url": "..." }
      ]
    }
  }
}
```

**Mapping notes:**
- `rosterSize` -> `PlatformLeague.roster_size`
- `starters.position` -> `PlatformLeague.roster_positions` (expand limits, e.g. "1-2" QB means 1 QB slot + up to 1 flex-eligible)
- `draftPlayerPool` = "Rookie" suggests dynasty; "Both" = redraft/keeper
- `bestLineup` = "Yes" -> best ball modifier
- `h2h` = "YES" -> head-to-head matchups
- Scoring type requires separate `rules` endpoint call
- `franchises.franchise` -> `PlatformLeagueUser` data (id, name)
- `history.league` -> historical seasons (MFL keeps same league_id, so `previous_league_id` maps differently than Sleeper)

### 3c. `rosters` — Team rosters
```
GET /export?TYPE=rosters&L={league_id}&JSON=1
```
Response:
```json
{
  "rosters": {
    "franchise": [
      {
        "id": "0001",
        "week": "22",
        "player": [
          { "id": "0808", "status": "ROSTER", "salary": "", "contractYear": "", "contractInfo": "" },
          { "id": "14777", "status": "TAXI_SQUAD" },
          { "id": "15331", "status": "INJURED_RESERVE" }
        ]
      }
    ]
  }
}
```

**Mapping:**
- `franchise.id` -> `PlatformRosterEntry.roster_id` (and `owner_id` — MFL uses franchise ID for both)
- `player.id` -> player IDs list
- `player.status` = "ROSTER" -> active; "TAXI_SQUAD" -> taxi; "INJURED_RESERVE" -> IR
- **No starters list** — roster endpoint only shows roster status, not starting lineup. Starters come from `weeklyResults`.

### 3d. `weeklyResults` — Matchup scores & starters
```
GET /export?TYPE=weeklyResults&L={league_id}&W={week}&JSON=1
```
Response (per franchise in matchup):
```json
{
  "id": "0009",
  "isHome": "0",
  "score": "88.71",
  "result": "L",
  "opt_pts": "114.075",
  "starters": "10700,16150,13850,15259,...",
  "nonstarters": "15717,11150,...",
  "player": [
    { "id": "10700", "status": "starter", "score": "5.200", "shouldStart": "0" },
    { "id": "16150", "status": "starter", "score": "24.610", "shouldStart": "1" }
  ]
}
```

**Mapping:**
- `starters` (comma-separated) -> `PlatformMatchup.starters`
- `player[].score` where status="starter" -> `PlatformMatchup.starters_points`
- `score` -> `PlatformMatchup.points`

### 3e. `schedule` — Matchup pairings
```
GET /export?TYPE=schedule&L={league_id}&W={week}&JSON=1
```
Response:
```json
{
  "schedule": {
    "weeklySchedule": {
      "week": "1",
      "matchup": [
        {
          "franchise": [
            { "id": "0009", "isHome": "0", "score": "88.71", "result": "L" },
            { "id": "0010", "isHome": "1", "score": "149.12", "result": "W" }
          ]
        }
      ]
    }
  }
}
```

**Mapping:**
- Each `matchup` pairs two franchises. `isHome` = "0" (away) / "1" (home).
- Matchup ID: use array index (MFL doesn't provide explicit matchup IDs like Sleeper).
- Need both `schedule` (for pairings) and `weeklyResults` (for starters/player scores) to build full `PlatformMatchup`.

### 3f. `leagueStandings` — Standings
```
GET /export?TYPE=leagueStandings&L={league_id}&JSON=1
```
Response:
```json
{
  "leagueStandings": {
    "franchise": [
      {
        "id": "0011",
        "fname": "@RotoLibrarian",
        "h2hw": "20",
        "h2hl": "6",
        "h2ht": "0",
        "pf": "2582.815",
        "all_play_pct": ".801",
        "h2hwlt": "20-6-0"
      }
    ]
  }
}
```

**Mapping:**
- `h2hw/h2hl/h2ht` -> wins/losses/ties
- `pf` -> points_for
- No `points_against` field directly available (may need `pa` with `ALL=1` param or compute from matchups)
- Rank: derive from array position (response appears sorted by standings)

### 3g. `transactions` — Trades, waivers, free agents
```
GET /export?TYPE=transactions&L={league_id}&W={week}&JSON=1
```
Transaction types: `WAIVER`, `BBID_WAIVER`, `FREE_AGENT`, `TRADE`, `IR`, `TAXI`, etc.

Response format varies by type:
- **FREE_AGENT:** `{ "franchise": "0003", "transaction": "16641,|15289,", "type": "FREE_AGENT", "timestamp": "..." }` — pipe separates added|dropped, comma-separated player IDs
- **TRADE:** `{ "franchise": "0001", "franchise2": "0003", "franchise1_gave_up": "14777,FP_0001_2025_3", "franchise2_gave_up": "15331,13590", "type": "TRADE", ... }` — includes draft pick IDs
- **BBID_WAIVER:** `{ "franchise": "0005", "transaction": "13940,|0.00|", "type": "BBID_WAIVER", ... }`

**Mapping to `PlatformTransaction`:**
- `FREE_AGENT` / `WAIVER` / `BBID_WAIVER` -> type="waiver" or "add"
- `TRADE` -> type="trade"
- Parse `transaction` field: before pipe = added, after pipe = dropped
- `franchise1_gave_up` / `franchise2_gave_up` for trades
- Filter out non-player IDs (draft picks like `FP_*`)

### 3h. `players` — Player database
```
GET /export?TYPE=players&DETAILS=1&JSON=1
```
- Returns all ~2000+ players with IDs, names, positions, teams
- `DETAILS=1` includes external source IDs (ESPN, Yahoo, etc.)
- Cache locally — changes at most once daily
- Use for building MFL player ID -> Player model mapping

## 4. Key Differences from Sleeper

| Aspect | Sleeper | MFL |
|--------|---------|-----|
| Auth | None (public API) | Cookie-based login required |
| League ID across seasons | Changes per season | Persists (same ID, different year in URL path) |
| Season in URL | Query param | URL path segment (`/{year}/export`) |
| User identification | User ID (numeric string) | Franchise ID per league ("0001") |
| Roster starters | In roster endpoint | Separate `weeklyResults` endpoint |
| Matchup pairing | `matchup_id` field groups pairs | `schedule` endpoint pairs franchises |
| Player IDs | Sleeper-specific numeric strings | MFL-specific 4-5 digit strings |
| Rate limiting | Generous | 1 req/sec, 429 on throttle |
| Scoring type | In league settings | Requires `rules` endpoint |
| Transaction format | Structured JSON | Pipe/comma-delimited strings |

## 5. Cross-Platform League Linking

### The Problem

A league can migrate between platforms. For example, a dynasty league may have run on MFL from 2018-2023 and then moved to Sleeper for 2024+. The current `previous_league_id` chain only works within a single platform — it stores platform-specific league IDs and the chain-walking code filters by `platform_type`. There's no way to bridge MFL seasons to Sleeper seasons for the same logical league.

### Proposed Solution: `league_group_id`

Add a `league_group_id: UUID` column to the `leagues` table. All seasons of the same logical league share the same value, regardless of platform.

```
leagues table (simplified):
┌──────────┬───────────┬────────┬──────────────────┬────────────────────┐
│ platform │ league_id │ season │ prev_league_id   │ league_group_id    │
├──────────┼───────────┼────────┼──────────────────┼────────────────────┤
│ mfl      │ 40750     │ 2021   │ NULL             │ aaa-bbb-ccc        │
│ mfl      │ 40750     │ 2022   │ 40750            │ aaa-bbb-ccc        │
│ mfl      │ 40750     │ 2023   │ 40750            │ aaa-bbb-ccc        │
│ sleeper  │ abc123    │ 2024   │ xyz789 (sleeper) │ aaa-bbb-ccc        │
│ sleeper  │ def456    │ 2025   │ abc123           │ aaa-bbb-ccc        │
└──────────┴───────────┴────────┴──────────────────┴────────────────────┘
```

**How it works:**

- **Within-platform chains** still auto-link via `previous_league_id` during sync (no change).
- **Auto-assign group ID:** When syncing a league chain, assign the same `league_group_id` to all seasons in the chain. If no group exists yet, generate a new UUID and apply it to the whole chain.
- **Cross-platform linking** is a manual user action — the user says "these are the same league" and we merge the two group IDs into one. This only needs to happen once; all seasons in both chains inherit the shared group ID.
- **Frontend becomes platform-agnostic:** The season selector and dashboard dedup query on `league_group_id` instead of walking `previous_league_id` chains. The season selector shows "2025 (Sleeper)", "2024 (Sleeper)", "2023 (MFL)", etc.
- **No schema changes to `previous_league_id`** — it continues to work as-is for within-platform chaining.

**Changes needed:**

| File | Change |
|------|--------|
| `backend/app/models/league.py` | Add `league_group_id: UUID` column (nullable, backfilled) |
| `backend/alembic/` | Migration to add column + backfill existing chains |
| `backend/app/sync/engine.py` | Assign `league_group_id` when syncing league chains |
| `backend/app/api/leagues.py` | Simplify season chain + dashboard dedup to use `league_group_id` |
| `backend/app/api/leagues.py` | New endpoint: `POST /api/leagues/{id}/link` to merge two league groups |
| `frontend/src/pages/LeagueDetailPage.tsx` | Season selector labels include platform name when mixed |
| `frontend/src/pages/LinkAccountsPage.tsx` | (or new page) UI for linking cross-platform leagues |

### User Flow: Linking Leagues

**Entry point:** League Detail page → settings/actions menu → "Link to another league"

**Step 1 — Initiate linking:**
On the League Detail page (viewing any season), the user clicks a "Link to another league" button in the league header or a settings dropdown. This is only shown when the user has leagues on multiple platforms (i.e., has more than one `platform_account`).

**Step 2 — Pick the target league:**
A modal or drawer opens showing the user's other league groups that aren't already linked to this one. Each option shows:
- League name
- Platform icon (Sleeper, MFL)
- Seasons available (e.g., "2018-2023")
- Number of teams

The list is sorted with suggested matches first (same or similar name, same team count, same league type), then everything else. Suggested matches get a subtle "Possible match" label.

```
┌─────────────────────────────────────────────────┐
│  Link to another league                    [X]  │
│                                                 │
│  Select a league to combine history with        │
│  "Do or Dynasty" (Sleeper, 2024-2025)           │
│                                                 │
│  ┌─────────────────────────────────────────┐    │
│  │  ⭐ Possible match                      │    │
│  │  Do or Dynasty          MFL 2018-2023   │    │
│  │  14 teams · Dynasty                     │    │
│  │                            [Link]       │    │
│  ├─────────────────────────────────────────┤    │
│  │  Other League Name      MFL 2020-2023   │    │
│  │  12 teams · Redraft                     │    │
│  │                            [Link]       │    │
│  └─────────────────────────────────────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Step 3 — Confirm:**
After clicking "Link", a confirmation dialog shows what will happen:
> "This will combine the season history of **Do or Dynasty** (MFL, 2018-2023) with **Do or Dynasty** (Sleeper, 2024-2025). You'll see all 8 seasons together in the season selector. This can be undone later."

User confirms → `POST /api/leagues/{id}/link` with the target league ID → backend merges the `league_group_id` values.

**Step 4 — Result:**
The League Detail page refreshes. The season selector now shows all seasons across both platforms:
```
Season: [2025 ▾]
  2025  (Sleeper)
  2024  (Sleeper)
  2023  (MFL)
  2022  (MFL)
  2021  (MFL)
  ...
```

**Unlinking:** The same menu offers "Unlink league history" which splits the group back into separate platform chains. Each chain gets a new `league_group_id`.

### API Endpoints

**Link leagues:**
```
POST /api/leagues/{league_id}/link
Body: { "target_league_id": "uuid" }
```
- Validates both leagues belong to the requesting user
- Merges: sets all leagues with the target's `league_group_id` to the source's `league_group_id`
- Returns the updated season list

**Unlink leagues:**
```
POST /api/leagues/{league_id}/unlink
Body: { "platform_type": "mfl" }
```
- Splits the group by platform: all seasons of the specified platform get a new `league_group_id`
- Returns the updated season list

### Smart Suggestions (Enhancement)

When MFL leagues are first synced, the sync engine can flag likely cross-platform matches by comparing against existing leagues with:
- Similar name (fuzzy match, e.g., Levenshtein distance)
- Same team count
- Same league type (dynasty/keeper/redraft)
- Adjacent seasons (MFL ends where Sleeper begins)

These matches are surfaced as a one-time prompt on the Dashboard: "We found leagues that might be the same — want to link them?" This is a nice-to-have on top of the manual flow.

### Edge Cases
- User links wrong leagues — unlink action splits group IDs back apart
- A league has never been on another platform — `league_group_id` still works, it's just a group of one platform's seasons
- Multiple users in the same league — `league_group_id` is on the league itself, so all users benefit once any user links them
- League name changed between platforms — suggestions use fuzzy matching, but manual linking always works

## 6. Implementation Considerations

### 6a. Adapter needs auth credentials
Current `get_adapter()` returns `adapter_cls()` with no args. MFL needs cookie/credentials. Options:
- Pass credentials to constructor: `MFLAdapter(credentials_json=...)`
- Modify `get_adapter()` to accept optional kwargs
- Adapter reads from a context/config

Decision deferred to implementation phase.

### 6b. Player identity mapping
- `get_or_create_player_by_sleeper_id()` is Sleeper-specific
- Need `get_or_create_player_by_mfl_id()` or a generic version
- MFL `players?DETAILS=1` provides external IDs that could cross-reference Sleeper IDs
- DynastyProcess player ID CSV already maps `sleeper_id` <-> `mfl_id`

### 6c. Season handling (history vs previous_league_id)
- MFL: same league_id across years. `history.league[].year` lists seasons.
- Sleeper: different league_id per season, linked by `previous_league_id`.
- For MFL, `previous_league_id` in our model could store `{league_id}_{prev_year}` or we handle history differently.
- Alternative: query MFL with different year paths using the same league_id.

### 6d. Franchise ID != User ID
- MFL identifies teams by franchise_id within a league (e.g., "0001")
- There's no global MFL user ID exposed in the same way as Sleeper
- `PlatformRosterEntry.owner_id` and `PlatformLeagueUser.user_id` should use franchise_id
- `PlatformAccount.platform_user_id` may store the MFL username or a derived ID from login

### 6e. Roster positions / slot inference
- MFL `starters.position` uses limit ranges ("1-2" for QB means 1 required, up to 2)
- Need to expand these into `roster_positions` list format matching Sleeper's approach
- Example: QB "1-2", RB "1-6", WR "1-6", TE "1-6" with count=9 -> need to infer flex slots

### 6f. Rate limiting
- Must add 1-second delays between MFL API calls
- Consider using `asyncio.sleep(1)` between requests
- Or use an async rate limiter (e.g., `aiolimiter`)

## 7. Endpoints Needed (Priority Order)

| Priority | Endpoint | Maps to | Notes |
|----------|----------|---------|-------|
| P0 | `login` | Auth flow | Get cookie for all subsequent calls |
| P0 | `myleagues` | `get_leagues()` | Discover user's leagues (requires auth) |
| P0 | `league` | `get_league()`, `get_league_users()` | League metadata + franchise list |
| P0 | `rosters` | `get_rosters()` | Team rosters with status |
| P0 | `leagueStandings` | Standings sync | W/L/T, points |
| P1 | `weeklyResults` | `get_matchups()` | Starters and player scores |
| P1 | `schedule` | `get_matchups()` | Matchup pairings (home/away) |
| P1 | `transactions` | `get_transactions()` | Trades, waivers, adds/drops |
| P2 | `players` | Player import | Full player database with external IDs |
| P2 | `rules` | Scoring type detection | Determine PPR/standard/custom |

## 8. Files That Will Need Changes

| File | Change |
|------|--------|
| `backend/app/platforms/mfl.py` | **New** — MFLAdapter class |
| `backend/app/platforms/registry.py` | Add MFLAdapter to registry |
| `backend/app/platforms/base.py` | Possibly add optional `credentials` param |
| `backend/app/sync/player_import.py` | Add `get_or_create_player_by_mfl_id()` |
| `backend/app/sync/engine.py` | Handle MFL player import path |
| `backend/app/api/platforms.py` | MFL account linking with username/password |
| `frontend/src/pages/LinkAccountsPage.tsx` | MFL auth form (username + password) |
| `backend/tests/` | MFL adapter unit tests |
| `docs/PRODUCT.md` | Update MFL status |
| `docs/DATA_MODEL.md` | Document any schema changes |

## 9. Verification

After implementation:
1. Unit tests for MFLAdapter methods with mocked HTTP responses
2. Integration test: link MFL account -> discover leagues -> sync all data types
3. Verify player identity mapping (mfl_id populated on Player records)
4. Verify rate limiting (no 429s during sync)
5. Manual test with a real MFL league (need test account credentials)
