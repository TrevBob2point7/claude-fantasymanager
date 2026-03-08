"""Conftest for unit tests that don't require a database connection.

Overrides the autouse ``cleanup_tables`` fixture from the parent conftest
so that unit tests can run without a PostgreSQL database.
"""

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def cleanup_tables():
    """No-op override — unit tests don't use the database."""
    yield
