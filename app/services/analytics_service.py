"""
Analytics event producer.
Pushes click events to the Celery task queue (Redis broker) asynchronously
so that analytics processing NEVER blocks the redirect response.
"""
import logging

from app.services.cache_service import get_redis

logger = logging.getLogger(__name__)

_ANALYTICS_QUEUE = "celery"  # default Celery queue name


async def push_analytics_event(event: dict) -> None:
    """
    Serialize and push an analytics event to the Celery Redis queue.

    The Celery worker (worker/tasks.py) picks this up and writes to DB.
    This is a fire-and-forget operation — failures are logged and swallowed
    to ensure zero latency impact on redirect.

    Args:
        event: Dict containing click metadata (ip, user_agent, short_code, etc.)
    """
    import json
    import uuid

    try:
        redis = get_redis()

        # Build a Celery-compatible task message
        task_id = str(uuid.uuid4())
        message = {
            "id": task_id,
            "task": "worker.tasks.process_analytics_event",
            "args": [event],
            "kwargs": {},
            "retries": 0,
            "eta": None,
            "expires": None,
            "utc": True,
            "callbacks": None,
            "errbacks": None,
            "timelimit": [None, None],
            "taskset": None,
            "chord": None,
        }

        # Wrap in Celery v2 protocol envelope
        envelope = {
            "body": json.dumps(message),
            "content-encoding": "utf-8",
            "content-type": "application/json",
            "headers": {},
            "properties": {
                "correlation_id": task_id,
                "reply_to": None,
                "delivery_mode": 2,
                "delivery_info": {
                    "exchange": "",
                    "routing_key": _ANALYTICS_QUEUE,
                },
                "body_encoding": "base64",
                "delivery_tag": task_id,
            },
        }

        await redis.lpush(_ANALYTICS_QUEUE, json.dumps(envelope))
        logger.debug("Analytics event queued: %s", event.get("short_code"))

    except Exception as exc:
        logger.warning("Failed to queue analytics event: %s", exc)
