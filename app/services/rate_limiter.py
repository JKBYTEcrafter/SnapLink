"""
Rate limiter using Redis Sliding Window algorithm.
Each IP gets a sorted set keyed by timestamp; old entries are pruned per request.
"""
import logging
import time

from fastapi import HTTPException, Request, status

from app.config import get_settings
from app.services.cache_service import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()

_RATE_PREFIX = "rl:"


class RateLimiter:
    """
    FastAPI dependency implementing a per-IP sliding window rate limiter.

    Usage:
        @router.get("/endpoint", dependencies=[Depends(RateLimiter())])
    """

    def __init__(
        self,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self.max_requests = max_requests or settings.rate_limit_max_requests
        self.window_seconds = window_seconds or settings.rate_limit_window_seconds

    async def __call__(self, request: Request) -> None:
        client_ip = self._get_client_ip(request)
        key = f"{_RATE_PREFIX}{client_ip}"

        try:
            redis = get_redis()
            now = time.time()
            window_start = now - self.window_seconds

            pipe = redis.pipeline()
            # Remove events older than the sliding window
            pipe.zremrangebyscore(key, "-inf", window_start)
            # Count remaining events in window
            pipe.zcard(key)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Set expiry on the key
            pipe.expire(key, self.window_seconds + 1)
            results = await pipe.execute()

            current_count: int = results[1]

            if current_count >= self.max_requests:
                retry_after = int(self.window_seconds)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={"Retry-After": str(retry_after)},
                )
        except HTTPException:
            raise
        except Exception as exc:
            # On Redis failure, fail open (allow request) to avoid outage
            logger.warning("Rate limiter Redis error for IP %s: %s", client_ip, exc)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the real client IP, respecting X-Forwarded-For."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
