"""
Core URL service: shorten, resolve, analytics aggregation, bulk ops, link management.
Rewritten for MongoDB/Motor — replaces the SQLAlchemy/asyncpg version.
"""
import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database.models import URLDoc, doc_to_url
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
    return max(remaining, 1)


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
    db: AsyncIOMotorDatabase,
    custom_alias: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
    user_id: Optional[int] = None,
) -> URLDoc:
    """
    Shorten a long URL.

    Steps:
      1. Validate the URL.
      2. If custom_alias provided, check uniqueness.
      3. Generate Snowflake ID → encode to Base62.
      4. Persist to MongoDB.
      5. Warm the cache.

    Returns a URLDoc.
    Raises ValueError on validation / uniqueness failures.
    """
    validated_url = validate_url(long_url)

    if custom_alias:
        existing = await db.urls.find_one({"short_code": custom_alias})
        if existing:
            raise ValueError(f"Custom alias '{custom_alias}' is already taken.")
        short_code = custom_alias
        url_id = generate_id()
    else:
        url_id = generate_id()
        short_code = encode(url_id)

    now = datetime.now(tz=timezone.utc)
    doc = {
        "_id": url_id,
        "user_id": user_id,
        "long_url": validated_url,
        "short_code": short_code,
        "created_at": now,
        "expiry_date": expiry_date,
        "click_count": 0,
    }
    await db.urls.insert_one(doc)

    # Warm the cache
    ttl = _ttl_from_expiry(expiry_date)
    await set_cached_url(short_code, validated_url, ttl=ttl)

    logger.info("Created short URL: %s → %s", short_code, validated_url)
    return doc_to_url(doc)


# ---------------------------------------------------------------------------
# Bulk Shorten
# ---------------------------------------------------------------------------

async def create_bulk_short_urls(
    requests: list,
    db: AsyncIOMotorDatabase,
    user_id: Optional[int] = None,
) -> list[dict]:
    """
    Shorten multiple URLs in one call.

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

async def resolve_short_url(short_code: str, db: AsyncIOMotorDatabase) -> str:
    """
    Resolve a short_code to its long URL.

    Cache-aside strategy:
      1. Check MongoDB cache → return immediately on hit.
      2. On miss → query MongoDB urls collection.
      3. Validate expiry.
      4. Warm cache.
      5. Increment click count.

    Raises:
        ValueError: If short_code not found or link has expired.
    """
    # 1. Cache check
    try:
        cached = await get_cached_url(short_code)
        if cached is not None:
            await _increment_click_count(short_code, db)
            return cached
    except CacheMissError:
        raise ValueError(f"Short URL '{short_code}' not found.")

    # 2. DB lookup
    url_doc = await db.urls.find_one({"short_code": short_code})

    if url_doc is None:
        await set_negative_cache(short_code)
        raise ValueError(f"Short URL '{short_code}' not found.")

    url_obj = doc_to_url(url_doc)

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


async def _increment_click_count(short_code: str, db: AsyncIOMotorDatabase) -> None:
    """Increment the URL click counter."""
    try:
        await db.urls.update_one(
            {"short_code": short_code},
            {"$inc": {"click_count": 1}},
        )
    except Exception as exc:
        logger.warning("Failed to increment click count for '%s': %s", short_code, exc)


# ---------------------------------------------------------------------------
# Link Management — List
# ---------------------------------------------------------------------------

async def list_all_urls(
    db: AsyncIOMotorDatabase,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    filter_status: Optional[str] = None,
    user_id: Optional[int] = None,
) -> dict:
    """
    Return a paginated list of all short URLs.

    Args:
        search:        Optional search string (long_url or short_code, case-insensitive).
        page:          1-based page number.
        limit:         Records per page (max 100).
        filter_status: "active" | "expired" | None.
        user_id:       Filter to this user's links only.
    """
    limit = min(limit, 100)
    skip = (page - 1) * limit

    query: dict = {}

    if user_id is not None:
        query["user_id"] = user_id

    if search:
        pattern = re.compile(search, re.IGNORECASE)
        query["$or"] = [
            {"long_url": {"$regex": pattern}},
            {"short_code": {"$regex": pattern}},
        ]

    now = datetime.now(tz=timezone.utc)
    if filter_status == "expired":
        query["expiry_date"] = {"$lte": now}
    elif filter_status == "active":
        query["$and"] = query.get("$and", []) + [
            {"$or": [{"expiry_date": None}, {"expiry_date": {"$gt": now}}]}
        ]

    total = await db.urls.count_documents(query)
    cursor = db.urls.find(query).sort("_id", -1).skip(skip).limit(limit)
    url_docs = await cursor.to_list(length=limit)

    pages = max(1, math.ceil(total / limit))

    return {
        "items": [doc_to_url(d) for d in url_docs],
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
    db: AsyncIOMotorDatabase,
    long_url: Optional[str] = None,
    custom_alias: Optional[str] = None,
    expiry_date: Optional[datetime] = None,
    user_id: Optional[int] = None,
) -> URLDoc:
    """
    Update an existing short URL's long_url, alias, or expiry.

    Returns the updated URLDoc.
    Raises ValueError if short_code not found or alias conflicts.
    """
    url_doc = await db.urls.find_one({"short_code": short_code})
    if url_doc is None:
        raise ValueError(f"Short URL '{short_code}' not found.")

    url_obj = doc_to_url(url_doc)

    if user_id is not None and url_obj.user_id != user_id:
        raise ValueError("Unauthorized to edit this link.")

    updates: dict = {}
    new_short_code = short_code

    if custom_alias and custom_alias != short_code:
        existing = await db.urls.find_one({"short_code": custom_alias})
        if existing:
            raise ValueError(f"Custom alias '{custom_alias}' is already taken.")
        new_short_code = custom_alias
        updates["short_code"] = new_short_code

    if long_url is not None:
        updates["long_url"] = validate_url(long_url)

    if expiry_date is not None:
        updates["expiry_date"] = expiry_date

    if updates:
        await db.urls.update_one({"short_code": short_code}, {"$set": updates})

    # Evict old cache entry if alias changed
    if new_short_code != short_code:
        await invalidate_cache(short_code)

    # Re-fetch to return the updated state
    updated_doc = await db.urls.find_one({"short_code": new_short_code})
    updated_obj = doc_to_url(updated_doc)  # type: ignore[arg-type]

    # Refresh cache
    ttl = _ttl_from_expiry(updated_obj.expiry_date)
    await set_cached_url(updated_obj.short_code, updated_obj.long_url, ttl=ttl)

    logger.info("Updated short URL: %s (was: %s)", updated_obj.short_code, short_code)
    return updated_obj


# ---------------------------------------------------------------------------
# Link Management — Delete
# ---------------------------------------------------------------------------

async def delete_short_url(
    short_code: str, db: AsyncIOMotorDatabase, user_id: Optional[int] = None
) -> None:
    """
    Delete a short URL and its analytics from MongoDB, and evict cache.

    Raises ValueError if short_code not found.
    """
    url_doc = await db.urls.find_one({"short_code": short_code})
    if url_doc is None:
        raise ValueError(f"Short URL '{short_code}' not found.")

    url_obj = doc_to_url(url_doc)
    if user_id is not None and url_obj.user_id != user_id:
        raise ValueError("Unauthorized to delete this link.")

    await db.analytics.delete_many({"short_code": short_code})
    await db.urls.delete_one({"short_code": short_code})
    await invalidate_cache(short_code)

    logger.info("Deleted short URL: %s", short_code)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

async def get_url_analytics(short_code: str, db: AsyncIOMotorDatabase) -> dict:
    """
    Retrieve aggregated analytics for a short URL.

    Returns a dict with summary stats and recent click records.
    """
    url_doc = await db.urls.find_one({"short_code": short_code})
    if url_doc is None:
        raise ValueError(f"Short URL '{short_code}' not found.")

    url_obj = doc_to_url(url_doc)

    # Aggregate per-country clicks
    country_pipeline = [
        {"$match": {"short_code": short_code}},
        {"$group": {"_id": "$geo_country", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    country_cursor = db.analytics.aggregate(country_pipeline)
    country_results = await country_cursor.to_list(length=10)

    # Aggregate per-device clicks
    device_pipeline = [
        {"$match": {"short_code": short_code}},
        {"$group": {"_id": "$device_type", "count": {"$sum": 1}}},
    ]
    device_cursor = db.analytics.aggregate(device_pipeline)
    device_results = await device_cursor.to_list(length=20)

    # Recent 20 click events
    recent_cursor = (
        db.analytics.find({"short_code": short_code})
        .sort("timestamp", -1)
        .limit(20)
    )
    recent_events = await recent_cursor.to_list(length=20)

    return {
        "short_code": short_code,
        "long_url": url_obj.long_url,
        "total_clicks": url_obj.click_count,
        "created_at": url_obj.created_at.isoformat() if url_obj.created_at else None,
        "expiry_date": url_obj.expiry_date.isoformat() if url_obj.expiry_date else None,
        "by_country": [
            {"country": r["_id"], "clicks": r["count"]} for r in country_results
        ],
        "by_device": [
            {"device": r["_id"], "clicks": r["count"]} for r in device_results
        ],
        "recent_clicks": [
            {
                "timestamp": e["timestamp"].isoformat() if e.get("timestamp") else None,
                "ip": e.get("ip_address"),
                "country": e.get("geo_country"),
                "city": e.get("geo_city"),
                "device": e.get("device_type"),
                "browser": e.get("browser"),
                "os": e.get("os"),
            }
            for e in recent_events
        ],
    }
