"""
Analytics event writer — replaces the Redis/Celery queue approach.

Instead of pushing to a Redis queue for a Celery worker to consume,
we write analytics events directly to MongoDB in a fire-and-forget
asyncio background task. This is simpler, requires no extra process,
and is fast enough for this use case.
"""
import logging
from datetime import datetime, timezone

from app.database.database import get_motor_db

logger = logging.getLogger(__name__)


async def push_analytics_event(event: dict) -> None:
    """
    Persist a click analytics event directly to the MongoDB `analytics` collection.

    This is called inside an asyncio.ensure_future() in url_routes.py,
    so it runs as a fire-and-forget background coroutine and does NOT
    block the redirect response.

    Args:
        event: Dict containing click metadata (short_code, ip_address,
               user_agent, device_type, browser, os, geo_country, geo_city, referer).
    """
    try:
        db = get_motor_db()
        doc = {
            "short_code": event.get("short_code", ""),
            "timestamp": datetime.now(tz=timezone.utc),
            "ip_address": event.get("ip_address"),
            "user_agent": event.get("user_agent"),
            "device_type": event.get("device_type"),
            "browser": event.get("browser"),
            "os": event.get("os"),
            "geo_country": event.get("geo_country"),
            "geo_city": event.get("geo_city"),
            "referer": event.get("referer"),
        }
        await db.analytics.insert_one(doc)
        logger.debug("Analytics event saved for: %s", event.get("short_code"))
    except Exception as exc:
        logger.warning("Failed to save analytics event: %s", exc)
