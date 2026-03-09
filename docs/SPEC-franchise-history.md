# Spec: Franchise History & League Summary Page

## Problem

When a user clicks a league card on the dashboard, they land on the current season's detail page. There is no cross-season view — no way to see your franchise's full history, career stats, or accomplishments at a glance.

## Goal

Replace the league landing experience with a **Franchise History** summary page that shows career stats across all synced seasons. The per-season detail (roster, matchups, standings, transactions) remains accessible by drilling into a specific season.

**Depends on:** [Playoff Data & Championship Detection](SPEC-playoff-data.md) for championship wins and playoff record.

---

## Franchise History Stats

### Career Record
- **All-time W/L/T** — sum across all seasons (regular season only, excluding playoffs)
- **All-time win percentage**
- **Total points for / points against** — sum from standings across seasons
- **Number of seasons**

### Championships & Playoffs
- **Championship wins** — list of seasons where the user won the championship (requires playoff data)
- **Championship appearances** — seasons where the user reached the finals
- **Playoff appearances** — seasons where the user made the playoffs
- **Playoff record** — W/L in playoff matchups only (non-consolation)

### Highlight Stats
- **Highest single-week score** — score + season + week + opponent + result (W/L)
- **Lowest single-week score** — same detail
- **Biggest blowout win** — largest margin of victory + details
- **Closest win** — smallest margin of victory + details
- **Longest winning streak** — count + season(s) + week range
- **Longest losing streak** — same detail

### Best Performances by Position
- **Top scorer at each position** — player name + points + season + week
- Positions: QB, RB, WR, TE, K, DEF
- Sourced from `matchup.home_starters_json` / `away_starters_json` player entries

### Season-by-Season Summary
- Table/timeline showing each season with: year, record, rank, PF, PA, playoff result, platform badge
- Clickable rows to drill into season detail

---

## Data Sources

All stats can be computed from existing synced data:

| Stat | Source Table(s) | Notes |
|------|----------------|-------|
| Career W/L/T | `standings` | Sum across all leagues in `league_group_id` |
| Total PF/PA | `standings` | Same |
| Championship wins | `matchups` | Requires `playoff_round` (max round) + win detection |
| Highest/lowest week score | `matchups` | `home_score`/`away_score` for user's matchups |
| Winning/losing streaks | `matchups` | Walk chronologically across seasons |
| Best player by position | `matchups` | Parse `starters_json`, group by position, find max points |
| Season summary | `leagues` + `standings` | Join league metadata with standing record |

### Data Availability Concern

Historical matchup data is **lazy-loaded** — it's only fetched when a user views the matchups tab for a specific season. This means:

- A user who has synced 5 seasons but only viewed matchups for the current season will only have matchup data for 1 season
- The franchise history page would show incomplete stats

**Solutions (pick one):**

1. **Eager sync for historical matchups** — when discovering historical seasons, also sync all matchup weeks (not just metadata + standings). This increases initial sync time but guarantees complete data.

2. **Progressive stats with gaps indicated** — show stats based on available data, with a note like "Stats from 3 of 5 seasons. Sync older seasons for complete history." Include a button to trigger a full historical matchup sync.

3. **On-demand backfill** — when the user opens the franchise history page, check which seasons have matchup data and offer to sync the missing ones (with progress indicator).

**Recommendation:** Option 2 for now (show what we have, indicate gaps), with a "Sync full history" button that triggers option 3. This avoids making the initial sync even longer while giving users a path to complete data.

---

## API Design

### New Endpoint: `GET /api/leagues/{league_id}/franchise-history`

Returns computed franchise history stats for the user across all seasons in the league group.

**Response schema:**

```json
{
  "career": {
    "seasons": 5,
    "wins": 48,
    "losses": 32,
    "ties": 0,
    "win_pct": 0.6,
    "points_for": 8234.5,
    "points_against": 7891.2,
    "championships": [2022, 2024],
    "championship_appearances": [2022, 2023, 2024],
    "playoff_appearances": [2021, 2022, 2023, 2024, 2025],
    "playoff_wins": 7,
    "playoff_losses": 3
  },
  "highlights": {
    "highest_score": {
      "score": 187.5,
      "season": 2023,
      "week": 12,
      "opponent": "Team Thunder",
      "result": "W"
    },
    "lowest_score": {
      "score": 62.3,
      "season": 2021,
      "week": 5,
      "opponent": "Team Lightning",
      "result": "L"
    },
    "biggest_blowout": {
      "margin": 85.2,
      "score": 172.4,
      "opponent_score": 87.2,
      "season": 2023,
      "week": 8,
      "opponent": "Team Breeze"
    },
    "closest_win": {
      "margin": 0.3,
      "score": 112.5,
      "opponent_score": 112.2,
      "season": 2024,
      "week": 3,
      "opponent": "Team Gale"
    },
    "longest_win_streak": {
      "count": 7,
      "start_season": 2023,
      "start_week": 9,
      "end_season": 2023,
      "end_week": 15
    },
    "longest_loss_streak": {
      "count": 4,
      "start_season": 2021,
      "start_week": 1,
      "end_season": 2021,
      "end_week": 4
    }
  },
  "best_performers": [
    {
      "position": "QB",
      "player_name": "Josh Allen",
      "points": 42.5,
      "season": 2024,
      "week": 11
    },
    {
      "position": "RB",
      "player_name": "Saquon Barkley",
      "points": 38.2,
      "season": 2024,
      "week": 14
    }
  ],
  "seasons": [
    {
      "season": 2025,
      "league_id": "uuid-here",
      "platform_type": "sleeper",
      "record": "9-5-0",
      "rank": 2,
      "points_for": 1823.4,
      "points_against": 1654.2,
      "playoff_result": "championship_loss",
      "has_matchup_data": true
    }
  ],
  "data_completeness": {
    "total_seasons": 5,
    "seasons_with_matchups": 3,
    "seasons_missing_matchups": ["2021", "2022"]
  }
}
```

### Computation Notes

**Streaks** — walk matchups sorted by `(league.season ASC, matchup.week ASC)` across all seasons. For each matchup, determine if user won (compare home/away score based on which side they're on). Track current streak length and max streak.

**Best performers** — iterate all matchups, parse `home_starters_json` or `away_starters_json` (whichever is the user's side), group by position, keep the max points entry per position.

**Playoff result per season** — requires playoff data from SPEC-playoff-data.md:
- `champion` — won the final round
- `championship_loss` — lost in the final round
- `eliminated_round_2` — lost in the semis (round 2)
- `eliminated_round_1` — lost in the first round (wildcard)
- `missed_playoffs` — no non-consolation playoff matchups for this team
- `unknown` — no playoff data available (matchups not synced or no bracket data)

Display labels for the Result column in Season History:

| `playoff_result` | Display | Color |
|---|---|---|
| `champion` | Champion | Gold |
| `championship_loss` | Finals | Silver |
| `eliminated_round_2` | Semis | Gray |
| `eliminated_round_1` | Round 1 | Gray |
| `missed_playoffs` | Missed Playoffs | Red/muted |
| `unknown` | — | — |

**Computation:** For each season, find the user's matchups where `playoff_round IS NOT NULL` and `is_consolation = false`. If none exist, result is `missed_playoffs`. Otherwise:
- Find the max `playoff_round` the user participated in
- Check if they won that matchup → `champion` (if max round for the league) or advance indicator
- If they lost → `eliminated_round_N` or `championship_loss` (if it was the final round)

**Championship detection** — find matchups where `playoff_round` equals the max round for that season and `is_consolation = false`. If the user won that matchup, they are the champion.

---

## Frontend Design

### Page Structure

When clicking a league card, land on the **Franchise History** page:

```
League Name
Season selector (dropdown) | Sync button

[Franchise History] [2025] [2024] [2023] ...
                     ↑ season tabs that drill into detail
```

**Franchise History tab (default landing):**

┌─────────────────────────────────┐
│  Career Record                  │
│  48-32-0 (.600) | 5 seasons    │
│  PF: 8,234  PA: 7,891          │
│  Championships: 2022, 2024     │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Highlights                     │
│  Highest Score: 187.5           │
│    2023 Week 12 vs Team Thunder │
│  Longest Win Streak: 7          │
│    2023 Weeks 9-15              │
│  Biggest Blowout: 85.2 pts     │
│    2023 Week 8 vs Team Breeze   │
│  Closest Win: 0.3 pts          │
│    2024 Week 3 vs Team Gale     │
│  ...                            │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Best Single-Game Performances  │
│  QB: Josh Allen — 42.5 pts     │
│      2024 Week 11               │
│  RB: Saquon Barkley — 38.2 pts │
│      2024 Week 14               │
│  WR: ...                        │
│  TE: ...                        │
│  K: ...                         │
│  DEF: ...                       │
└─────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  Season History                                        │
│  Year | Record | Rank | PF    | Playoff Result         │
│  2025 | 9-5-0  | 2    | 1,823 | 🥈 Finals             │
│  2024 | 11-3-0 | 1    | 1,945 | 🏆 Champion            │
│  2023 | 10-4-0 | 3    | 1,876 | Semis                  │
│  2022 | 12-2-0 | 1    | 2,001 | 🏆 Champion            │
│  2021 | 6-8-0  | 7    | 1,589 | Missed Playoffs        │
│  2020 | 8-6-0  | 4    | 1,702 | Round 1                │
└────────────────────────────────────────────────────────┘

**Season tabs** — clicking a season year switches to the existing per-season detail view (Overview, Roster, Standings, Matchups, Transactions tabs).

### Data Completeness Banner

If some seasons are missing matchup data, show a subtle banner:

```
Stats based on 3 of 5 seasons. [Sync full history] for complete stats.
```

The "Sync full history" button triggers a sync of historical matchups for seasons that don't have matchup data yet, with SSE progress.

---

## Implementation Plan

### Prerequisites

- Playoff data spec must be implemented first (at least PR 1: playoff_round on matchups)
- Championship detection can be added incrementally

### PR 1: Backend — Franchise History Endpoint

1. **New endpoint** — `GET /api/leagues/{league_id}/franchise-history`
2. **Query all seasons** in the league group via `league_group_id`
3. **Aggregate standings** for career record
4. **Walk matchups** for highlights and streaks
5. **Parse starters JSON** for best performers
6. **Return data completeness** info
7. **Pydantic response schemas** for the full response
8. **Tests** — unit tests for streak calculation, highlight detection, best performer extraction

### PR 2: Frontend — Franchise History Page

1. **New API function** — `getFranchiseHistory(leagueId)`
2. **Restructure LeagueDetailPage** navigation:
   - "Franchise History" as default landing tab
   - Season years as drill-down tabs
3. **Franchise History UI** — career record card, highlights card, best performers, season history table
4. **Data completeness banner** with sync trigger
5. **Loading state** — spinner while computing (may be slow for many seasons)

### PR 3: Historical Matchup Backfill

1. **"Sync full history" action** — new endpoint or extension of existing sync
2. **SSE progress** for historical matchup fetch
3. **Frontend trigger** — button on franchise history page
4. **Auto-refresh** franchise history stats after backfill completes

---

## Edge Cases

- **Single season league** — franchise history is just current season stats. Still useful for highlights and best performers.
- **No matchup data** — show career record from standings only. Highlights section shows "Sync matchups to see highlight stats."
- **Cross-platform leagues** — league group may span Sleeper + MFL seasons. Stats aggregate across both. Season history table shows platform badge per row.
- **Ties** — streaks end on ties (a tie is neither a win nor a loss).
- **Bye weeks / no opponent** — some leagues have bye weeks where a team doesn't play. Skip these for streak calculation.
- **Best ball / guillotine leagues** — no traditional H2H matchups or playoffs. Playoff result column shows "—". Franchise history still shows career record and highlights from whatever matchup data exists, but championship/playoff stats are excluded.

---

## Out of Scope (Future)

- Head-to-head record vs specific opponents
- Trade history analysis (best/worst trades)
- Draft grade history
- Waiver wire success rate
- Playoff bracket visualization
- Comparison view (your franchise vs another)
