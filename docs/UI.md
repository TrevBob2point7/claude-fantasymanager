# UI Specifications

Page-by-page layout specs, behavior notes, and wireframes.

---

## Dashboard (`/`)

The main landing page after login. Shows all leagues for the current season with key stats at a glance. Clicking a card navigates to the league detail page.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Sidebar │  Header (user name, logout)                       │
│         │───────────────────────────────────────────────────│
│         │                                                   │
│         │  My Leagues · 2025 Season                         │
│         │                                                   │
│         │  ┌─────────────────┐  ┌─────────────────┐        │
│         │  │   League Card   │  │   League Card   │        │
│         │  │                 │  │                 │        │
│         │  └─────────────────┘  └─────────────────┘        │
│         │  ┌─────────────────┐                              │
│         │  │   League Card   │                              │
│         │  │                 │                              │
│         │  └─────────────────┘                              │
│         │                                                   │
│         │  ▸ Past Seasons (collapsed)                       │
│         │                                                   │
└─────────────────────────────────────────────────────────────┘
```

- **Grid:** 2 columns on desktop (`lg`), 2 on tablet (`sm`), 1 on mobile
- **Season heading:** "My Leagues · {year} Season" shown once above the grid. The year comes from the current season, not repeated per card.
- **Past seasons:** Collapsed section below the current season grid. Expands to show prior season leagues grouped by year. Only shown if the user has leagues from previous seasons.

### League Card

Each card is a clickable link to `/leagues/:leagueId`.

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
- **Empty (no current season):** Show past seasons expanded instead of collapsed

### Data Requirements

The league card needs data not currently returned by the `/api/leagues` endpoint:
- `standings` — user's W-L-T, PF, PA, rank in this league
- `recent_matchups` — last completed matchup (score, opponent)
- `next_matchup` — upcoming opponent and week (if in-season)

This could be handled by either enriching the `/api/leagues` response or making a separate summary endpoint.

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
