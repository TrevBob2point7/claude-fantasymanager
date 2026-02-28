import os
from collections.abc import AsyncGenerator

# IMPORTANT: Set naming convention on Base.metadata BEFORE importing models,
# so that create_all() generates constraint names matching what the sync engine
# references (e.g. uq_leagues_platform_type_...).
from app.core.database import Base

Base.metadata.naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

import app.models  # noqa: F401, E402 — register all models with Base.metadata
import pytest_asyncio  # noqa: E402
from app.api.auth import router as auth_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.api.leagues import router as leagues_router  # noqa: E402
from app.api.platforms import router as platforms_router  # noqa: E402
from app.api.sync import router as sync_router  # noqa: E402
from app.auth import create_access_token, hash_password  # noqa: E402
from app.auth.dependencies import get_current_user  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.models.user import User  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://fantasy:fantasy_dev_password@db:5432/fantasy_manager_test",
)


def create_test_app() -> FastAPI:
    """Create a FastAPI app without the production lifespan/scheduler."""
    test_app = FastAPI(title="Fantasy Manager API - Test")
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(health_router)
    test_app.include_router(auth_router)
    test_app.include_router(platforms_router)
    test_app.include_router(leagues_router)
    test_app.include_router(sync_router)
    return test_app


# Create a single test app instance used by all tests
test_app = create_test_app()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """Create and dispose the test engine once per session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_session_factory(test_engine):
    """Session factory bound to the test engine."""
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async session for direct DB access in tests."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def cleanup_tables(test_engine):
    """Truncate all tables after each test for isolation."""
    yield
    async with test_engine.begin() as conn:
        table_names = [t.name for t in reversed(Base.metadata.sorted_tables)]
        for table in table_names:
            await conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))


@pytest_asyncio.fixture(loop_scope="session")
async def client(test_session_factory) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB dependency overridden to use test database."""

    async def _override_get_db():
        async with test_session_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    test_app.dependency_overrides.clear()


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_client(
    test_session_factory,
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with a pre-created user and auth header set."""
    async with test_session_factory() as session:
        user = User(
            email="testuser@example.com",
            hashed_password=hash_password("testpassword123"),
            display_name="Test User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})

    async def _override_get_db():
        async with test_session_factory() as session:
            yield session

    async def _override_get_current_user():
        return user

    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_current_user] = _override_get_current_user
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        ac.test_user = user  # type: ignore[attr-defined]
        yield ac
    test_app.dependency_overrides.clear()
