# Architecture

## Tech Stack Decisions

Each layer lists options that were considered. The **Decision** line records what was chosen.

### Frontend/Backend Framework

| Option | Pros | Cons |
|--------|------|------|
| **Next.js (App Router) + TypeScript** | Full-stack in one project; SSR & static generation; API routes built in; large ecosystem and community | Tied to React; heavier than needed for a small app; App Router still maturing |
| **React SPA + Python (FastAPI) backend** | Separation of concerns; Python excels at data processing/scraping; FastAPI is fast and well-documented | Two codebases to maintain; CORS configuration; separate deployments |
| **React SPA + Node.js (Express) backend** | JavaScript everywhere; lightweight and flexible backend; huge middleware ecosystem | Two codebases; less built-in structure than Next.js; manual SSR if needed |

**Decision:** React SPA + Python (FastAPI) backend

### Database

| Option | Pros | Cons |
|--------|------|------|
| **PostgreSQL + Drizzle ORM** | Robust relational DB; excellent JSON support; handles concurrent writes well; Drizzle is type-safe and lightweight | Requires running a DB server; slightly more setup |
| **SQLite + Drizzle ORM** | Zero setup; file-based; great for small scale and local dev; Drizzle provides same type-safe API | Limited concurrent writes; harder to scale; no native JSON operators |
| **PostgreSQL + Prisma** | Popular ORM; auto-generated client; Prisma Studio for visual exploration; strong migration tooling | Heavier runtime; separate generation step; slower queries than Drizzle |

**Decision:** PostgreSQL + SQLAlchemy (async)

### Auth

| Option | Pros | Cons |
|--------|------|------|
| **Auth.js v5 (NextAuth)** | Built for Next.js; handles sessions, providers, CSRF out of the box; easy setup | Tightly coupled to Next.js; less flexible outside that ecosystem |
| **Custom JWT auth** | Full control over flow; framework-agnostic; no external dependency | More code to write and maintain; security burden falls entirely on us |
| **Lucia Auth** | Lightweight; framework-agnostic; good developer experience; session-based | Smaller community; less documentation; newer project |

**Decision:** Custom JWT auth (FastAPI's `OAuth2PasswordBearer` + `python-jose` + `passlib`)

### Deployment

| Option | Pros | Cons |
|--------|------|------|
| **Docker Compose on VPS** | Full control; persistent DB; native cron jobs; cheap (~$5-6/mo) | Self-managed server; manual updates and monitoring |
| **Railway / Fly.io** | Managed platform; includes DB hosting; easy deploys from Git; decent free tiers | Costs scale with usage; less control over infrastructure |
| **Vercel + managed DB** | Excellent Next.js integration; auto-deploys on push; edge functions | Background jobs need workarounds (no persistent processes); DB hosting costs extra |

**Decision:** Docker Compose on home server, exposed via Cloudflare Tunnel (free, no open ports, automatic HTTPS) for alpha testers.

---

## Architecture Overview

### Two-Codebase Structure

- **Backend:** Python FastAPI serving a REST API, handling auth, sync, and all platform communication
- **Frontend:** React SPA (TypeScript + Vite) consuming the backend API, handling all UI rendering

### Platform Adapter Interface

A common `PlatformAdapter` Python abstract class that each platform implements. This standardizes how the backend fetches rosters, standings, matchups, etc. regardless of the underlying API differences.

### Player Identity Mapping

Uses the [DynastyProcess open-data CSV](https://github.com/dynastyprocess/data) containing ~11,600+ players with cross-platform IDs (`mfl_id`, `sleeper_id`, `espn_id`, etc.). This enables a single canonical player record that maps across all supported platforms.

### Auth

Custom JWT auth using FastAPI's `OAuth2PasswordBearer` with `python-jose` for token encoding and `passlib` for password hashing. The React SPA stores JWT tokens and sends them via `Authorization` header on each request.

### Data Sync Engine

- Scheduled background sync with configurable per-data-type frequency (APScheduler)
- Manual "Sync Now" endpoint triggered from the UI
- Sync log tracking (last sync time, status, errors per data type)
- **Slot inference:** During roster sync, the engine reads `roster_positions` from the league's `settings_json` and zips starter IDs with their positional slots (QB, RB, FLEX, etc.) instead of storing a generic "STARTER" label
- **Historical season sync:** On first sync, the engine walks the `previous_league_id` chain to discover and sync all past seasons of a league. Seasons already in the DB are skipped. This enables the League Detail season selector.
- **Bye week sync:** NFL bye weeks are fetched once per season from the ESPN Fantasy API (`proTeamSchedules_wl` view) and stored in the `team_bye_weeks` table. Team abbreviations are normalized to uppercase. ESPN failures are caught and do not block the main sync.

### Database as Cache Layer

PostgreSQL via SQLAlchemy (async). The app reads exclusively from the local database. External platform APIs are only called during sync operations. This provides fast page loads, offline resilience, and reduces API rate limit pressure.

### Deployment

Docker Compose on home server with three services: FastAPI backend, React frontend (served via Nginx), and PostgreSQL. Exposed to alpha testers via Cloudflare Tunnel.

---

## Supported Platforms (Technical Details)

| Platform | Auth | API Style | Notes |
|----------|------|-----------|-------|
| **MFL** (MyFantasyLeague) | Cookie-based auth | REST, JSON via `JSON=1` param | Year-based API paths (e.g., `/2025/export`) |
| **Sleeper** | None required | Public read-only REST API | JSON native; no auth needed for read operations |

---

## Database Schema (SQLAlchemy Models)

| Table | Purpose |
|-------|---------|
| `users` | App user accounts |
| `platform_accounts` | Linked platform credentials (MFL cookie, Sleeper username) |
| `players` | Canonical player records with multi-platform IDs |
| `player_adp` | ADP data per player, source, format, and season |
| `leagues` | League metadata (name, platform, season, settings) |
| `user_leagues` | Junction: which users are in which leagues |
| `rosters` | Team rosters per league |
| `standings` | League standings and records |
| `matchups` | Weekly matchup pairings and results |
| `player_scores` | Actual player scoring data |
| `projected_scores` | Player projections |
| `transactions` | Trades, waivers, add/drops |
| `team_bye_weeks` | NFL bye week data per team per season (from ESPN Fantasy API) |
| `sync_log` | Sync history (timestamps, status, errors) |
