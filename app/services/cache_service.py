"""
Redis cache service — cache-aside pattern.
"""
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Module-level Redis pool (initialised during app startup)
_redis: aioredis.Redis | None = None

_SHORT_CODE_PREFIX = "url:"
_MISS_SENTINEL = "__MISS__"   # Negative caching sentinel


def init_redis(url: str | None = None) -> None:
    """Initialise the module-level Redis client. Call once at startup."""
    global _redis
    _redis = aioredis.from_url(
        url or settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )


def get_redis() -> aioredis.Redis:
    """Return the Redis client (must call init_redis first)."""
    if _redis is None:
        raise RuntimeError("Redis not initialised — call init_redis() at startup")
    return _redis


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    if _redis is not None:
        await _redis.aclose()


async def get_cached_url(short_code: str) -> Optional[str]:
    """
    Look up a long URL from Redis cache.

    Returns:
        - The cached long URL string on a cache hit.
        - None if the key is absent.
        - Raises CacheMissError for keys cached as negative (MISS_SENTINEL).
    """
    try:
        value = await get_redis().get(f"{_SHORT_CODE_PREFIX}{short_code}")
        if value is None:
            return None
        if value == _MISS_SENTINEL:
            raise CacheMissError(f"short_code '{short_code}' is negatively cached")
        return value
    except CacheMissError:
        raise
    except Exception as exc:
        logger.warning("Redis GET error for '%s': %s", short_code, exc)
        return None


async def set_cached_url(short_code: str, long_url: str, ttl: int | None = None) -> None:
    """Cache a short_code → long_url mapping."""
    try:
        key = f"{_SHORT_CODE_PREFIX}{short_code}"
        effective_ttl = ttl if ttl is not None else settings.cache_default_ttl
        await get_redis().setex(key, effective_ttl, long_url)
    except Exception as exc:
        logger.warning("Redis SET error for '%s': %s", short_code, exc)


async def set_negative_cache(short_code: str, ttl: int = 60) -> None:
    """Negatively cache a short_code to avoid repeated DB misses."""
    try:
        key = f"{_SHORT_CODE_PREFIX}{short_code}"
        await get_redis().setex(key, ttl, _MISS_SENTINEL)
    except Exception as exc:
        logger.warning("Redis negative-cache SET error for '%s': %s", short_code, exc)


async def invalidate_cache(short_code: str) -> None:
    """Remove a cached entry (e.g., when a URL is deleted or expires)."""
    try:
        await get_redis().delete(f"{_SHORT_CODE_PREFIX}{short_code}")
    except Exception as exc:
        logger.warning("Redis DEL error for '%s': %s", short_code, exc)


class CacheMissError(Exception):
    """Raised when a negatively-cached key is accessed."""
