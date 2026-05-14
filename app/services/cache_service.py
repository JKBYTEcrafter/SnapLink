"""
MongoDB-backed cache service — replaces the Redis cache_service.

Uses the `url_cache` collection with a TTL index on `expires_at`
(MongoDB automatically deletes expired documents).

Public API is identical to the old Redis version so no callers change.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database.database import get_motor_db

logger = logging.getLogger(__name__)
settings = get_settings()

_MISS_SENTINEL = "__MISS__"   # Negative caching sentinel


# ---------------------------------------------------------------------------
# Cache CRUD
# ---------------------------------------------------------------------------

async def get_cached_url(short_code: str) -> Optional[str]:
    """
    Look up a long URL from the MongoDB cache.

    Returns:
        - The cached long URL string on a hit.
        - None if not cached.
        - Raises CacheMissError for negatively-cached keys.
    """
    try:
        db: AsyncIOMotorDatabase = get_motor_db()
        doc = await db.url_cache.find_one({"short_code": short_code})
        if doc is None:
            return None
        value: str = doc["long_url"]
        if value == _MISS_SENTINEL:
            raise CacheMissError(f"short_code '{short_code}' is negatively cached")
        return value
    except CacheMissError:
        raise
    except Exception as exc:
        logger.warning("Cache GET error for '%s': %s", short_code, exc)
        return None


async def set_cached_url(
    short_code: str, long_url: str, ttl: int | None = None
) -> None:
    """Cache a short_code → long_url mapping with an optional TTL (seconds)."""
    try:
        db: AsyncIOMotorDatabase = get_motor_db()
        effective_ttl = ttl if ttl is not None else settings.cache_default_ttl
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=effective_ttl)
        await db.url_cache.update_one(
            {"short_code": short_code},
            {"$set": {"short_code": short_code, "long_url": long_url, "expires_at": expires_at}},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("Cache SET error for '%s': %s", short_code, exc)


async def set_negative_cache(short_code: str, ttl: int = 60) -> None:
    """Negatively cache a short_code to prevent repeated DB misses."""
    try:
        db: AsyncIOMotorDatabase = get_motor_db()
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)
        await db.url_cache.update_one(
            {"short_code": short_code},
            {"$set": {"short_code": short_code, "long_url": _MISS_SENTINEL, "expires_at": expires_at}},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("Cache negative-SET error for '%s': %s", short_code, exc)


async def invalidate_cache(short_code: str) -> None:
    """Remove a cached entry (e.g., when a URL is deleted or updated)."""
    try:
        db: AsyncIOMotorDatabase = get_motor_db()
        await db.url_cache.delete_one({"short_code": short_code})
    except Exception as exc:
        logger.warning("Cache DELETE error for '%s': %s", short_code, exc)


# ---------------------------------------------------------------------------
# Legacy Redis init/close stubs (no-ops — kept so main.py import doesn't break)
# ---------------------------------------------------------------------------

def init_redis(url: str | None = None) -> None:  # noqa: ARG001
    """No-op: Redis removed. MongoDB cache is initialised via database.init_db()."""
    pass


async def close_redis() -> None:
    """No-op: Redis removed."""
    pass


class CacheMissError(Exception):
    """Raised when a negatively-cached key is accessed."""
