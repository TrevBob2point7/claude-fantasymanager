from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.health import router as health_router
from app.core.config import settings
from app.core.database import get_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient


def create_test_app() -> FastAPI:
    """Create a FastAPI app without the DB-dependent lifespan."""
    test_app = FastAPI(title="Fantasy Manager API - Test")
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(health_router)
    return test_app


@pytest.fixture
def mock_db_session():
    """A mock AsyncSession whose .execute() succeeds."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    return session


@pytest.fixture
async def client(mock_db_session):
    test_app = create_test_app()
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    test_app.dependency_overrides.clear()
