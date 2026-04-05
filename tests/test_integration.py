"""
Integration tests — require real PostgreSQL and Redis (via Docker or local services).

Run with:
    docker-compose up -d postgres redis
    pytest tests/test_integration.py -v
"""
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.database import Base, get_db
from app.main import app
from app.services import cache_service

# Use real services from environment (defaults match docker-compose)
_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/urlshortener_test",
)
_TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="module")
async def integration_engine():
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def integration_client(integration_engine):
    import redis.asyncio as aioredis

    session_factory = async_sessionmaker(
        bind=integration_engine, class_=AsyncSession, expire_on_commit=False
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

    redis_client = aioredis.from_url(_TEST_REDIS_URL, decode_responses=True)
    cache_service._redis = redis_client  # type: ignore[assignment]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    await redis_client.flushdb()  # clean up test keys
    await redis_client.aclose()
    app.dependency_overrides.clear()
    cache_service._redis = None


@pytest.mark.asyncio
class TestIntegrationFullFlow:
    async def test_shorten_and_redirect_pipeline(self, integration_client):
        """Full pipeline: shorten → cache warms → redirect from cache."""
        # Shorten
        create_resp = await integration_client.post(
            "/shorten", json={"long_url": "https://www.python.org"}
        )
        assert create_resp.status_code == 201
        short_code = create_resp.json()["short_code"]

        # First redirect — hits PostgreSQL (cache miss on fresh DB)
        r1 = await integration_client.get(f"/{short_code}", follow_redirects=False)
        assert r1.status_code == 302

        # Second redirect — should come from Redis cache
        r2 = await integration_client.get(f"/{short_code}", follow_redirects=False)
        assert r2.status_code == 302
        assert r2.headers["location"] == "https://www.python.org"

    async def test_analytics_after_clicks(self, integration_client):
        """Analytics total_clicks increments with each redirect."""
        create_resp = await integration_client.post(
            "/shorten", json={"long_url": "https://www.github.com"}
        )
        short_code = create_resp.json()["short_code"]

        # Simulate 3 clicks
        for _ in range(3):
            await integration_client.get(f"/{short_code}", follow_redirects=False)

        analytics = await integration_client.get(f"/analytics/{short_code}")
        assert analytics.status_code == 200
        # click_count should be at least 3
        assert analytics.json()["total_clicks"] >= 3

    async def test_redis_cache_hit(self, integration_client):
        """Verify the cache entry is populated after first resolution."""
        import redis.asyncio as aioredis

        create_resp = await integration_client.post(
            "/shorten", json={"long_url": "https://www.redis.io"}
        )
        short_code = create_resp.json()["short_code"]

        # Trigger resolution to warm cache
        await integration_client.get(f"/{short_code}", follow_redirects=False)

        # Verify key is in Redis
        redis = aioredis.from_url(_TEST_REDIS_URL, decode_responses=True)
        cached = await redis.get(f"url:{short_code}")
        assert cached == "https://www.redis.io"
        await redis.aclose()

    async def test_expired_url_returns_404(self, integration_client):
        """Expired links must not redirect."""
        from datetime import datetime, timedelta, timezone

        expiry = (datetime.now(tz=timezone.utc) - timedelta(seconds=1)).isoformat()
        create_resp = await integration_client.post(
            "/shorten",
            json={"long_url": "https://www.expired-example.com", "expiry_date": expiry},
        )
        short_code = create_resp.json()["short_code"]

        response = await integration_client.get(f"/{short_code}", follow_redirects=False)
        assert response.status_code == 404
        assert "expired" in response.json()["detail"].lower()
