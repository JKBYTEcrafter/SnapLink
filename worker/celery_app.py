"""
Celery application configuration.
"""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "url_shortener_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Performance
    worker_prefetch_multiplier=4,
    task_compression="gzip",
    # Result expiry
    result_expires=3600,
    # Retry policy for DB writes
    task_max_retries=3,
    task_default_retry_delay=5,  # seconds
)
