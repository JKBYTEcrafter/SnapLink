"""
pytest configuration and shared fixtures.
"""
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.database import Base, get_db
from app.main import app
from app.services import cache_service

# Use SQLite for tests (no Docker required for unit/API tests)
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def mock_redis():
    """Mock Redis client that behaves like an in-memory dict."""
    store: dict = {}
    zsets: dict = {}

    redis_mock = AsyncMock()

    async def get(key):
        return store.get(key)

    async def setex(key, ttl, value):
        store[key] = value

    async def delete(key):
        store.pop(key, None)

    class MockPipeline:
        def __init__(self):
            self._commands = []

        def zremrangebyscore(self, *args):
            self._commands.append(("zrem", args))
            return self

        def zcard(self, key):
            self._commands.append(("zcard", key))
            return self

        def zadd(self, *args):
            self._commands.append(("zadd", args))
            return self

        def expire(self, *args):
            self._commands.append(("expire", args))
            return self

        async def execute(self):
            return [None, 0, None, None]  # 0 requests in window → not rate limited

    redis_mock.get = get
    redis_mock.setex = setex
    redis_mock.delete = delete
    redis_mock.pipeline = MockPipeline

    return redis_mock


@pytest_asyncio.fixture(scope="function")
async def client(test_engine, mock_redis):
    """Async HTTP test client with DB and Redis overrides."""

    # Override DB
    session_factory = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    # Override Redis
    cache_service._redis = mock_redis  # type: ignore[assignment]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    cache_service._redis = None
