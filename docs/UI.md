# UI Specifications

Page-by-page layout specs, behavior notes, and wireframes.

---

## Dashboard (`/`)

The main landing page after login. Shows one card per league using the most recent season's data. Clicking a card navigates to the league detail page. Historical seasons are accessed from within the league detail view, not the Dashboard.

### League Identity

A "league" in the Dashboard is a unique combination of `(platform_type, platform_league_id)`. If the same league has data for 2023, 2024, and 2025, it appears as **one card** showing 2025 data. Past seasons are browsable inside the League Detail page via a season selector.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Sidebar │  Header (user name, logout)                       │
│         │───────────────────────────────────────────────────│
│         │                                                   │
│         │  My Leagues                                       │
│         │                                                   │
│         │  ┌─────────────────┐  ┌─────────────────┐        │
│         │  │   League Card   │  │   League Card   │        │
│         │  │   (2025 data)   │  │   (2025 data)   │        │
│         │  └─────────────────┘  └─────────────────┘        │
│         │  ┌─────────────────┐                              │
│         │  │   League Card   │                              │
│         │  │   (2025 data)   │                              │
│         │  └─────────────────┘                              │
│         │                                                   │
└─────────────────────────────────────────────────────────────┘
```

- **Grid:** 2 columns on desktop (`lg`), 2 on tablet (`sm`), 1 on mobile
- **Heading:** "My Leagues" (no season qualifier — each card shows its own season)
- **Only active leagues:** Dashboard only shows leagues that have a season matching the current year. Leagues that only exist in past seasons are not shown — access them via the League Detail season selector on a league that shares the same `platform_league_id`, or via a future "All Leagues" page.

### League Card

Each card is a clickable link to `/leagues/:leagueId` (the most recent season's league ID).

```
┌─────────────────────────────────┐
│ Do or Dynasty              [S]  │
│ My Team Name                    │
├─────────────────────────────────┤
│ Record: 7-3-0    Rank: 2nd     │
│ PF: 1,247.5      PA: 1,102.3   │
├─────────────────────────────────┤
│ Last:  W 142.3 vs Team X       │
│ Next:  vs Team Y (Wk 12)       │
└─────────────────────────────────┘
```

**Header section:**
- League name (left-aligned, bold)
- Platform badge (right-aligned) — small pill/icon showing "S" for Sleeper, "M" for MFL, etc.
- Team name on the second line (the user's team name within this league)

**Stats section** (middle):
- Record: W-L-T
- Rank: ordinal position (e.g. "2nd of 10")
- PF: total points for this season (formatted with commas and 1 decimal)
- PA: total points against this season

**Matchup section** (bottom):
- Last: most recent completed matchup — W/L indicator, score, opponent name
- Next: upcoming matchup opponent and week number (if in-season)

**Missing data handling:**
- If no standings data: show "—" for record, rank, PF, PA
- If no matchup data: show "No matchups yet" in the matchup section
- If season is complete: hide "Next" line, only show last matchup

### States

- **Loading:** Centered spinner (existing pattern)
- **Error:** Red error banner (existing pattern)
- **Empty (no leagues):** Empty state component with link to "Link Account" (existing pattern)

### Data Requirements

The league card needs data not currently returned by the `/api/leagues` endpoint:
- `standings` — user's W-L-T, PF, PA, rank in this league
- `recent_matchups` — last completed matchup (score, opponent)
- `next_matchup` — upcoming opponent and week (if in-season)

The `/api/leagues` endpoint needs to **deduplicate leagues across seasons**, returning only the most recent season per `(platform_type, platform_league_id)` group. This could be handled by either enriching the existing endpoint or making a separate summary endpoint.

---

## League Detail (`/leagues/:leagueId`)

The detail view for a single league. Shows the user's team within the league with tabs for different data views. The **Overview** tab is the default landing tab.

### Header

Always visible above the tabs.

```
← Back to Dashboard

Do or Dynasty                          Season: [2025 ▾]
2025 · HALF PPR · Dynasty · 28 roster spots · My Team Name
```

- **Back link:** Returns to the Dashboard
- **League name:** Bold heading (left)
- **Season selector:** Dropdown (right-aligned) listing all seasons this league has data for (e.g. 2025, 2024, 2023). Defaults to the most recent season. Changing the season reloads all tab data for the selected season.
- **Subtitle:** Season year, scoring type (uppercase), league type (capitalized), roster size, user's team name — separated by middots. Updates when season changes.

**Season selector behavior:**
- Seasons are identified by grouping on `(platform_type, platform_league_id)` — same league across years shares these values.
- Selecting a past season loads that season's league record (different `league_id` in the database).
- URL updates to reflect the selected season's league ID: `/leagues/:leagueId`.

### Tabs

```
  Overview    Roster    Standings    Matchups    Transactions
  ────────
```

Five tabs. Overview is the default active tab. Active tab has bottom border accent.

### Current vs. Past Season Behavior

The Overview tab adapts based on whether the selected season is the current year:

| Section | Current Season | Past Season |
|---|---|---|
| Record & Matchup | Full (with "Next" matchup) | Record only, no "Next" matchup |
| Roster Alerts | Active (bye weeks, injuries) | Hidden — not actionable |
| Starting Lineup | Active lineup from last sync | Final roster snapshot |
| Recent Activity | Last 5 transactions | Hidden or shows last 5 transactions of that season |

Other tabs (Roster, Standings, Matchups, Transactions) show the same layout regardless of season — they're historical data either way.

---

### Overview Tab (default)

The "at a glance" summary. Shows the user's record, upcoming matchup, starting lineup, roster alerts, and recent activity.

#### Desktop Layout

Two-column grid at the top (record + alerts side by side), then full-width sections below.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────────────────┐  ┌─────────────────────────────┐  │
│  │ Record & Matchup         │  │ Roster Alerts               │  │
│  │                          │  │                             │  │
│  │ 7-3-0  ·  2nd of 10     │  │ ⚠ D. Henry — BYE (Wk 12)   │  │
│  │ PF: 1,247.5              │  │ ⚠ C. Lamb — Questionable   │  │
│  │ PA: 1,102.3              │  │ ⚠ M. Andrews — OUT         │  │
│  │                          │  │                             │  │
│  │ Last: W 142.3 vs Bears  │  │                             │  │
│  │ Next: vs Packers (Wk 12)│  │                             │  │
│  └──────────────────────────┘  └─────────────────────────────┘  │
│                                                                 │
│  Starting Lineup                                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Slot  │ Player       │ Pos │ Team │ ADP                   │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │ QB    │ J. Hurts     │ QB  │ PHI  │ 8.0                   │  │
│  │ RB    │ S. Barkley   │ RB  │ PHI  │ 5.1                   │  │
│  │ RB    │ D. Henry     │ RB  │ BAL  │ 12.4                  │  │
│  │ WR    │ J. Chase     │ WR  │ CIN  │ 3.2                   │  │
│  │ WR    │ A. Brown     │ WR  │ PHI  │ 6.8                   │  │
│  │ TE    │ T. Kelce     │ TE  │ KC   │ 15.0                  │  │
│  │ FLEX  │ C. Lamb      │ WR  │ DAL  │ 2.1                   │  │
│  │ K     │ J. Tucker    │ K   │ BAL  │ —                     │  │
│  │ DEF   │ Cowboys      │ DEF │ DAL  │ —                     │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  Recent Activity                                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ADD   B. Thomas (WR)           · 2 days ago              │  │
│  │ DROP  R. Stevenson (RB)        · 2 days ago              │  │
│  │ TRADE sent J. Mixon to Team X  · 5 days ago              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Mobile Layout

Stacks vertically in priority order:

1. Record & Matchup card
2. Roster Alerts (if any)
3. Starting Lineup table
4. Recent Activity

#### Record & Matchup Card

A single card showing the user's season summary and most recent/upcoming matchup.

**Content:**
- **Record:** W-L-T formatted (e.g. "7-3-0")
- **Rank:** Ordinal position with league size (e.g. "2nd of 10")
- **PF / PA:** Points for and points against, formatted with commas and 1 decimal
- **Last matchup:** W/L indicator, score, opponent name
- **Next matchup:** Opponent name and week number

**Data source:** Standings table (record, rank, PF, PA) + matchups table (last/next).

**Missing data handling:**
- No standings: show "—" for record, rank, PF, PA
- No matchups: show "No matchups yet"
- Season complete: hide "Next" line

#### Roster Alerts

Flags potential lineup issues for starters only (bench/taxi players are not flagged).

**Alert types:**

| Alert | Condition | Display |
|---|---|---|
| BYE week | Starter's team has a bye this week | `⚠ {Name} — BYE (Wk {N})` |
| OUT | Player status = `out` | `⚠ {Name} — OUT` |
| Injured Reserve | Player status = `injured_reserve` | `⚠ {Name} — IR` |
| Doubtful | Player status = `doubtful` | `⚠ {Name} — Doubtful` |
| Questionable | Player status = `questionable` | `⚠ {Name} — Questionable` |
| Suspended | Player status = `suspended` | `⚠ {Name} — Suspended` |

**Sort order:** Severity (OUT/IR/Suspended first, then Doubtful, then BYE, then Questionable).

**Empty state:** If no alerts, show a subtle "No roster alerts" message or hide the section entirely.

**Data source:** Player `status` field (already synced) + bye week data (new — see Data Requirements).

#### Starting Lineup Table

Shows the user's current starters with inferred slot labels.

**Columns:**

| Column | Description |
|---|---|
| Slot | Inferred position slot (QB, RB, WR, TE, FLEX, SUPERFLEX, K, DEF) |
| Player | Full name |
| Pos | Player's actual position |
| Team | NFL team abbreviation |
| ADP | Current ADP value (clickable — opens ADP modal) |

**Slot inference:** The league's `roster_positions` array (from `settings_json`) defines the ordered starter slots. During sync, the `starters` array from Sleeper is zipped with the non-bench/IR/taxi slots from `roster_positions` to assign each starter their specific slot label (see Data Requirements).

**ADP format:** Defaults based on league type — `dynasty` format for dynasty leagues, league's `scoring_type` for redraft/keeper. No format picker on the Overview tab (that lives on the Roster tab).

**Empty state:** "No roster data available."

#### Recent Activity

Shows the last 5 transactions for the league.

**Each entry shows:**
- Transaction type badge (ADD in green, DROP in red, TRADE in orange, WAIVER in secondary)
- Player name and position
- From/to team names (for trades)
- Relative timestamp ("2 days ago", "1 week ago")

**Empty state:** "No recent activity."

---

### Roster Tab

Full roster view with all players grouped into sections. Designed for deeper analysis — eventually adding stats columns, status badges, and more.

#### Layout

Three sections with headers, each containing a roster table:

```
  ADP: (Dynasty) (PPR) (Half PPR) (Standard) (Superflex) (2QB)

  Starters
  ┌────────────────────────────────────────────────────────┐
  │ Player       │ Pos │ Team │ Slot │ ADP                 │
  ├────────────────────────────────────────────────────────┤
  │ J. Hurts     │ QB  │ PHI  │ QB   │ 8.0                 │
  │ S. Barkley   │ RB  │ PHI  │ RB   │ 5.1                 │
  │ C. Lamb      │ WR  │ DAL  │ FLEX │ 2.1                 │
  │ ...          │     │      │      │                     │
  └────────────────────────────────────────────────────────┘

  Bench
  ┌────────────────────────────────────────────────────────┐
  │ Player       │ Pos │ Team │ ADP                        │
  ├────────────────────────────────────────────────────────┤
  │ B. Thomas    │ WR  │ JAX  │ 42.0                       │
  │ T. Allgeier  │ RB  │ ATL  │ 85.3                       │
  └────────────────────────────────────────────────────────┘

  Taxi Squad                    (only shown for dynasty leagues)
  ┌────────────────────────────────────────────────────────┐
  │ Player       │ Pos │ Team │ ADP                        │
  │ ...          │     │      │                            │
  └────────────────────────────────────────────────────────┘
```

#### Sections

| Section | Filter | Sort | Notes |
|---|---|---|---|
| **Starters** | `slot` is a starter slot (QB, RB, WR, etc. — not null, not TAXI) | By slot order matching `roster_positions` | Shows Slot column |
| **Bench** | `slot` is null | By position group, then ADP within group | No Slot column |
| **Taxi Squad** | `slot === "TAXI"` | By position group, then ADP within group | Only shown if league has taxi players |

#### ADP Format Picker

Pill buttons above the table (existing pattern). Dynasty leagues show "Dynasty" as the first option. Selection applies to all three sections.

#### Clickable ADP

Clicking an ADP value opens the PlayerADPModal showing ADP from all sources (existing behavior).

#### Future Enhancements (not in initial implementation)

- Player status badge (colored dot or icon next to player name)
- Season/weekly fantasy points column
- Bye week indicator column
- Age and experience (dynasty relevance)

---

### Standings Tab

Full league standings table. No changes from current implementation.

#### Layout

```
┌────────────────────────────────────────────────────────────┐
│ Rank │ Team          │  W │  L │  T │     PF │     PA     │
├────────────────────────────────────────────────────────────┤
│  1   │ Team Alpha    │ 8  │ 2  │ 0  │ 1,350.2│ 1,080.5   │
│  2   │ My Team Name  │ 7  │ 3  │ 0  │ 1,247.5│ 1,102.3   │
│  3   │ Team Gamma    │ 6  │ 4  │ 0  │ 1,180.0│ 1,150.2   │
│ ...  │               │    │    │    │        │           │
└────────────────────────────────────────────────────────────┘
```

- Sorted by rank (ascending)
- PF highlighted in accent green
- User's own row could be highlighted (future enhancement)
- **Empty state:** "No standings data available."

---

### Matchups Tab

Weekly matchup results for the league.

#### Layout

Matchup cards grouped by week, most recent first.

```
  Week 11
  ┌─────────────────────────────────────────┐
  │ Team Alpha          vs      My Team     │
  │     142.3                    138.7      │
  └─────────────────────────────────────────┘
  ┌─────────────────────────────────────────┐
  │ Team Beta           vs      Team Gamma  │
  │     125.0                    130.2      │
  └─────────────────────────────────────────┘

  Week 10
  ┌─────────────────────────────────────────┐
  │ ...                                     │
  └─────────────────────────────────────────┘
```

- Shows last 20 matchups (current behavior)
- Home team on left, away team on right
- Scores displayed with accent styling
- **Empty state:** "No matchup data available."

---

### Transactions Tab

Recent league-wide transaction feed.

#### Layout

```
  ┌──────────────────────────────────────────────────────────┐
  │ ADD    B. Thomas (WR)         Team Alpha    · 2 days ago │
  │ DROP   R. Stevenson (RB)      Team Alpha    · 2 days ago │
  │ TRADE  J. Mixon (RB)          Team Beta → Team Gamma     │
  │ WAIVER D. Johnson (RB)        Team Delta    · 1 week ago │
  └──────────────────────────────────────────────────────────┘
```

- Shows last 20 transactions (current behavior)
- Type badge color-coded: ADD (green), DROP (red), TRADE (orange), WAIVER (secondary)
- Player name and position
- From/to team names
- **Empty state:** "No transaction data available."

---

### Data Requirements

#### Slot Inference (sync-time change)

The `roster.slot` field must store the actual lineup slot label instead of a generic `"STARTER"` string.

**How it works:**

1. The league's `settings_json` contains `roster_positions` — an ordered array like:
   ```json
   ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF", "BN", "BN", "BN", "BN", "BN", "BN", "IR"]
   ```

2. Filter out non-starter slots (`BN`, `IR`) to get the starter slot list:
   ```json
   ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "K", "DEF"]
   ```

3. Sleeper's `starters` array is **ordered** and corresponds 1:1 with these slot positions.

4. During roster sync, zip the `starters` array with the starter slot list to assign each player their actual slot:
   ```
   starters[0] → slot = "QB"
   starters[1] → slot = "RB"
   starters[2] → slot = "RB"
   starters[3] → slot = "WR"
   ...
   ```

5. Players in `taxi` → `slot = "TAXI"` (unchanged)
6. All other players → `slot = NULL` (bench)

**Confirmed via live API testing:** Sleeper's `starters` array contains exactly as many entries as non-BN/IR slots in `roster_positions`. For a league with `roster_positions = ["QB","RB","RB","WR","WR","TE","FLEX","FLEX","DEF","BN","BN"...]`, the `starters` array has 9 entries in the same order.

**Adapter/schema changes needed:**

| File | Change |
|---|---|
| `platforms/base.py` | Add `get_league(league_id: str) -> PlatformLeague` abstract method |
| `platforms/schemas.py` | Add `previous_league_id: str \| None` and `roster_positions: list[str] \| None` to `PlatformLeague` |
| `platforms/sleeper.py` | Implement `get_league()`, extract `previous_league_id` and `roster_positions` in both `get_league()` and `get_leagues()` |
| `sync/engine.py` | Read `roster_positions` from league's `settings_json` during roster sync, zip with starters |

#### Bye Week Data (new)

NFL bye weeks are static per season (32 teams, each gets one bye). Fetched once per season from the ESPN API.

**Source:** ESPN Fantasy API (free, no auth):
```
GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{YEAR}?view=proTeamSchedules_wl
```

**Confirmed response structure** (tested with 2025 season):
```json
{
  "settings": {
    "proTeams": [
      { "abbrev": "Ind", "byeWeek": 11, "id": 11, "location": "Indianapolis", "name": "Colts" },
      { "abbrev": "KC",  "byeWeek": 10, "id": 12, "location": "Kansas City",  "name": "Chiefs" }
    ]
  }
}
```

Returns 33 entries (32 teams + "FA" with `byeWeek: 0`). Filter out the FA entry.

**Team abbreviation mapping:** ESPN uses mixed-case abbreviations (`"Atl"`, `"Phi"`, `"KC"`). Sleeper uses uppercase (`"ATL"`, `"PHI"`, `"KC"`). Normalize by calling `.upper()` on ESPN's `abbrev` field.

**Storage:** New `team_bye_weeks` table:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `season` | INTEGER | e.g. 2025 |
| `team` | VARCHAR(10) | NFL team abbreviation, uppercase (e.g. "KC", "PHI") |
| `bye_week` | INTEGER | Week number |

**Unique constraint:** `(season, team)`

**Sync cadence:** Once per season, triggered manually or via a scheduled job. Could also be fetched on-demand when the Overview tab loads and no bye data exists for the current season.

**Error handling:** If ESPN API is down or returns unexpected data, skip bye week alerts gracefully. The Overview tab still renders — just the BYE alert type is missing.

**Usage:** When rendering roster alerts, join the starter's team against this table to check if `bye_week == current_week`.

#### Current NFL Week

Available from two sources:
- `settings_json.leg` on the league model — the last scored week for that league
- Sleeper NFL state endpoint: `GET /v1/state/nfl` — returns `{ "week": N, "season": "2025", "season_type": "regular" }`

Use `settings_json.leg` as the primary source (already synced). Fall back to the Sleeper NFL state endpoint if needed. During offseason, `season_type` will be `"off"` and `week` will be `0` — in this case, skip roster alerts entirely.

#### Historical Season Sync

When a league is first synced, the engine walks Sleeper's `previous_league_id` chain to discover and sync all past seasons of the same league.

**How Sleeper models league history:**

Sleeper assigns a **different `league_id` per season**. Seasons are linked via a `previous_league_id` field on each league object:

```
2025: league_id = "abc123", previous_league_id = "xyz789"
2024: league_id = "xyz789", previous_league_id = "def456"
2023: league_id = "def456", previous_league_id = null
```

**Sync flow:**

1. User triggers sync for current season (2025)
2. Engine calls `GET /user/{id}/leagues/nfl/2025` → gets league `abc123`
3. Syncs 2025 data (rosters, matchups, standings, transactions) as normal
4. Reads `previous_league_id` from the league response → `"xyz789"`
5. Calls `GET /league/xyz789` to get the 2024 league object
6. Syncs 2024 data (full: all 18 weeks of matchups + transactions, rosters, standings)
7. Reads `previous_league_id` → `"def456"`
8. Repeats until `previous_league_id` is null (end of chain)
9. **Skip already-synced seasons:** If a `previous_league_id` already exists in our `leagues` table (matching `platform_type` + `platform_league_id`), skip re-syncing it. This makes subsequent syncs fast.

**Depth limit:** None — sync all available history. Dynasty leagues may have 5-10+ seasons. This is a one-time cost per league.

**Sleeper API endpoints needed:**
- `GET /league/{league_id}` — fetch a single league by its platform league ID (new adapter method needed, confirmed working via live API testing)
- Existing: `GET /league/{league_id}/rosters`, `/matchups/{week}`, `/transactions/{week}`

**Weeks per past season:** Use `settings.leg` from the league object (the last scored week). For completed seasons this gives the exact week count without hardcoding. Same logic already used for current season sync.

**User league mapping for past seasons:** Sleeper `owner_id` (the user's platform user ID) persists across seasons. The existing sync logic that matches `owner_id` to `platform_user_id` works unchanged for historical seasons.

**Rate limiting:** Sleeper doesn't document rate limits but is generally permissive. A 5-season history walk ≈ 190 API calls (~5 league fetches + 5 roster calls + ~90 matchup calls + ~90 transaction calls). At ~100ms each, this is ~20 seconds. Acceptable for a one-time first sync. Add a small courtesy delay (50-100ms) between calls.

**Data model change — `previous_league_id` on League:**

Add a `previous_league_id` column to the `leagues` table:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `previous_league_id` | VARCHAR(100) | YES | Platform's league ID for the prior season |

This is the **platform's** league ID (e.g., Sleeper's `"xyz789"`), not our internal UUID. Used to walk the chain during sync and to find related seasons for the season selector.

#### Season Selector (new endpoint)

The season selector in the League Detail header needs to know which seasons exist for a given league.

**New endpoint:** `GET /api/leagues/{league_id}/seasons`

Walks the `previous_league_id` chain (both forward and backward) from the given league to find all seasons of the same logical league.

**Algorithm:**
1. Start from the given `league_id`
2. Walk backward via `previous_league_id` to find older seasons
3. Walk forward by finding any league whose `previous_league_id` points to the current league's `platform_league_id` (for finding newer seasons when entering from an old season)
4. Return all found seasons sorted by year descending

```json
{
  "seasons": [
    { "season": 2025, "league_id": "uuid-2025" },
    { "season": 2024, "league_id": "uuid-2024" },
    { "season": 2023, "league_id": "uuid-2023" }
  ]
}
```

When the user selects a different season, the frontend navigates to `/leagues/{league_id}` using the corresponding `league_id` for that season. All existing endpoints (`GET /api/leagues/{league_id}`) continue to work unchanged — they just receive a different league ID.

#### Dashboard Deduplication

The `GET /api/leagues` endpoint needs to return only the most recent season per logical league. Since Sleeper uses different `platform_league_id` values per season, deduplication requires walking the `previous_league_id` chain:

1. Query all leagues for the current user
2. Group leagues that are connected via `previous_league_id` chains
3. For each group, return only the league with the highest `season` value
4. Only include groups that have a league matching the current year (active leagues only)

#### API Changes

The existing `GET /api/leagues/{league_id}` endpoint already returns all needed data (roster with slots, standings, matchups, transactions). The main changes are:

1. **Slot values change** from `"STARTER"` to actual slot names (QB, RB, FLEX, etc.) — this is a sync-time change, not an API change
2. **Bye week data** needs a new endpoint or can be included in the league detail response:
   - Option A: Add `bye_week` field to each `RosterEntryRead` (derived from player's team + season)
   - Option B: Return `current_week` and `team_bye_weeks` map in the league detail response
   - Option A is simpler for the frontend

3. **Player status** is already on the Player model but not returned in `RosterEntryRead`. Add `status` field to the schema.

4. **Current week** — add `current_week` field to `LeagueDetailRead` response (from `settings_json.leg` or Sleeper NFL state). Needed by the frontend to determine whether to show roster alerts and which bye week to flag.

Updated `RosterEntryRead`:
```python
class RosterEntryRead(BaseModel):
    id: UUID
    player_id: UUID
    player_name: str
    position: str | None
    team: str | None
    slot: str | None        # Now: "QB", "RB", "FLEX", "TAXI", or null (bench)
    status: str | None      # NEW: "active", "questionable", "out", etc.
    bye_week: int | None    # NEW: player's team bye week for this season
```

Updated `LeagueDetailRead`:
```python
class LeagueDetailRead(BaseModel):
    # ... existing fields ...
    current_week: int | None = None  # NEW: current NFL week for this season
```

---

## Players (`/players`)

A searchable, sortable player database for researching stats, evaluating trade targets, and checking weekly performance. Accessible from the sidebar. Shows all players in the database across all synced leagues and seasons.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ Sidebar │  Header                                                    │
│         │────────────────────────────────────────────────────────────│
│         │                                                            │
│         │  Players                                                   │
│         │                                                            │
│         │  ┌──────────────┐  ┌────┐ ┌────┐ ┌────┐ ┌────┐           │
│         │  │ 🔍 Search... │  │ QB │ │ RB │ │ WR │ │ TE │ ... │All│ │
│         │  └──────────────┘  └────┘ └────┘ └────┘ └────┘           │
│         │                                                            │
│         │  Season:[2025▾] View:[Season▾] ADP:[FFC▾] Scoring:[½PPR▾] │
│         │                                                            │
│         │  ┌────────────────────────────────────────────────────┐    │
│         │  │ Name       │Pos│Team│ ADP │ Pts │ Yds  │ TD │ Rec │    │
│         │  ├────────────────────────────────────────────────────┤    │
│         │  │ J. Chase   │WR │CIN │ 3.2│285.3│1,456 │ 12 │  98 │    │
│         │  │ S. Barkley │RB │PHI │ 5.1│262.1│1,312 │ 10 │  45 │    │
│         │  │ J. Hurts   │QB │PHI │ 8.0│312.7│  ... │ .. │  .. │    │
│         │  │ ...        │   │    │     │      │    │     │    │    │
│         │  └────────────────────────────────────────────────────┘    │
│         │                                                            │
│         │  ◀ 1  2  3 ... 42 ▶        Showing 1-50 of 2,087          │
│         │                                                            │
└──────────────────────────────────────────────────────────────────────┘
```

### Filter Bar

Top section above the table with controls arranged in two rows:

**Row 1 — Search and position:**
- **Search box** — free-text search by player name. Debounced (300ms), triggers server-side filter.
- **Position filter** — toggle buttons for `QB`, `RB`, `WR`, `TE`, `K`, `DEF`, and `All`. Only one active at a time. Defaults to `All`.

**Row 2 — Dropdowns:**
- **Season selector** — dropdown of available seasons from the database (e.g. 2025, 2024). Defaults to the most recent season.
- **View toggle** — switches between "Season" (aggregated full-season stats) and "Weekly" (per-week breakdown). Defaults to "Season".
- **ADP Source** — dropdown to choose which ADP provider's data to display. Options: `FFC`, `Sleeper`, `DynastyProcess`, or whichever sources have data for the selected season. Defaults to `FFC` (most format-specific data).
- **Scoring Format** — dropdown to select the scoring format for both fantasy points and ADP. Options: `Standard`, `Half PPR`, `PPR`, `Superflex`, `Dynasty`, `2QB`. Defaults to `Half PPR`. This controls which ADP values are shown and which `pts_*` stat is used for the fantasy points column.

When "Weekly" is selected, an additional **Week selector** appears in row 2:

```
  Row 1:  [🔍 Search...          ]  │QB│RB│WR│TE│K│DEF│All│
  Row 2:  Season: [2025 ▾]  View: [Season ▾]  ADP: [FFC ▾]  Scoring: [Half PPR ▾]
```

The ADP and Scoring Format selections should persist across page navigation (stored in URL query params or local state) so the user doesn't have to re-select each time they return to the page.

### Player Table — Season View

Default view. Shows aggregated stats for the selected season. All columns sortable.

| Column | Description | Default Sort |
|---|---|---|
| Name | Player full name (clickable — future: opens player detail) | — |
| Pos | Position (QB, RB, WR, TE, K, DEF) | — |
| Team | NFL team abbreviation | — |
| ADP | Average draft position (from best available source for the format) | — |
| GP | Games played | — |
| Pts | Fantasy points for the season (uses league's scoring format or defaults to half PPR) | DESC (default) |
| Pass Yds | Passing yards (QB-relevant, show "—" for non-passers) | — |
| Rush Yds | Rushing yards | — |
| Rec Yds | Receiving yards | — |
| Rec | Receptions | — |
| TD | Total touchdowns | — |

**Position-adaptive columns:** When a position filter is active, show position-relevant columns:
- **QB selected:** Pass Yds, Pass TD, INT, Rush Yds, Rush TD, Pts
- **RB selected:** Rush Yds, Rush TD, Rec, Rec Yds, Rec TD, Pts
- **WR selected:** Rec, Rec Yds, Rec TD, Targets, Pts
- **TE selected:** Rec, Rec Yds, Rec TD, Targets, Pts
- **K selected:** FGM, FGA, FG%, XPM, Pts
- **DEF selected:** Sacks, INT, FR, TD, Pts Allowed, Pts
- **All:** Mixed columns as shown in the base table above

### Player Table — Weekly View

Shows individual game stats for the selected season + week combination.

Same columns as Season View but values are for a single week. The table heading or a sub-header should indicate which week is displayed (e.g. "Week 1 · 2025").

### Pagination

Server-side pagination. The API handles filtering, sorting, and paging.

- **Page size:** 50 rows per page
- **Controls:** Previous/Next arrows + page number buttons (show first, last, and 2 pages around current)
- **Info line:** "Showing 1-50 of 2,087" below the table

### States

- **Loading:** Skeleton rows in the table (not a full-page spinner — keeps the filter bar interactive)
- **Error:** Red error banner above the table
- **No results:** "No players found matching your filters" message in the table body
- **No stats for season:** Table shows player metadata (name, pos, team, ADP) with "—" for all stat columns. A banner above the table: "Stats not yet available for {season}. Sync player stats to populate."

### Data Requirements

This page needs a new API endpoint. The current backend has no paginated player list or player stats endpoint.

**New endpoint:** `GET /api/players`

Query parameters:
- `search` — name search (ILIKE)
- `position` — position filter
- `season` — season year
- `week` — week number (omit for season aggregate)
- `sort` — column to sort by (default: `pts`)
- `order` — `asc` or `desc` (default: `desc`)
- `page` — page number (default: 1)
- `per_page` — rows per page (default: 50, max: 100)

Response shape:
```json
{
  "players": [...],
  "total": 2087,
  "page": 1,
  "per_page": 50,
  "total_pages": 42
}
```

**Prerequisite:** Player stats sync from Sleeper (`GET /v1/stats/nfl/regular/{season}/{week}`) must be implemented before stat columns can populate. Until then, the table shows player metadata + ADP with "—" for stats.

### Sidebar Update

Add "Players" to the sidebar navigation between "Dashboard" and "Link Accounts":

```
  Dashboard
  Players       ← new
  Link Accounts
```
