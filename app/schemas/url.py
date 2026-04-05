"""
Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ShortenRequest(BaseModel):
    long_url: str
    custom_alias: Optional[str] = None
    expiry_date: Optional[datetime] = None

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) < 3 or len(v) > 20:
            raise ValueError("Custom alias must be between 3 and 20 characters.")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Custom alias may only contain letters, digits, hyphens, and underscores.")
        return v

    @field_validator("long_url")
    @classmethod
    def validate_long_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("long_url must not be empty.")
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "long_url": "https://www.example.com/some/very/long/path?query=1",
                    "custom_alias": "my-link",
                    "expiry_date": None,
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ShortenResponse(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    created_at: datetime
    expiry_date: Optional[datetime] = None
    qr_url: str

    model_config = {"from_attributes": True}


class AnalyticsClickEvent(BaseModel):
    timestamp: Optional[str] = None
    ip: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None


class CountryCount(BaseModel):
    country: Optional[str] = None
    clicks: int


class DeviceCount(BaseModel):
    device: Optional[str] = None
    clicks: int


class AnalyticsResponse(BaseModel):
    short_code: str
    long_url: str
    total_clicks: int
    created_at: Optional[str] = None
    expiry_date: Optional[str] = None
    by_country: list[CountryCount]
    by_device: list[DeviceCount]
    recent_clicks: list[AnalyticsClickEvent]


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Bulk shortening schemas
# ---------------------------------------------------------------------------

class BulkShortenRequest(BaseModel):
    urls: list[ShortenRequest]

    @field_validator("urls")
    @classmethod
    def validate_urls_count(cls, v: list) -> list:
        if len(v) == 0:
            raise ValueError("At least one URL is required.")
        if len(v) > 50:
            raise ValueError("Maximum 50 URLs per bulk request.")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "urls": [
                        {"long_url": "https://www.example.com/page1"},
                        {"long_url": "https://www.example.com/page2", "custom_alias": "page2"},
                    ]
                }
            ]
        }
    }


class BulkShortenResultItem(BaseModel):
    index: int
    success: bool
    data: Optional[ShortenResponse] = None
    error: Optional[str] = None


class BulkShortenResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BulkShortenResultItem]


# ---------------------------------------------------------------------------
# Link management / editor schemas
# ---------------------------------------------------------------------------

class UpdateLinkRequest(BaseModel):
    long_url: Optional[str] = None
    custom_alias: Optional[str] = None
    expiry_date: Optional[datetime] = None

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) < 3 or len(v) > 20:
            raise ValueError("Custom alias must be between 3 and 20 characters.")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Custom alias may only contain letters, digits, hyphens, and underscores.")
        return v

    @field_validator("long_url")
    @classmethod
    def validate_long_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("long_url must not be empty.")
        return v


class LinkListItem(BaseModel):
    short_code: str
    short_url: str
    long_url: str
    click_count: int
    created_at: Optional[str] = None
    expiry_date: Optional[str] = None
    is_expired: bool
    qr_url: str
    preview_url: str

    model_config = {"from_attributes": True}


class LinkListResponse(BaseModel):
    items: list[LinkListItem]
    total: int
    page: int
    limit: int
    pages: int
