"""
Core URL service: shorten, resolve, analytics aggregation, bulk ops, link management.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import Analytics, URL
from app.services.cache_service import (
    CacheMissError,
    get_cached_url,
    invalidate_cache,
    set_cached_url,
    set_negative_cache,
)
from app.utils.base62 import encode
from app.utils.id_generator import generate_id
from app.utils.validators import validate_url

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ttl_from_expiry(expiry_date: datetime | None) -> int | None:
    """Compute remaining TTL seconds from an expiry_date, or None if no expiry."""
    if expiry_date is None:
        return None
    now = datetime.now(tz=timezone.utc)
    remaining = int((expiry_date - now).total_seconds())
    return max(remaining, 1)  # always at least 1 second


def _is_expired(expiry_date: datetime | None) -> bool:
    """Return True if the given expiry_date has passed."""
    if expiry_date is None:
        return False
    now = datetime.now(tz=timezone.utc)
    expiry = expiry_date
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return now > expiry


# ---------------------------------------------------------------------------
# Shorten (single)
# ---------------------------------------------------------------------------

async def create_short_url(
    long_url: str,
    db: AsyncSession,
    custom_alias: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
    user_id: Optional[int] = None,
) -> URL:
    """
    Shorten a long URL.

    Steps:
      1. Validate the URL.
      2. If custom_alias provided, check uniqueness.
      3. Generate Snowflake ID → encode to Base62.
      4. Persist to PostgreSQL.
      5. Warm the Redis cache.

    Returns the created URL ORM object.
    Raises ValueError on validation / uniqueness failures.
    """
    validated_url = validate_url(long_url)

    if custom_alias:
        # Check alias uniqueness
        existing = await db.scalar(select(URL).where(URL.short_code == custom_alias))
        if existing:
            raise ValueError(f"Custom alias '{custom_alias}' is already taken.")
        short_code = custom_alias
        url_id = generate_id()
    else:
        url_id = generate_id()
        short_code = encode(url_id)

    url_obj = URL(
        id=url_id,
        user_id=user_id,
        long_url=validated_url,
        short_code=short_code,
        expiry_date=expiry_date,
    )
    db.add(url_obj)
    await db.flush()  # get the persisted state without committing

    # Warm the cache
    ttl = _ttl_from_expiry(expiry_date)
    await set_cached_url(short_code, validated_url, ttl=ttl)

    logger.info("Created short URL: %s → %s", short_code, validated_url)
    return url_obj


# ---------------------------------------------------------------------------
# Bulk Shorten
# ---------------------------------------------------------------------------

async def create_bulk_short_urls(
    requests: list,
    db: AsyncSession,
    user_id: Optional[int] = None,
) -> list[dict]:
    """
    Shorten multiple URLs in a single session.

    Each item in `requests` is a ShortenRequest-like object with
    .long_url, .custom_alias, .expiry_date attributes.

    Returns a list of result dicts with keys: index, success, url_obj / error.
    """
    results = []
    for idx, req in enumerate(requests):
        try:
            url_obj = await create_short_url(
                long_url=req.long_url,
                db=db,
                custom_alias=req.custom_alias,
                expiry_date=req.expiry_date,
                user_id=user_id,
            )
            results.append({"index": idx, "success": True, "url_obj": url_obj})
        except Exception as exc:
            logger.warning("Bulk shorten failed for index %d: %s", idx, exc)
            results.append({"index": idx, "success": False, "error": str(exc)})
    return results


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

async def resolve_short_url(short_code: str, db: AsyncSession) -> str:
    """
    Resolve a short_code to its long URL.

    Cache-aside strategy:
      1. Check Redis → return immediately on hit.
      2. On miss → query PostgreSQL.
      3. Validate expiry.
      4. Warm cache.
      5. Increment click count asynchronously.

    Raises:
        ValueError: If short_code not found or link has expired.
    """
    # 1. Cache check
    try:
        cached = await get_cached_url(short_code)
        if cached is not None:
            # Fire-and-forget click count increment
            await _increment_click_count(short_code, db)
            return cached
    except CacheMissError:
        raise ValueError(f"Short URL '{short_code}' not found.")

    # 2. DB lookup
    url_obj = await db.scalar(select(URL).where(URL.short_code == short_code))

    if url_obj is None:
        await set_negative_cache(short_code)
        raise ValueError(f"Short URL '{short_code}' not found.")

    # 3. Expiry check
    if url_obj.expiry_date:
        now = datetime.now(tz=timezone.utc)
        expiry = url_obj.expiry_date
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if now > expiry:
            await set_negative_cache(short_code, ttl=60)
            raise ValueError(f"Short URL '{short_code}' has expired.")

    # 4. Warm cache
    ttl = _ttl_from_expiry(url_obj.expiry_date)
    await set_cached_url(short_code, url_obj.long_url, ttl=ttl)

    # 5. Increment click count
    await _increment_click_count(short_code, db)

    return url_obj.long_url


async def _increment_click_count(short_code: str, db: AsyncSession) -> None:
    """Increment the URL click counter non-blockingly."""
    try:
        await db.execute(
            update(URL)
            .where(URL.short_code == short_code)
            .values(click_count=URL.click_count + 1)
        )
    except Exception as exc:
        logger.warning("Failed to increment click count for '%s': %s", short_code, exc)


# ---------------------------------------------------------------------------
# Link Management — List
# ---------------------------------------------------------------------------

async def list_all_urls(
    db: AsyncSession,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    filter_status: Optional[str] = None,  # "active" | "expired" | None
    user_id: Optional[int] = None,
) -> dict:
    """
    Return a paginated list of all short URLs.

    Args:
        search:        Optional search string to filter on long_url or short_code (case-insensitive).
        page:          1-based page number.
        limit:         Records per page (max 100).
        filter_status: "active" | "expired" | None (all).
        user_id:       Filter to return only links from a specific user.

    Returns a dict with items, total, page, limit, pages.
    """
    limit = min(limit, 100)
    offset = (page - 1) * limit

    query = select(URL)
    count_query = select(func.count(URL.id))

    if user_id is not None:
        query = query.where(URL.user_id == user_id)
        count_query = count_query.where(URL.user_id == user_id)

    if search:
        pattern = f"%{search}%"
        from sqlalchemy import or_
        search_filter = or_(
            URL.long_url.ilike(pattern),
            URL.short_code.ilike(pattern),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    now = datetime.now(tz=timezone.utc)
    if filter_status == "expired":
        query = query.where(URL.expiry_date <= now)
        count_query = count_query.where(URL.expiry_date <= now)
    elif filter_status == "active":
        from sqlalchemy import or_
        query = query.where(or_(URL.expiry_date.is_(None), URL.expiry_date > now))
        count_query = count_query.where(or_(URL.expiry_date.is_(None), URL.expiry_date > now))

    total = await db.scalar(count_query) or 0

    query = query.order_by(URL.id.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    url_objs = result.scalars().all()

    pages = max(1, math.ceil(total / limit))

    return {
        "items": url_objs,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


# ---------------------------------------------------------------------------
# Link Management — Update (Edit)
# ---------------------------------------------------------------------------

async def update_short_url(
    short_code: str,
    db: AsyncSession,
    long_url: Optional[str] = None,
    custom_alias: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
    user_id: Optional[int] = None,
) -> URL:
    """
    Update an existing short URL's long_url, alias, or expiry.

    - If custom_alias is provided and differs from current, checks uniqueness.
    - Updates Redis cache (evict old, set new).
    - If alias changes, the old short_code becomes a dead entry — we delete it
      and create a new row to preserve short_code integrity.

    Returns the updated URL object.
    Raises ValueError if short_code not found or alias conflicts.
    """
    url_obj = await db.scalar(select(URL).where(URL.short_code == short_code))
    if url_obj is None:
        raise ValueError(f"Short URL '{short_code}' not found.")
        
    if user_id is not None and url_obj.user_id != user_id:
        raise ValueError("Unauthorized to edit this link.")

    new_short_code = short_code

    # Handle alias rename
    if custom_alias and custom_alias != short_code:
        existing = await db.scalar(select(URL).where(URL.short_code == custom_alias))
        if existing:
            raise ValueError(f"Custom alias '{custom_alias}' is already taken.")
        new_short_code = custom_alias

    # Apply updates
    if long_url is not None:
        validated = validate_url(long_url)
        url_obj.long_url = validated
    if expiry_date is not None:
        url_obj.expiry_date = expiry_date

    # If alias changed: we need to update short_code
    if new_short_code != short_code:
        await invalidate_cache(short_code)  # evict old key
        url_obj.short_code = new_short_code

    await db.flush()

    # Refresh cache with new data
    ttl = _ttl_from_expiry(url_obj.expiry_date)
    await set_cached_url(url_obj.short_code, url_obj.long_url, ttl=ttl)

    logger.info("Updated short URL: %s (was: %s)", url_obj.short_code, short_code)
    return url_obj


# ---------------------------------------------------------------------------
# Link Management — Delete
# ---------------------------------------------------------------------------

async def delete_short_url(short_code: str, db: AsyncSession, user_id: Optional[int] = None) -> None:
    """
    Delete a short URL and its analytics from the database,
    and evict from Redis cache.

    Raises ValueError if short_code not found.
    """
    url_obj = await db.scalar(select(URL).where(URL.short_code == short_code))
    if url_obj is None:
        raise ValueError(f"Short URL '{short_code}' not found.")
        
    if user_id is not None and url_obj.user_id != user_id:
        raise ValueError("Unauthorized to delete this link.")

    # Delete analytics for this code
    await db.execute(delete(Analytics).where(Analytics.short_code == short_code))
    # Delete the URL row
    await db.delete(url_obj)
    await db.flush()

    # Evict from cache
    await invalidate_cache(short_code)
    logger.info("Deleted short URL: %s", short_code)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

async def get_url_analytics(short_code: str, db: AsyncSession) -> dict:
    """
    Retrieve aggregated analytics for a short URL.

    Returns a dict with summary stats and recent click records.
    """
    url_obj = await db.scalar(select(URL).where(URL.short_code == short_code))
    if url_obj is None:
        raise ValueError(f"Short URL '{short_code}' not found.")

    # Aggregate per-country counts
    country_counts = await db.execute(
        select(Analytics.geo_country, func.count(Analytics.id).label("count"))
        .where(Analytics.short_code == short_code)
        .group_by(Analytics.geo_country)
        .order_by(func.count(Analytics.id).desc())
        .limit(10)
    )

    # Aggregate per-device-type counts
    device_counts = await db.execute(
        select(Analytics.device_type, func.count(Analytics.id).label("count"))
        .where(Analytics.short_code == short_code)
        .group_by(Analytics.device_type)
    )

    # Recent 20 click events
    recent = await db.execute(
        select(Analytics)
        .where(Analytics.short_code == short_code)
        .order_by(Analytics.timestamp.desc())
        .limit(20)
    )
    recent_events = recent.scalars().all()

    return {
        "short_code": short_code,
        "long_url": url_obj.long_url,
        "total_clicks": url_obj.click_count,
        "created_at": url_obj.created_at.isoformat() if url_obj.created_at else None,
        "expiry_date": url_obj.expiry_date.isoformat() if url_obj.expiry_date else None,
        "by_country": [
            {"country": row.geo_country, "clicks": row.count}
            for row in country_counts.fetchall()
        ],
        "by_device": [
            {"device": row.device_type, "clicks": row.count}
            for row in device_counts.fetchall()
        ],
        "recent_clicks": [
            {
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "ip": event.ip_address,
                "country": event.geo_country,
                "city": event.geo_city,
                "device": event.device_type,
                "browser": event.browser,
                "os": event.os,
            }
            for event in recent_events
        ],
    }
