# Product Spec

## Vision

All-in-one fantasy football dashboard that aggregates your leagues across multiple platforms into a single unified view. NFL only.

Designed for personal use today, built to support multiple users (friends, league-mates) as a hosted service.

---

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| **Sleeper** | Active (primary) | Free public read-only API. No auth needed for reads. |
| **MFL** (MyFantasyLeague) | Active (in progress) | Cookie-based auth. Year-based API paths (`/2025/export`). |
| ESPN | Future | — |
| Yahoo | Future | — |
| NFL | Future | — |

New platforms are added via an adapter pattern (`PlatformAdapter` ABC).

---

## League Types

All four types are actively played and must be supported:

| Type | Description | Sleeper API Mapping |
|------|-------------|---------------------|
| **Redraft** | Standard seasonal league, draft fresh each year | `settings.type: 0` |
| **Keeper** | Keep a limited number of players year-over-year | `settings.type: 1` |
| **Dynasty** | Keep entire roster year-over-year, rookie drafts, taxi squads | `settings.type: 2` |
| **Guillotine** | Lowest-scoring team each week is eliminated, roster goes to waivers | `settings.type: 3` |

**Best Ball** is a modifier, not a league type. Any league type can have best ball enabled (`settings.best_ball: 1`), which auto-optimizes lineups each week with no manual management.
**NOTE:** Best ball might not be a modifier for the other platforms. The modifier is sleeper specific. Confirm how this works as other league support is added.

Sleeper also exposes guillotine-specific fields like `settings.last_chopped_leg` (last week a team was eliminated).

---

## Scoring Formats

| Format | Reception Points |
|--------|-----------------|
| Standard | 0 |
| Half PPR | 0.5 |
| PPR | 1.0 |
| Custom | Varies |

Each league has one scoring format. **ADP, rankings, and trade values must match the league's scoring format.** Showing dynasty values in a redraft league, or standard ADP in a PPR league, is wrong.

---

## ADP & Rankings

### Philosophy

ADP and player rankings are foundational data used across multiple features:
- **Roster context** — show ADP next to roster players to gauge value at a glance
- **Trade analysis** — compare trade values, identify buy-low/sell-high opportunities
- **Draft assistant** — help during live drafts with rankings and recommendations

**Format-specific rankings are essential.** Each league should display ADP/values that match its league type and scoring format.

### Current Data Sources

| Provider | Formats | Data Type | Access |
|----------|---------|-----------|--------|
| **Fantasy Football Calculator** | Standard, Half PPR, PPR, Dynasty, Superflex, 2QB | Mock draft ADP | Free public REST API |
| **DynastyProcess** | Dynasty | Trade values (CSV) | Free GitHub CSV, open data |
| **Sleeper** | All (same data) | `search_rank` | Free API, but returns identical rankings regardless of format |

### Sources Investigated — Not Viable

| Source | Why Not |
|--------|---------|
| **FantasyPros** | No public API. Partner API requires custom business negotiation. ToS explicitly prohibits scraping. DynastyProcess mirrors their ECR data but only best-ball rankings (incomplete — missing WR/TE). |
| **Keep Trade Cut** | No API (FAQ confirms this). ToS explicitly prohibits all automated data collection. Crowdsourced dynasty values only accessible via HTML scraping. |
| **Dynasty Trade Calculator** | Paid subscription ($2.99-$9.99/mo). No API, no documented endpoints, no OSS integrations. |

### Known Gaps

- **Best Ball ADP**: No provider currently offers best-ball-specific rankings via a free API. Best Ball ADP might basically be a redraft ADP, but we should confirm this as we bring in other league sources
- **Guillotine ADP**: Niche format, no dedicated source exists. Redraft ADP is the closest proxy.
- **Sleeper ADP quality**: Returns `search_rank` which is the same value for all formats — not truly format-specific. Useful as a fallback but not a primary source.
- **FFC is the strongest source** for format-specific redraft ADP. DynastyProcess is the strongest for dynasty values.

---

## Player Stats

Sleeper provides detailed weekly player stats via an undocumented but functional endpoint:

```
GET https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}
```

Available data per player:

| Category | Fields |
|----------|--------|
| Passing | `pass_yd`, `pass_td`, `pass_att`, `pass_cmp`, `pass_lng`, `pass_rtg`, `pass_air_yd`, `pass_ypa`, `cmp_pct` |
| Rushing | `rush_yd`, `rush_att`, `rush_td`, `rush_lng`, `rush_ypa`, `rush_fd` |
| Receiving | `rec`, `rec_yd`, `rec_td`, `rec_tgt`, `rec_lng`, `rec_ypr`, `rec_air_yd` |
| Scoring | `pts_std`, `pts_half_ppr`, `pts_ppr`, `td`, `anytime_tds` |
| Position Rank | `pos_rank_std`, `pos_rank_half_ppr`, `pos_rank_ppr` |
| Kicking | `fga`, `fgm`, `fgm_lng`, `xpa`, `xpm` |
| IDP | `idp_tkl`, `idp_tkl_solo`, `idp_tkl_ast`, `idp_qb_hit` |
| Snap Counts | `off_snp`, `def_snp`, `st_snp` |

Pre-calculates fantasy points in all three scoring formats and provides position ranks per format.

---

## Data Model — Known Gaps

These are issues identified in the current codebase that need to be addressed:

1. **`LeagueType` enum** is missing `guillotine`. Currently only has `redraft`, `keeper`, `dynasty`.
2. **`best_ball` flag** does not exist on the League model. Sleeper provides `settings.best_ball` but it's not extracted.
3. **Sleeper adapter** (`SleeperAdapter.get_leagues()`) only maps `settings.type` values 0-2. Type 3 (guillotine) falls through and stores `league_type` as `NULL`.
4. **`ADPFormat` enum** has no `best_ball` variant (though this may not be needed if no ADP source provides best-ball-specific data).
5. **Sleeper ADP provider** claims to support multiple formats but returns identical `search_rank` data for all of them.


