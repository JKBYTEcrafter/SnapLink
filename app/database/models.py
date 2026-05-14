"""
MongoDB document dataclasses.
Replace the SQLAlchemy ORM models with lightweight Python dataclasses
that mirror the same field interface used throughout the service layer.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Helper: safe UTC-aware datetime
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Document dataclasses
# ---------------------------------------------------------------------------

@dataclass
class UserDoc:
    """Mirrors the old User ORM model."""
    id: int
    email: str
    password_hash: str
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class URLDoc:
    """Mirrors the old URL ORM model."""
    id: int
    user_id: Optional[int]
    long_url: str
    short_code: str
    created_at: datetime = field(default_factory=_utcnow)
    expiry_date: Optional[datetime] = None
    click_count: int = 0


@dataclass
class AnalyticsDoc:
    """Mirrors the old Analytics ORM model."""
    id: str
    short_code: str
    timestamp: datetime = field(default_factory=_utcnow)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    referer: Optional[str] = None


@dataclass
class PasswordResetOTPDoc:
    """Mirrors the old PasswordResetOTP ORM model."""
    id: str
    email: str
    otp_code: str
    expires_at: datetime
    is_used: int = 0


# ---------------------------------------------------------------------------
# Converters: MongoDB document dict → dataclass
# ---------------------------------------------------------------------------

def doc_to_user(doc: dict) -> UserDoc:
    return UserDoc(
        id=doc["_id"],
        email=doc["email"],
        password_hash=doc["password_hash"],
        created_at=doc.get("created_at", _utcnow()),
    )


def doc_to_url(doc: dict) -> URLDoc:
    return URLDoc(
        id=doc["_id"],
        user_id=doc.get("user_id"),
        long_url=doc["long_url"],
        short_code=doc["short_code"],
        created_at=doc.get("created_at", _utcnow()),
        expiry_date=doc.get("expiry_date"),
        click_count=doc.get("click_count", 0),
    )


def doc_to_otp(doc: dict) -> PasswordResetOTPDoc:
    return PasswordResetOTPDoc(
        id=str(doc["_id"]),
        email=doc["email"],
        otp_code=doc["otp_code"],
        expires_at=doc["expires_at"],
        is_used=doc.get("is_used", 0),
    )
