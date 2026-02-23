# Plan: Scaffold Fantasy Manager Project

## Context
The repo has only README.md, CLAUDE.md, and _plans/ — no code. The tech stack has been decided (React SPA + FastAPI + PostgreSQL/SQLAlchemy + Custom JWT + Docker Compose). The goal is to create a minimal but functional skeleton so that `docker compose up` produces a running system: PostgreSQL, FastAPI with a `/health` endpoint, and a React frontend showing a landing page that confirms backend connectivity.

## Files to Create (~36 files)

### Phase 1: Root-Level Config

| File | Purpose |
|------|---------|
| `.gitignore` | Python + Node + Docker + IDE ignores |
| `.env.example` | Template for DB, auth, and CORS env vars |
| `docker-compose.yml` | 3 services: `db` (postgres:16-alpine), `backend` (FastAPI), `frontend` (React/Nginx) |
| `Makefile` | Convenience commands: `up`, `down`, `build`, `logs`, `migrate`, `shell-backend` |

### Phase 2: Backend (`backend/`)

| File | Purpose |
|------|---------|
| `pyproject.toml` | Project metadata + dependencies managed by **uv** (fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, python-jose, passlib, pydantic-settings, httpx) |
| `Dockerfile` | python:3.12-slim, installs **uv** via pip, uses `uv sync` to install deps, runs uvicorn with --reload |
| `.dockerignore` | Exclude __pycache__, .venv, .env |
| `app/__init__.py` | Package marker |
| `app/core/__init__.py` | Package marker |
| `app/core/config.py` | `pydantic-settings` Settings class loading DATABASE_URL, SECRET_KEY, CORS origins from env |
| `app/core/database.py` | Async SQLAlchemy engine, session factory, `DeclarativeBase`, `get_db` dependency |
| `app/api/__init__.py` | Package marker |
| `app/api/health.py` | `GET /health` — verifies DB connection, returns `{"status": "healthy", "database": "connected"}` |
| `app/main.py` | FastAPI app with lifespan (DB verify on startup, dispose on shutdown), CORS middleware, health router |
| `app/models/__init__.py` | Empty (placeholder for SQLAlchemy models) |
| `app/schemas/__init__.py` | Empty (placeholder for Pydantic schemas) |
| `app/platforms/__init__.py` | Empty (placeholder for adapter system) |
| `app/sync/__init__.py` | Empty (placeholder for sync engine) |
| `app/auth/__init__.py` | Empty (placeholder for JWT auth) |

### Phase 3: Alembic (`backend/alembic/`)

| File | Purpose |
|------|---------|
| `alembic.ini` | Standard config, URL overridden programmatically in env.py |
| `alembic/env.py` | Async-aware migration runner, imports Base metadata for autogenerate |
| `alembic/script.py.mako` | Standard migration template |
| `alembic/versions/.gitkeep` | Empty dir for future migrations |

### Phase 4: Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `package.json` | react 19, react-dom 19, vite 6, @vitejs/plugin-react, typescript 5.7 |
| `tsconfig.json` | Strict TS config, ES2020 target, react-jsx |
| `tsconfig.app.json` | Extends base, composite for project references |
| `tsconfig.node.json` | Extends base, for vite.config.ts |
| `vite.config.ts` | React plugin, dev proxy: `/api` → `http://localhost:8000` (strips prefix) |
| `index.html` | Minimal HTML shell, mounts `#root`, loads `/src/main.tsx` |
| `src/vite-env.d.ts` | Vite client type reference |
| `src/main.tsx` | React 19 createRoot, renders `<App />` in StrictMode |
| `src/App.tsx` | Fetches `/api/health`, shows "Fantasy Manager" heading + backend status (green/red) |
| `Dockerfile` | Multi-stage: node:22-alpine builds, nginx:alpine serves dist |
| `nginx.conf` | Proxies `/api/` to `http://backend:8000/`, SPA fallback for all other routes |
| `.dockerignore` | Exclude node_modules, dist, .env |
| `src/components/.gitkeep` | Placeholder dir |
| `src/pages/.gitkeep` | Placeholder dir |
| `src/hooks/.gitkeep` | Placeholder dir |
| `src/api/.gitkeep` | Placeholder dir |
| `src/context/.gitkeep` | Placeholder dir |

## Agent Workstreams (post-scaffold)

Four agents, each owning a distinct area. Can be parallel Claude Code sessions or sequential focus areas.

| Agent | Owns | Responsibilities |
|-------|------|-----------------|
| **Backend API** | `backend/app/api/`, `models/`, `schemas/`, `auth/` | SQLAlchemy models, Pydantic schemas, FastAPI routes, JWT auth. Largest surface area — defines the API contracts the frontend builds against. |
| **Frontend UI** | `frontend/` | React components, pages, API client, auth context, state management. Starts once the first API endpoints are available. |
| **Platform + Sync** | `backend/app/platforms/`, `backend/app/sync/` | MFL and Sleeper adapters, data normalization, DynastyProcess player import, background sync scheduler. Most domain-specific work. |
| **Infrastructure** | `docker-compose.yml`, `alembic/`, CI/CD, deployment | Migrations, Docker config, Cloudflare Tunnel, deploy scripts. Lighter workload but keeps others unblocked. |

**Build order:**
1. **Infra** scaffolds first (this plan)
2. **Backend API** builds models + auth + initial endpoints
3. **Platform/Sync** builds adapters in parallel once the model layer exists
4. **Frontend UI** starts once the first API endpoints are available

## Not in Scope (post-scaffold)

- **DynastyProcess player ID import**: The `players` table and `sync/` module are placeholders in this scaffold. After scaffolding, one of the first features will be importing the [DynastyProcess CSV](https://github.com/dynastyprocess/data) into the `players` table. This CSV maps ~11,600+ players across platforms (`mfl_id`, `sleeper_id`, `espn_id`, etc.) and is what enables a unified view — when MFL says player `13604` and Sleeper says player `4034`, this mapping tells us they're the same person.

## Key Design Decisions

- **uv for Python dependency management**: Fast dependency resolution (10-100x faster than pip), reproducible builds via `uv.lock`, `pyproject.toml`-based (modern Python standard), and clean Docker integration via `uv sync --frozen`. Replaces pip + requirements.txt.
- **`/api/` proxy pattern**: Frontend fetches `/api/health`, both Vite (dev) and Nginx (prod) strip the prefix and forward to FastAPI's `/health`. Backend routes stay clean without prefix awareness.
- **Async SQLAlchemy from the start**: `env.py` is hand-written async (not from `alembic init`) so migrations work with asyncpg.
- **`pydantic-settings`** for config instead of python-dotenv — typed, validated, idiomatic for FastAPI.
- **No React Router yet** — added when multi-page features arrive, not dead code now.
- **`--reload` in backend Dockerfile** — acceptable for dev/alpha; remove for production.

## Verification
1. `docker compose build` — both Dockerfiles build successfully
2. `docker compose up` — all 3 services start, DB healthcheck passes
3. `curl http://localhost:8000/health` → `{"status":"healthy","database":"connected"}`
4. `http://localhost:3000` → React app with green "Backend: healthy | DB: connected" message
