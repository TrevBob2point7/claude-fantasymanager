# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Description

An all-in-one fantasy football manager application — React SPA frontend + FastAPI backend + PostgreSQL, all running in Docker Compose.

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
