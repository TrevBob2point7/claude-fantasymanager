# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Description

An all-in-one fantasy football manager application — React SPA frontend + FastAPI backend + PostgreSQL, all running in Docker Compose.

## Product Spec

See [docs/PRODUCT.md](docs/PRODUCT.md) for product vision, supported league types, scoring formats, data source decisions, and known gaps.

## Data Model

See [docs/DATA_MODEL.md](docs/DATA_MODEL.md) for the complete database schema, enums, indexes, and relationships. **This document must be kept in sync with the codebase** — update it whenever SQLAlchemy models, enums, or migrations change.

## Tech Stack

- **Frontend:** React 19, TypeScript, Vite 6
- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic
- **Database:** PostgreSQL 16
- **Auth:** Custom JWT (python-jose + passlib)
- **Package Management:** uv (backend), npm (frontend)
- **Containerization:** Docker Compose

## Development Commands

```bash
# Docker Compose
make up          # Start all services (detached)
make down        # Stop all services
make build       # Rebuild images
make logs        # Tail logs

# Local dev (outside Docker)
make dev-backend   # Run FastAPI with hot-reload
make dev-frontend  # Run Vite dev server

# Database
make migrate       # Run Alembic migrations

# Testing
make test-backend   # pytest (backend)
make test-frontend  # vitest (frontend)
make test-e2e       # Playwright e2e tests
make test           # Run backend + frontend tests

# Linting & Formatting
make lint            # ruff check (backend) + eslint (frontend)
make format          # ruff format (backend) + prettier (frontend)
make typecheck       # tsc --noEmit (frontend)
```

## Project Structure

```
backend/
  app/
    api/         # FastAPI route handlers
    models/      # SQLAlchemy models
    schemas/     # Pydantic request/response schemas
    platforms/   # Platform adapter system
    sync/        # Sync engine
    auth/        # JWT auth
    core/        # Config, database session
  alembic/       # Database migrations
  tests/         # pytest tests

frontend/
  src/
    components/  # React components
    pages/       # Route-level pages
    hooks/       # Custom React hooks
    api/         # API client
    context/     # React context providers
  e2e/           # Playwright e2e tests
```

## Key Patterns

- **Backend config:** `pydantic-settings` loads from env vars (see `.env.example`)
- **Database:** Async SQLAlchemy with `asyncpg` driver. Use `get_db` dependency for sessions.
- **Migrations:** Alembic with async support. Run `make migrate` after model changes.
- **Frontend proxy:** Vite dev server proxies `/api` to `http://localhost:8000`. Nginx does the same in production.
- **Testing:** Backend uses `pytest-asyncio` with `httpx.AsyncClient`. Frontend uses `vitest` + `@testing-library/react`.
- **Linting:** Backend uses Ruff (linting + formatting). Frontend uses ESLint 9 (flat config, typescript-eslint) + Prettier. Pre-commit hook via husky + lint-staged runs on staged files.

## Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/). All commit messages must follow this format:

```
<type>(<scope>): <short summary>

<optional body>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`

**Scopes:** `backend`, `frontend`, `db`, `infra`, `deps` (or omit for cross-cutting changes)

**Examples:**
```
feat(backend): add user registration endpoint
fix(frontend): prevent double-submit on login form
refactor(db): normalize league settings into separate table
test(backend): add integration tests for sync engine
build(infra): add health check to Docker Compose db service
chore(deps): bump fastapi to 0.115
docs: update README getting started section
```
