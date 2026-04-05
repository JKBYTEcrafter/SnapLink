"""
Celery tasks — consume analytics events and persist to PostgreSQL.
"""
import logging
from datetime import datetime, timezone

from celery import Task
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Analytics
from worker.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Synchronous SQLAlchemy engine for Celery worker (Celery is sync-based)
# ---------------------------------------------------------------------------

_SYNC_DB_URL = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

_sync_engine = create_engine(
    _SYNC_DB_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal = sessionmaker(bind=_sync_engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="worker.tasks.process_analytics_event",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_analytics_event(self: Task, event: dict) -> dict:
    """
    Celery task: persist a click analytics event to the PostgreSQL analytics table.

    Args:
        event: Dict with keys: short_code, ip_address, user_agent, device_type,
               browser, os, geo_country, geo_city, referer.

    Returns:
        Dict with the ID of the saved analytics row.
    """
    try:
        with SyncSessionLocal() as db:
            analytics = Analytics(
                short_code=event.get("short_code", ""),
                timestamp=datetime.now(tz=timezone.utc),
                ip_address=event.get("ip_address"),
                user_agent=event.get("user_agent"),
                device_type=event.get("device_type"),
                browser=event.get("browser"),
                os=event.get("os"),
                geo_country=event.get("geo_country"),
                geo_city=event.get("geo_city"),
                referer=event.get("referer"),
            )
            db.add(analytics)
            db.commit()
            db.refresh(analytics)
            logger.debug(
                "Analytics saved: id=%s short_code=%s",
                analytics.id,
                analytics.short_code,
            )
            return {"id": analytics.id, "short_code": analytics.short_code}

    except Exception as exc:
        logger.error("Analytics DB write failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
