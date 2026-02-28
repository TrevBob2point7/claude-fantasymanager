# Fantasy Manager

All-in-one fantasy football dashboard aggregating your leagues across MFL, Sleeper, and more. NFL only.

- [Product Spec](docs/PRODUCT.md) — vision, league types, scoring, data sources
- [Roadmap](docs/ROADMAP.md) — MVP checklist and future features
- [Architecture](docs/ARCHITECTURE.md) — tech stack decisions, patterns, database schema
- [Data Model](docs/DATA_MODEL.md) — complete database schema, enums, indexes, relationships
- [UI Specs](docs/UI.md) — page-by-page layout wireframes and behavior

---

## Project Structure

```
backend/
  app/
    api/            # FastAPI route handlers
    models/         # SQLAlchemy models
    schemas/        # Pydantic request/response schemas
    platforms/      # Adapter system (base class, mfl/, sleeper/)
    adp/            # ADP provider system (base class, providers, sync)
    sync/           # Sync engine, scheduler, player ID import
    auth/           # JWT auth (tokens, password hashing, dependencies)
    core/           # Config, database session, settings
  alembic/          # Database migrations

frontend/
  src/
    components/     # React components
    pages/          # Route-level page components
    hooks/          # Custom React hooks
    api/            # API client (fetch wrappers, types)
    context/        # Auth context, app state
  e2e/              # Playwright e2e tests

docker-compose.yml
```

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
