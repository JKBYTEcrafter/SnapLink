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

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017/snaplink"

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
