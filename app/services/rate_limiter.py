"""
Rate limiter using MongoDB — sliding window algorithm.
Replaces the Redis sorted-set based implementation.

Uses a `rate_limits` collection where each document holds a list of
request timestamps for a given key (IP address). Old timestamps outside
the window are purged on each request.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status

from app.config import get_settings
from app.database.database import get_motor_db

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimiter:
    """
    FastAPI dependency implementing a per-IP sliding window rate limiter
    backed by MongoDB.

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
        key = f"rl:{client_ip}"

        try:
            db = get_motor_db()
            now = time.time()
            window_start = now - self.window_seconds
            reset_at = datetime.now(tz=timezone.utc) + timedelta(
                seconds=self.window_seconds + 1
            )

            # Atomically:
            # 1. Pull timestamps older than the window
            # 2. Push the current timestamp
            # 3. Set the TTL reset_at field
            result = await db.rate_limits.find_one_and_update(
                {"key": key},
                {
                    "$pull": {"timestamps": {"$lt": window_start}},
                    "$push": {"timestamps": now},
                    "$set": {"reset_at": reset_at},
                },
                upsert=True,
                return_document=True,  # type: ignore[call-arg]
            )

            # Count timestamps within window after the update
            timestamps = result.get("timestamps", []) if result else []
            # Filter again client-side since $pull runs before $push in same op
            current_count = sum(1 for ts in timestamps if ts >= window_start)
            # +1 for the push we just added
            current_count += 1

            if current_count > self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {self.window_seconds} seconds.",
                    headers={"Retry-After": str(self.window_seconds)},
                )

        except HTTPException:
            raise
        except Exception as exc:
            # On DB failure, fail open (allow request) to avoid outage
            logger.warning("Rate limiter DB error for IP %s: %s", client_ip, exc)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the real client IP, respecting X-Forwarded-For."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"
