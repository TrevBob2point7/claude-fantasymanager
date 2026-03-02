# Data Model

> **Keep this document in sync with the codebase.** When SQLAlchemy models or Alembic migrations change, update this file to match.

## Entity Relationship Diagram

```
┌──────────┐     ┌───────────────────┐     ┌──────────┐
│  users   │────<│ platform_accounts │     │ players  │
│          │     └───────────────────┘     │          │
│          │                               │          │
│          │────<┌──────────────┐>────────<│          │
│          │     │ user_leagues │          │          │
│          │     │              │          │          │>────┌────────────┐
│          │     │              │>────┐    │          │     │ player_adp │
│          │     └──────────────┘     │    └──────────┘     └────────────┘
│          │           │  │  │        │         │
│          │           │  │  │        │         │
│          │────<┌──────────┐  │      │    ┌───────────────┐
│          │     │ sync_log │  │      │    │ player_scores │
│          │     └──────────┘  │      │    └───────────────┘
│          │                   │      │         │
└──────────┘            ┌──────────┐  │    ┌─────────────────┐
                        │ rosters  │  │    │ projected_scores│
                        └──────────┘  │    └─────────────────┘
                                      │
                        ┌──────────┐  │    ┌──────────────┐
                        │standings │──┘    │ transactions │
                        └──────────┘       └──────────────┘
                                                │
                        ┌──────────┐            │
                        │matchups  │────────────┘
                        └──────────┘      (both via league_id)
```

**Key:** `────<` = one-to-many, `>────` = many-to-one

---

## Enums

All enums are defined in `backend/app/models/enums.py` and stored as PostgreSQL enum types.

| Python Enum | PG Type | Values |
|---|---|---|
| `PlatformType` | `platformtype` | `sleeper`, `mfl`, `espn` |
| `Position` | `playerposition` | `QB`, `RB`, `WR`, `TE`, `K`, `DEF`, `DL`, `LB`, `DB`, `FLEX`, `SUPERFLEX`, `BENCH`, `IR` |
| `ScoringType` | `scoringtype` | `standard`, `half_ppr`, `ppr`, `custom` |
| `PlayerStatus` | `playerstatus` | `active`, `injured_reserve`, `out`, `questionable`, `doubtful`, `suspended` |
| `TransactionType` | `transactiontype` | `add`, `drop`, `trade`, `waiver` |
| `SyncStatus` | `syncstatus` | `pending`, `in_progress`, `completed`, `failed` |
| `LeagueType` | `leaguetype` | `redraft`, `keeper`, `dynasty` |
| `ADPFormat` | `adpformat` | `standard`, `half_ppr`, `ppr`, `superflex`, `dynasty`, `two_qb` |
| `DataType` | `datatype` | `leagues`, `rosters`, `matchups`, `standings`, `players`, `transactions` |

---

## Tables

### `users`

App user accounts.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `email` | VARCHAR(320) | NO | — | UNIQUE |
| `hashed_password` | VARCHAR(128) | NO | — | bcrypt via passlib |
| `display_name` | VARCHAR(100) | YES | — | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Relationships:** `platform_accounts`, `user_leagues`, `sync_logs`

---

### `platform_accounts`

Linked platform credentials (Sleeper username, MFL cookie, etc.).

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → `users.id` |
| `platform_type` | `platformtype` | NO | — | |
| `platform_username` | VARCHAR(100) | YES | — | e.g. Sleeper username |
| `platform_user_id` | VARCHAR(100) | YES | — | Platform's internal user ID |
| `credentials_json` | JSON | YES | — | Platform-specific auth data |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(user_id, platform_type)` — one account per platform per user

---

### `players`

Canonical player records with cross-platform IDs. Imported from DynastyProcess CSV.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `full_name` | VARCHAR(150) | NO | — | |
| `position` | `playerposition` | YES | — | |
| `team` | VARCHAR(10) | YES | — | NFL team abbreviation |
| `sleeper_id` | VARCHAR(50) | YES | — | UNIQUE |
| `mfl_id` | VARCHAR(50) | YES | — | UNIQUE |
| `espn_id` | VARCHAR(50) | YES | — | UNIQUE |
| `status` | `playerstatus` | YES | — | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Relationships:** `rosters`, `player_scores`, `projected_scores`, `adp_entries`

---

### `leagues`

League metadata synced from platforms.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `platform_type` | `platformtype` | NO | — | |
| `platform_league_id` | VARCHAR(100) | NO | — | Platform's league ID |
| `name` | VARCHAR(200) | NO | — | |
| `season` | INTEGER | NO | — | e.g. 2025 |
| `roster_size` | INTEGER | YES | — | |
| `scoring_type` | `scoringtype` | YES | — | |
| `league_type` | `leaguetype` | YES | — | |
| `settings_json` | JSON | YES | — | Raw platform settings blob |
| `previous_league_id` | VARCHAR(100) | YES | — | Platform's league ID for the prior season (used to chain seasons together) |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(platform_type, platform_league_id, season)`
**Relationships:** `user_leagues`, `standings`, `matchups`, `player_scores`, `projected_scores`, `transactions`

**Season chaining:** Sleeper (and potentially other platforms) assign different `platform_league_id` values to each season of the same logical league. The `previous_league_id` field stores the platform's league ID for the prior season, forming a linked list: `2025 → 2024 → 2023 → null`. This chain is used to group seasons for the League Detail season selector and Dashboard deduplication.

---

### `user_leagues`

Junction table: which users are in which leagues. Also stores the user's team identity within that league.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → `users.id` |
| `league_id` | UUID | NO | — | FK → `leagues.id` |
| `team_name` | VARCHAR(200) | YES | — | User's team name in this league |
| `platform_team_id` | VARCHAR(100) | YES | — | Platform's roster/team ID |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(user_id, league_id)`
**Relationships:** `user`, `league`, `rosters`, `standings`

---

### `rosters`

Player roster assignments per user-league.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_league_id` | UUID | NO | — | FK → `user_leagues.id` |
| `player_id` | UUID | NO | — | FK → `players.id` |
| `slot` | VARCHAR(20) | YES | — | e.g. QB, RB, FLEX, BENCH, TAXI, IR |
| `acquired_date` | DATE | YES | — | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(user_league_id, player_id)`

---

### `standings`

League standings and win/loss records.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `league_id` | UUID | NO | — | FK → `leagues.id` |
| `user_league_id` | UUID | NO | — | FK → `user_leagues.id` |
| `wins` | INTEGER | NO | `0` | |
| `losses` | INTEGER | NO | `0` | |
| `ties` | INTEGER | NO | `0` | |
| `points_for` | NUMERIC(10,2) | NO | `0` | |
| `points_against` | NUMERIC(10,2) | NO | `0` | |
| `rank` | INTEGER | YES | — | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(league_id, user_league_id)`

---

### `matchups`

Weekly matchup pairings and scores.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `league_id` | UUID | NO | — | FK → `leagues.id` |
| `week` | INTEGER | NO | — | |
| `home_user_league_id` | UUID | NO | — | FK → `user_leagues.id` |
| `away_user_league_id` | UUID | NO | — | FK → `user_leagues.id` |
| `home_score` | NUMERIC(10,2) | YES | — | |
| `away_score` | NUMERIC(10,2) | YES | — | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

---

### `player_scores`

Actual player scoring data per week.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `player_id` | UUID | NO | — | FK → `players.id` |
| `league_id` | UUID | NO | — | FK → `leagues.id` |
| `week` | INTEGER | NO | — | |
| `season` | INTEGER | NO | — | |
| `points` | NUMERIC(10,2) | YES | — | |
| `stats_json` | JSON | YES | — | Raw stat breakdown |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(player_id, league_id, week, season)`

---

### `projected_scores`

Player projections per week.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `player_id` | UUID | NO | — | FK → `players.id` |
| `league_id` | UUID | NO | — | FK → `leagues.id` |
| `week` | INTEGER | NO | — | |
| `season` | INTEGER | NO | — | |
| `projected_points` | NUMERIC(10,2) | YES | — | |
| `source` | VARCHAR(50) | YES | — | e.g. "sleeper", "espn" |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(player_id, league_id, week, season)`

---

### `transactions`

Trades, waivers, add/drops.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `league_id` | UUID | NO | — | FK → `leagues.id` |
| `type` | `transactiontype` | NO | — | |
| `week` | INTEGER | NO | — | |
| `player_id` | UUID | YES | — | FK → `players.id` |
| `from_user_league_id` | UUID | YES | — | FK → `user_leagues.id` |
| `to_user_league_id` | UUID | YES | — | FK → `user_leagues.id` |
| `timestamp` | TIMESTAMPTZ | NO | `now()` | When the transaction occurred |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

---

### `player_adp`

ADP data per player from multiple sources and formats.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `player_id` | UUID | NO | — | FK → `players.id` |
| `source` | VARCHAR(50) | NO | — | e.g. "sleeper", "ffc", "dynastyprocess" |
| `format` | `adpformat` | NO | — | |
| `season` | INTEGER | NO | — | |
| `adp` | NUMERIC(8,2) | NO | — | Max 999,999.99 |
| `position_rank` | INTEGER | YES | — | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

**Unique constraint:** `(player_id, source, format, season)`

---

### `team_bye_weeks`

NFL bye week data per team per season. Static data fetched once per season from the ESPN Fantasy API.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `season` | INTEGER | NO | — | e.g. 2025 |
| `team` | VARCHAR(10) | NO | — | NFL team abbreviation, uppercase (e.g. "KC", "PHI") |
| `bye_week` | INTEGER | NO | — | Week number |

**Unique constraint:** `(season, team)`

**Source:** `GET https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{YEAR}?view=proTeamSchedules_wl` — returns `settings.proTeams[]` with `abbrev` (mixed case, normalize to uppercase) and `byeWeek` fields. Filter out the "FA" entry (`byeWeek: 0`).

---

### `sync_log`

Sync operation history for tracking and debugging.

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → `users.id` |
| `platform_type` | `platformtype` | NO | — | |
| `data_type` | `datatype` | NO | — | What was synced |
| `status` | `syncstatus` | NO | `'pending'` | |
| `started_at` | TIMESTAMPTZ | YES | — | |
| `completed_at` | TIMESTAMPTZ | YES | — | |
| `error_message` | TEXT | YES | — | |
| `created_at` | TIMESTAMPTZ | NO | `now()` | |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Auto-updated |

---

## Indexes

All primary keys have implicit indexes. Additional indexes:

| Table | Index | Columns | Type |
|---|---|---|---|
| `users` | `users_email_key` | `email` | UNIQUE |
| `players` | `players_sleeper_id_key` | `sleeper_id` | UNIQUE |
| `players` | `players_mfl_id_key` | `mfl_id` | UNIQUE |
| `players` | `players_espn_id_key` | `espn_id` | UNIQUE |
| `leagues` | `leagues_platform_type_platform_league_id_season_key` | `(platform_type, platform_league_id, season)` | UNIQUE |
| `platform_accounts` | `platform_accounts_user_id_platform_type_key` | `(user_id, platform_type)` | UNIQUE |
| `user_leagues` | `user_leagues_user_id_league_id_key` | `(user_id, league_id)` | UNIQUE |
| `rosters` | `rosters_user_league_id_player_id_key` | `(user_league_id, player_id)` | UNIQUE |
| `standings` | `standings_league_id_user_league_id_key` | `(league_id, user_league_id)` | UNIQUE |
| `player_scores` | `player_scores_player_id_league_id_week_season_key` | `(player_id, league_id, week, season)` | UNIQUE |
| `projected_scores` | `projected_scores_player_id_league_id_week_season_key` | `(player_id, league_id, week, season)` | UNIQUE |
| `player_adp` | `player_adp_player_id_source_format_season_key` | `(player_id, source, format, season)` | UNIQUE |
| `team_bye_weeks` | `team_bye_weeks_season_team_key` | `(season, team)` | UNIQUE |

---

## Database Configuration

- **Engine:** PostgreSQL 16
- **Driver:** `asyncpg` (async)
- **ORM:** SQLAlchemy 2.x with mapped columns (`DeclarativeBase`)
- **Migrations:** Alembic with async support
- **Session:** `AsyncSession` via `async_sessionmaker`, `expire_on_commit=False`
- **ID generation:** `gen_random_uuid()` (server-side)
- **Timestamps:** All tables have `created_at` / `updated_at` with `server_default=now()`. `updated_at` uses `onupdate=now()` at the ORM level.

### Source Files

| File | Purpose |
|---|---|
| `backend/app/core/database.py` | Engine, session factory, `Base` class, `get_db` dependency |
| `backend/app/core/config.py` | `DATABASE_URL` and other settings via pydantic-settings |
| `backend/app/models/enums.py` | All enum definitions |
| `backend/app/models/*.py` | One file per model |
| `backend/app/models/__init__.py` | Re-exports all models and enums |
| `backend/alembic/` | Migration scripts |
