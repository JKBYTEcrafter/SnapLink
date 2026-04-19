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
        extra="ignore",
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

    @property
    def validated_redis_url(self) -> str:
        """Ensure the Redis URL has the correct scheme."""
        url = self.redis_url
        if not url.startswith(("redis://", "rediss://", "unix://")):
            # Fallback to local if someone passes an empty string by accident in env vars
            if not url.strip():
                return "redis://localhost:6379/0"
            raise ValueError(f"Invalid REDIS_URL format. Must start with redis:// or rediss://. Got: '{url}'")
        return url

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
