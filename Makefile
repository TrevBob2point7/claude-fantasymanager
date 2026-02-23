# Use docker compose v2 if available, fallback to docker-compose v1
DOCKER_COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

.PHONY: up down build logs migrate shell-backend dev-backend dev-frontend test test-backend test-frontend test-e2e

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

build:
	$(DOCKER_COMPOSE) build

logs:
	$(DOCKER_COMPOSE) logs -f

migrate:
	$(DOCKER_COMPOSE) exec backend alembic upgrade head

shell-backend:
	$(DOCKER_COMPOSE) exec backend bash

dev-backend:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

dev-frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest -v

test-frontend:
	cd frontend && npm test -- --run

test-e2e:
	cd frontend && npx playwright test
