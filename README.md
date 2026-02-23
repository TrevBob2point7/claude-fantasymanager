# Fantasy Manager

All-in-one fantasy football dashboard aggregating your leagues across MFL, Sleeper, and more. NFL only.

---

## Tech Stack Decisions

Each layer lists 2-3 options with pros/cons. Once a choice is made, update the **Decision** line.

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

## Supported Platforms

| Platform | Auth | API Style | Notes |
|----------|------|-----------|-------|
| **MFL** (MyFantasyLeague) | Cookie-based auth | REST, JSON via `JSON=1` param | Year-based API paths (e.g., `/2025/export`) |
| **Sleeper** | None required | Public read-only REST API | JSON native; no auth needed for read operations |

Designed for extensibility — new platforms are added via an adapter pattern (see Architecture below).

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
- Scheduled background sync with configurable per-data-type frequency (APScheduler or similar)
- Manual "Sync Now" endpoint triggered from the UI
- Sync log tracking (last sync time, status, errors per data type)

### Database as Cache Layer
PostgreSQL via SQLAlchemy (async). The app reads exclusively from the local database. External platform APIs are only called during sync operations. This provides fast page loads, offline resilience, and reduces API rate limit pressure.

### Deployment
Docker Compose on home server with three services: FastAPI backend, React frontend (served via Nginx), and PostgreSQL. Exposed to alpha testers via Cloudflare Tunnel.

---

## Data Scope

- Rosters & teams
- League standings & matchups
- Player stats & live scoring
- Projections
- Transactions (trades, waivers, add/drops)

---

## Database Schema (SQLAlchemy Models)

| Table | Purpose |
|-------|---------|
| `users` | App user accounts |
| `platform_accounts` | Linked platform credentials (MFL cookie, Sleeper username) |
| `players` | Canonical player records with multi-platform IDs |
| `leagues` | League metadata (name, platform, season, settings) |
| `user_leagues` | Junction: which users are in which leagues |
| `rosters` | Team rosters per league |
| `standings` | League standings and records |
| `matchups` | Weekly matchup pairings and results |
| `player_scores` | Actual player scoring data |
| `projected_scores` | Player projections |
| `transactions` | Trades, waivers, add/drops |
| `sync_log` | Sync history (timestamps, status, errors) |

---

## Project Structure

```
backend/
  app/
    api/            # FastAPI route handlers
    models/         # SQLAlchemy models
    schemas/        # Pydantic request/response schemas
    platforms/      # Adapter system (base class, mfl/, sleeper/)
    sync/           # Sync engine, scheduler, player ID import
    auth/           # JWT auth (tokens, password hashing, dependencies)
    core/           # Config, database session, settings
  alembic/          # Database migrations
  requirements.txt

frontend/
  src/
    components/     # React components
    pages/          # Route-level page components
    hooks/          # Custom React hooks
    api/            # API client (fetch wrappers, types)
    context/        # Auth context, app state
  package.json

docker-compose.yml
```

---

## MVP (v1) Features

- [ ] User registration and login
- [ ] Link Sleeper and MFL accounts
- [ ] Auto-discover leagues for a season
- [ ] Sync rosters, standings, matchups, scores, and transactions
- [ ] Unified "My Teams" dashboard
- [ ] Per-league detail view
- [ ] Manual and scheduled background sync
- [ ] Mobile-responsive UI

---

## Roadmap (v2+)

- Player comparison tool
- Trade analyzer
- Waiver wire recommendations
- Weekly recap / power rankings
- Push notifications
- Additional platforms (ESPN, Yahoo, Fleaflicker)
- League history / year-over-year analysis
- Draft assistant
- AI-powered insights (start/sit, trade suggestions)

---

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- For local dev (outside Docker): Python 3.12+, Node 22+, [uv](https://docs.astral.sh/uv/)

### Installation

```bash
git clone https://github.com/TrevBob2point7/claude-fantasymanager.git
cd claude-fantasymanager
cp .env.example .env
```

### Quick Start (Docker Compose)

```bash
make build    # Build backend + frontend images
make up       # Start all services (PostgreSQL, FastAPI, React/Nginx)
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- Health check: http://localhost:3000/api/health

### Local Development

Run the database in Docker, backend and frontend locally:

```bash
make up                # Start PostgreSQL (and other services)
make dev-backend       # FastAPI on http://localhost:8000 (in a separate terminal)
make dev-frontend      # Vite on http://localhost:5173 (in a separate terminal)
```

### Database Migrations

```bash
make migrate           # Run pending Alembic migrations
```

### Running Tests

```bash
make test              # Backend (pytest) + frontend (vitest)
make test-backend      # Backend only
make test-frontend     # Frontend only
make test-e2e          # Playwright end-to-end tests
```

### Linting & Formatting

```bash
make lint              # Ruff (backend) + ESLint (frontend)
make format            # Ruff format (backend) + Prettier (frontend)
make typecheck         # TypeScript type checking (frontend)
```
