"""
MongoDB async client using Motor.
Replaces the SQLAlchemy/asyncpg setup.
"""
import logging
from typing import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level Motor client (initialised during app startup)
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def init_db() -> None:
    """Initialise the Motor client. Call once at startup."""
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongodb_url)
    # Parse the database name from the URI, falling back to "snaplink"
    db_name = _client.get_default_database().name if "/" in settings.mongodb_url.split("?")[0].rsplit("/", 1)[-1] else "snaplink"
    _db = _client[db_name]
    logger.info("MongoDB client initialised (db=%s)", db_name)


def get_motor_db() -> AsyncIOMotorDatabase:
    """Return the Motor database (must call init_db first)."""
    if _db is None:
        raise RuntimeError("MongoDB not initialised — call init_db() at startup")
    return _db


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """FastAPI dependency that yields the Motor database object."""
    yield get_motor_db()


async def close_db() -> None:
    """Close the Motor client connection pool."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed")


async def create_indexes() -> None:
    """
    Create all required MongoDB indexes on startup.
    Uses `background=True` so the app doesn't stall on large collections.
    """
    db = get_motor_db()

    # --- urls collection ---
    await db.urls.create_index("short_code", unique=True, background=True)
    await db.urls.create_index("user_id", background=True)
    await db.urls.create_index([("created_at", -1)], background=True)

    # --- users collection ---
    await db.users.create_index("email", unique=True, background=True)

    # --- analytics collection ---
    await db.analytics.create_index(
        [("short_code", 1), ("timestamp", -1)], background=True
    )

    # --- password_reset_otps collection ---
    await db.password_reset_otps.create_index("email", background=True)
    # Auto-expire OTP documents 1 hour after expires_at
    await db.password_reset_otps.create_index(
        "expires_at", expireAfterSeconds=3600, background=True
    )

    # --- url_cache collection (TTL-based Redis replacement) ---
    await db.url_cache.create_index("short_code", unique=True, background=True)
    await db.url_cache.create_index(
        "expires_at", expireAfterSeconds=0, background=True
    )

    # --- rate_limits collection ---
    await db.rate_limits.create_index("key", unique=True, background=True)
    await db.rate_limits.create_index(
        "reset_at", expireAfterSeconds=0, background=True
    )

    logger.info("MongoDB indexes ensured")
