"""
Application configuration using pydantic-settings.
All settings are loaded from environment variables / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # General
    app_name: str = "URL Shortener"
    base_url: str = "http://localhost:8000"
    secret_key: str = "change-me-in-production"
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/urlshortener"

    @property
    def async_database_url(self) -> str:
        """Convert database URL to async format for SQLAlchemy."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Rate Limiting
    rate_limit_max_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Cache
    cache_default_ttl: int = 3600  # seconds

    # Snowflake ID
    machine_id: int = 1


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
