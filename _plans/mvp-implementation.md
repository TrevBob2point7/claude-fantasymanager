# Fantasy Manager MVP Implementation Plan

## Context

The project has full infrastructure scaffolding (FastAPI + React + PostgreSQL in Docker Compose) but zero business logic. All feature directories (`models/`, `schemas/`, `platforms/`, `sync/`, `auth/`, `components/`, `pages/`, etc.) are empty placeholders. This plan delivers the MVP features: user auth, Sleeper account linking, league discovery, data sync, dashboard, and league detail views.

**Key decisions:**
- Tailwind CSS for frontend styling, Sleeper-inspired dark theme
- Sleeper platform first, MFL as fast-follow after MVP
- Phase-by-phase execution with review between phases
- Default season: 2025 for league discovery
- Missing players during sync: create stub records (sleeper_id + raw name), backfill on next player import
- Backend tests: real PostgreSQL (separate `fantasy_manager_test` DB, requires Docker)
- Auth UX: full-page spinner with logo while validating stored JWT on app startup

---

## Design System: Sleeper-Inspired Theme

The UI mimics Sleeper's dark, modern aesthetic. All values below are configured in Tailwind's `tailwind.config.ts` as custom theme extensions.

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `background` | `#05091d` | Page/app background (Sleeper's "Black Pearl") |
| `surface` | `#0f1328` | Cards, panels, elevated containers |
| `surface-hover` | `#161b35` | Hover state for cards/rows |
| `border` | `#1e2442` | Subtle borders, dividers |
| `text-primary` | `#e8eaf0` | Primary text (near-white) |
| `text-secondary` | `#8b90a0` | Secondary/muted text |
| `accent` | `#00fff9` | Primary accent — Sleeper's signature cyan |
| `accent-green` | `#00CEB8` | Success states, win indicators |
| `accent-orange` | `#FF6F42` | Warnings, loss indicators |
| `accent-yellow` | `#e7fe53` | Highlights, Sleeper's "Canary" |
| `destructive` | `#ef4444` | Errors, delete actions |

### Typography

| Role | Font | Weight |
|------|------|--------|
| Headings / Display | `Poppins` | 600-700 |
| Body / UI | `Inter` | 400-500 |
| Scores / Numbers | `Oswald` | 600 |
| Monospace | system monospace stack | 400 |

Load via Google Fonts: `Poppins:wght@600;700`, `Inter:wght@400;500;600`, `Oswald:wght@600`

### Design Tokens

| Token | Value |
|-------|-------|
| Border radius (base) | `6px` |
| Border radius (cards) | `12px` / `1rem` |
| Border radius (buttons) | `6px` |
| Transition | `150ms cubic-bezier(0.4, 0, 0.2, 1)` |
| Min tap target | `44px` |

### Component Patterns

- **Cards**: `bg-surface` with `border border-border` and `rounded-xl`, subtle hover lift
- **Tables**: Dark rows with alternating `bg-surface`/`bg-background`, cyan accent on selected row
- **Buttons (primary)**: `bg-accent text-background font-semibold rounded-md px-4 py-2`
- **Buttons (secondary)**: `bg-surface border border-border text-text-primary`
- **Navigation**: Side drawer on desktop, bottom tabs on mobile (Sleeper pattern)
- **Inputs**: `bg-surface border border-border text-text-primary` with cyan focus ring
- **Position badges**: Color-coded chips (QB=red, RB=cyan, WR=green, TE=orange, K/DEF=gray)

### Tailwind Configuration

In Phase 1D, create `frontend/tailwind.config.ts` extending the default theme with all colors, fonts, and radii above. Add `@import "tailwindcss"` to `frontend/src/index.css`. Import Google Fonts in `frontend/index.html`.

---

## Agent Roles

| Agent | Scope | Key Files |
|-------|-------|-----------|
| **Lead** | Coordination, dependency management, phase verification, code review | `Makefile`, `docker-compose.yml`, `main.py` |
| **Database** | SQLAlchemy models, Alembic migrations, DB schema | `backend/app/models/`, `backend/alembic/` |
| **Backend** | Auth module, API routes, platform adapters, sync engine, Pydantic schemas | `backend/app/auth/`, `backend/app/api/`, `backend/app/platforms/`, `backend/app/sync/`, `backend/app/schemas/` |
| **Frontend** | React components, pages, routing, Tailwind styling, API client | `frontend/src/` |
| **QA** | Test infrastructure, unit/integration/e2e tests | `backend/tests/`, `frontend/e2e/` |

---

## Task List by Agent

### Database Agent

| ID | Task | Phase | Depends On | Files |
|----|------|-------|------------|-------|
| DB-1 | Create all 12 SQLAlchemy models (see Model Reference below) | 1 | — | `backend/app/models/*.py` |
| DB-2 | Update `models/__init__.py` to import all models | 1 | DB-1 | `backend/app/models/__init__.py` |
| DB-3 | Generate initial Alembic migration | 1 | DB-2 | `backend/alembic/versions/` |
| DB-4 | Run migration and verify schema | 1 | DB-3 | — |

#### Model Reference

| Model File | Table | Key Fields |
|-----------|-------|------------|
| `user.py` | `users` | id (UUID), email, hashed_password, display_name, created_at, updated_at |
| `platform_account.py` | `platform_accounts` | id, user_id FK, platform_type, platform_username, platform_user_id, credentials_json |
| `player.py` | `players` | id, full_name, position, team, sleeper_id, mfl_id, espn_id, status |
| `league.py` | `leagues` | id, platform_type, platform_league_id, name, season, roster_size, scoring_type, settings_json |
| `user_league.py` | `user_leagues` | id, user_id FK, league_id FK, team_name, platform_team_id |
| `roster.py` | `rosters` | id, user_league_id FK, player_id FK, slot, acquired_date |
| `standing.py` | `standings` | id, league_id FK, user_league_id FK, wins, losses, ties, points_for, points_against, rank |
| `matchup.py` | `matchups` | id, league_id FK, week, home/away_user_league_id FKs, home/away_score |
| `player_score.py` | `player_scores` | id, player_id FK, league_id FK, week, season, points, stats_json |
| `projected_score.py` | `projected_scores` | id, player_id FK, league_id FK, week, season, projected_points, source |
| `transaction.py` | `transactions` | id, league_id FK, type enum, player_id FK, from/to_user_league_id FKs, timestamp |
| `sync_log.py` | `sync_log` | id, user_id FK, platform_type, data_type, status enum, started_at, completed_at, error_message |

**Implementation details:**
- SQLAlchemy 2.0 style (`Mapped`, `mapped_column`)
- UUID PKs via `gen_random_uuid()`
- `created_at`/`updated_at` with server defaults

---

### Backend Agent

| ID | Task | Phase | Depends On | Files |
|----|------|-------|------------|-------|
| BE-1 | Auth module: `passwords.py`, `tokens.py`, `dependencies.py` | 1 | DB-1 | `backend/app/auth/` |
| BE-2 | Pydantic schemas: `user.py`, `auth.py` | 1 | — | `backend/app/schemas/user.py`, `backend/app/schemas/auth.py` |
| BE-3 | Add `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` to config | 1 | — | `backend/app/core/config.py` |
| BE-4 | Install `email-validator` dependency | 1 | — | `backend/pyproject.toml` |
| BE-5 | Auth API routes: `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | 2 | BE-1, BE-2, DB-4 | `backend/app/api/auth.py`, `backend/app/main.py` |
| BE-6 | Platform account schemas | 2 | DB-4 | `backend/app/schemas/platform_account.py` |
| BE-7 | Platform account CRUD routes: `POST/GET/DELETE /platforms/accounts` | 2 | BE-6, DB-4 | `backend/app/api/platforms.py`, `backend/app/main.py` |
| BE-8 | Platform adapter base class + registry | 3 | — | `backend/app/platforms/base.py`, `backend/app/platforms/schemas.py`, `backend/app/platforms/registry.py` |
| BE-9 | Sleeper adapter implementation | 3 | BE-8 | `backend/app/platforms/sleeper.py` |
| BE-10 | Player import service (DynastyProcess CSV) | 3 | DB-4 | `backend/app/sync/player_import.py` |
| BE-11 | Sync engine: `SyncEngine` class with all sync methods | 3 | BE-9, DB-4 | `backend/app/sync/engine.py` |
| BE-12 | League & sync Pydantic schemas | 3 | — | `backend/app/schemas/league.py`, `backend/app/schemas/sync.py` |
| BE-13 | League API routes: `POST /discover`, `GET /`, `GET /{id}` | 3 | BE-11, BE-12 | `backend/app/api/leagues.py`, `backend/app/main.py` |
| BE-14 | Sync API routes: `POST /{account_id}`, `GET /log` | 3 | BE-11, BE-12 | `backend/app/api/sync.py`, `backend/app/main.py` |
| BE-15 | Background sync scheduler (APScheduler) | 5 | BE-11 | `backend/app/sync/scheduler.py`, `backend/app/main.py`, `backend/app/core/config.py` |

**Auth module details:**
- `passwords.py` — `hash_password()`, `verify_password()` using passlib+bcrypt
- `tokens.py` — `create_access_token()`, `decode_access_token()` using python-jose
- `dependencies.py` — `get_current_user` FastAPI dependency (OAuth2PasswordBearer, DB lookup, 401 on failure)

**Sleeper adapter endpoints:**
- User lookup: `GET /user/{username}`
- Leagues: `GET /user/{user_id}/leagues/nfl/{season}`
- Rosters: `GET /league/{id}/rosters`
- Matchups: `GET /league/{id}/matchups/{week}`
- Transactions: `GET /league/{id}/transactions/{week}`

**Sync engine methods:**
- `sync_leagues(user_id, platform_account_id)` — discover & upsert leagues
- `sync_rosters(league_id)`, `sync_matchups(league_id, week)`, `sync_standings(league_id)`, `sync_transactions(league_id, week)`
- `sync_all(user_id, platform_account_id)` — orchestrate all
- Each operation logs to `sync_log` table
- Use `insert().on_conflict_do_update()` for upserts

---

### Frontend Agent

| ID | Task | Phase | Depends On | Files |
|----|------|-------|------------|-------|
| FE-1 | Install `react-router-dom`, `tailwindcss`, `@tailwindcss/vite` | 1 | — | `frontend/package.json` |
| FE-2 | Tailwind config with Sleeper theme (see Design System) | 1 | FE-1 | `frontend/tailwind.config.ts`, `frontend/src/index.css`, `frontend/index.html` |
| FE-3 | API client: fetch wrapper with auth header injection, 401 redirect | 1 | — | `frontend/src/api/client.ts` |
| FE-4 | TypeScript interfaces: `User`, `LoginRequest/Response`, `RegisterRequest` | 1 | — | `frontend/src/api/types.ts` |
| FE-5 | Auth context: state, login/register/logout, JWT localStorage | 1 | FE-3, FE-4 | `frontend/src/context/AuthContext.tsx` |
| FE-6 | Layout shell: header, nav, main content area | 1 | FE-2 | `frontend/src/components/Layout.tsx` |
| FE-7 | ProtectedRoute component | 1 | FE-5 | `frontend/src/components/ProtectedRoute.tsx` |
| FE-8 | Auth pages: LoginPage, RegisterPage | 1 | FE-2, FE-5 | `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/RegisterPage.tsx` |
| FE-9 | Placeholder pages: DashboardPage, NotFoundPage | 1 | FE-2 | `frontend/src/pages/DashboardPage.tsx`, `frontend/src/pages/NotFoundPage.tsx` |
| FE-10 | App routing: BrowserRouter + Routes + AuthProvider | 1 | FE-5, FE-6, FE-7, FE-8, FE-9 | `frontend/src/App.tsx`, `frontend/src/main.tsx` |
| FE-11 | Wire auth pages to real API endpoints | 2 | FE-10, BE-5 | `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/RegisterPage.tsx`, `frontend/src/context/AuthContext.tsx` |
| FE-12 | API client functions: platforms, leagues, sync | 4 | BE-7, BE-13, BE-14 | `frontend/src/api/platforms.ts`, `frontend/src/api/leagues.ts`, `frontend/src/api/sync.ts` |
| FE-13 | Extend TypeScript interfaces: League, Roster, Standing, Matchup, Transaction, SyncLog | 4 | — | `frontend/src/api/types.ts` |
| FE-14 | Custom hooks: `useLeagues`, `useSyncStatus` | 4 | FE-12 | `frontend/src/hooks/useLeagues.ts`, `frontend/src/hooks/useSyncStatus.ts` |
| FE-15 | Link Accounts page + components | 4 | FE-12 | `frontend/src/pages/LinkAccountsPage.tsx`, `frontend/src/components/PlatformAccountCard.tsx`, `frontend/src/components/LinkAccountForm.tsx` |
| FE-16 | Dashboard: LeagueCard grid, SyncButton, EmptyState | 4 | FE-14 | `frontend/src/pages/DashboardPage.tsx`, `frontend/src/components/LeagueCard.tsx`, `frontend/src/components/SyncButton.tsx`, `frontend/src/components/EmptyState.tsx` |
| FE-17 | League detail page with tabs: Roster, Standings, Matchups, Transactions | 4 | FE-14 | `frontend/src/pages/LeagueDetailPage.tsx`, `frontend/src/components/RosterTable.tsx`, `frontend/src/components/StandingsTable.tsx`, `frontend/src/components/MatchupCard.tsx`, `frontend/src/components/TransactionItem.tsx` |
| FE-18 | Mobile responsive polish | 5 | FE-16, FE-17 | `frontend/src/components/Layout.tsx`, all page/component files |

**Mobile polish details:**
- Hamburger menu / mobile nav in Layout
- Responsive grid breakpoints on dashboard (1/2/3 columns)
- Scrollable tables on mobile
- Touch-friendly tap targets (44px min)

---

### QA Agent

| ID | Task | Phase | Depends On | Files |
|----|------|-------|------------|-------|
| QA-1 | Test infrastructure: real test DB, async session fixture, per-test cleanup, `authenticated_client` fixture | 2 | DB-4 | `backend/tests/conftest.py` |
| QA-2 | Test factories: User, PlatformAccount, League | 2 | DB-4 | `backend/tests/factories.py` |
| QA-3 | Auth endpoint tests | 2 | BE-5, QA-1, QA-2 | `backend/tests/test_auth.py` |
| QA-4 | Platform account CRUD tests | 2 | BE-7, QA-1, QA-2 | `backend/tests/test_platform_accounts.py` |
| QA-5 | Sleeper adapter unit tests (mocked HTTP via `respx`) | 3 | BE-9 | `backend/tests/test_platforms/test_sleeper.py` |
| QA-6 | Sync engine integration tests | 3 | BE-11, QA-1 | `backend/tests/test_sync/test_engine.py` |
| QA-7 | League API integration tests | 3 | BE-13, QA-1 | `backend/tests/test_leagues.py` |
| QA-8 | Sync API integration tests | 3 | BE-14, QA-1 | `backend/tests/test_sync.py` |
| QA-9 | E2E: auth flow (register, login, logout) | 5 | FE-11 | `frontend/e2e/tests/auth.spec.ts` |
| QA-10 | E2E: link account + discover leagues | 5 | FE-15 | `frontend/e2e/tests/link-account.spec.ts` |
| QA-11 | E2E: dashboard loads, navigate to detail | 5 | FE-16 | `frontend/e2e/tests/dashboard.spec.ts` |
| QA-12 | E2E: league detail tabs + data display | 5 | FE-17 | `frontend/e2e/tests/league-detail.spec.ts` |

**Test infrastructure details:**
- Install `respx` (dev) for mocking httpx in adapter tests
- Real PostgreSQL with separate `fantasy_manager_test` DB (requires Docker)
- factory-boy factories for test data generation

---

### Lead Agent

| ID | Task | Phase | Depends On | Files |
|----|------|-------|------------|-------|
| LEAD-1 | Phase 1 kickoff: spawn DB, Backend, Frontend agents in parallel | 1 | — | — |
| LEAD-2 | Phase 1 review: verify models, auth, schemas, frontend shell | 1 | DB-4, BE-1, BE-2, BE-3, BE-4, FE-10 | — |
| LEAD-3 | Phase 1 verification: `make lint && make typecheck && make test` | 1 | LEAD-2 | — |
| LEAD-4 | Phase 2 kickoff: spawn Backend, QA, Frontend agents | 2 | LEAD-3 | — |
| LEAD-5 | Phase 2 review: verify auth flow end-to-end, platform CRUD, tests pass | 2 | BE-5, BE-7, QA-3, QA-4, FE-11 | — |
| LEAD-6 | Phase 2 verification: `make test && make lint && make typecheck` | 2 | LEAD-5 | — |
| LEAD-7 | Phase 3 kickoff: spawn Backend, QA agents | 3 | LEAD-6 | — |
| LEAD-8 | Phase 3 review: verify adapter, sync engine, API routes, tests | 3 | BE-13, BE-14, QA-5, QA-6, QA-7, QA-8 | — |
| LEAD-9 | Phase 3 verification: `make test && make lint` | 3 | LEAD-8 | — |
| LEAD-10 | Phase 4 kickoff: spawn Frontend agent | 4 | LEAD-9 | — |
| LEAD-11 | Phase 4 review: verify all pages, API integration, data display | 4 | FE-15, FE-16, FE-17 | — |
| LEAD-12 | Phase 4 verification: `make test && make lint && make typecheck && make build && make up` | 4 | LEAD-11 | — |
| LEAD-13 | Phase 5 kickoff: spawn Backend, Frontend, QA agents in parallel | 5 | LEAD-12 | — |
| LEAD-14 | Phase 5 review: verify scheduler, mobile UX, all tests | 5 | BE-15, FE-18, QA-9, QA-10, QA-11, QA-12 | — |
| LEAD-15 | Final MVP verification: full smoke test (see checklist below) | 5 | LEAD-14 | — |

---

## Phase Summary

### Phase 1: Foundation
**Goal:** Database schema, auth primitives, frontend routing — everything downstream depends on this.

**Parallel work:**
- Database Agent: DB-1 → DB-2 → DB-3 → DB-4
- Backend Agent: BE-1, BE-2, BE-3, BE-4 (all parallel)
- Frontend Agent: FE-1 → FE-2, then FE-3 through FE-10

### Phase 2: Auth Endpoints + Platform Linking
**Goal:** Working registration/login flow and ability to link Sleeper accounts.

**Parallel work:**
- Backend Agent: BE-5, BE-6 → BE-7 (parallel where possible)
- QA Agent: QA-1, QA-2 → QA-3, QA-4
- Frontend Agent: FE-11 (after BE-5 lands)

### Phase 3: Sleeper Adapter + Sync Engine
**Goal:** Connect to Sleeper API, pull leagues/rosters/standings/matchups, store in DB.

**Parallel work:**
- Backend Agent: BE-8 → BE-9 → BE-11 → BE-13, BE-14 (serial chain); BE-10, BE-12 (parallel)
- QA Agent: QA-5, QA-6, QA-7, QA-8 (as backend tasks complete)

### Phase 4: Frontend Dashboard + League Views
**Goal:** Build the pages that make the app usable.

**Parallel work:**
- Frontend Agent: FE-12, FE-13 → FE-14 → FE-15, FE-16, FE-17 (parallel after hooks)

### Phase 5: Polish + Testing
**Goal:** Scheduled sync, mobile responsiveness, comprehensive testing.

**Parallel work:**
- Backend Agent: BE-15
- Frontend Agent: FE-18
- QA Agent: QA-9, QA-10, QA-11, QA-12

---

## Dependency Graph

```
                    PHASE 1                              PHASE 2
   ┌──────────────────────────────────────┐   ┌──────────────────────────┐
   │                                      │   │                          │
   │  DB-1 → DB-2 → DB-3 → DB-4 ────────────→ QA-1, QA-2               │
   │                    │                 │   │   │                      │
   │  BE-1 ─────────────┼────────────────────→ BE-5 ──→ FE-11           │
   │  BE-2 ─────────────┤                │   │   │                      │
   │  BE-3              │                │   │ BE-6 → BE-7              │
   │  BE-4              │                │   │          │                │
   │                    │                │   │ QA-3, QA-4               │
   │  FE-1 → FE-2 ─────┤                │   │                          │
   │  FE-3, FE-4 → FE-5 → FE-6 → FE-10 │   │                          │
   │         FE-7, FE-8, FE-9 ──┘       │   │                          │
   └──────────────────────────────────────┘   └──────────────────────────┘

              PHASE 3                                    PHASE 4
   ┌─────────────────────────────────┐      ┌──────────────────────────────┐
   │                                 │      │                              │
   │  BE-8 → BE-9 → BE-11 → BE-13 ────────→ FE-12, FE-13 → FE-14        │
   │                    │     BE-14 ────────→        │                     │
   │  BE-10 (parallel)  │           │      │  FE-15, FE-16, FE-17        │
   │  BE-12 (parallel)  │           │      │                              │
   │                    │           │      └──────────────────────────────┘
   │  QA-5, QA-6, QA-7, QA-8       │
   └─────────────────────────────────┘               PHASE 5
                                            ┌──────────────────────────────┐
                                            │  BE-15                       │
                                            │  FE-18                       │
                                            │  QA-9, QA-10, QA-11, QA-12  │
                                            └──────────────────────────────┘
```

**Critical path:** DB-1 → DB-4 → BE-5 → BE-9 → BE-11 → BE-13 → FE-12 → FE-14 → FE-16/FE-17 → QA-11/QA-12

---

## New Dependencies to Install

| Package | Where | Phase | Agent |
|---------|-------|-------|-------|
| `email-validator` | backend | 1 | Backend |
| `react-router-dom` | frontend | 1 | Frontend |
| `tailwindcss` + `@tailwindcss/vite` | frontend | 1 | Frontend |
| `respx` (dev) | backend | 3 | QA |
| `apscheduler` | backend | 5 | Backend |

---

## Verification

**After each phase (Lead Agent):**
1. `make test` — all backend + frontend unit tests pass
2. `make lint && make typecheck` — no lint or type errors
3. `make build && make up` — Docker Compose stack starts cleanly
4. Manual smoke test of new features via browser at `http://localhost:3000`

**Final MVP verification (Lead Agent — LEAD-15):**
1. Register a new user, log in
2. Link a Sleeper account by username
3. Discover leagues for current season
4. Sync rosters, standings, matchups
5. View dashboard with league cards
6. Click into league detail, browse all tabs
7. Trigger manual "Sync Now", verify data updates
8. `make test-e2e` — all Playwright tests pass
