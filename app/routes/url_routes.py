"""
URL shortening, redirect, bulk shorten, link edit, and delete routes.
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from user_agents import parse as ua_parse

from app.config import get_settings
from app.database.database import get_db
from app.schemas.url import (
    BulkShortenRequest,
    BulkShortenResponse,
    BulkShortenResultItem,
    ShortenRequest,
    ShortenResponse,
    UpdateLinkRequest,
)
from app.services import analytics_service, url_service
from app.services.rate_limiter import RateLimiter
from app.utils.geo import get_geo_info
from app.utils.security import get_current_user_optional

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["URL Shortener"])

_rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# POST /shorten — single URL
# ---------------------------------------------------------------------------

@router.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Shorten a URL",
    description="Accept a long URL and return a unique short URL with optional custom alias and expiry.",
)
async def shorten_url(
    payload: ShortenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_rate_limiter),
) -> ShortenResponse:
    """POST /shorten — create a shortened URL."""
    try:
        user_id = get_current_user_optional(request)
        url_obj = await url_service.create_short_url(
            long_url=payload.long_url,
            db=db,
            custom_alias=payload.custom_alias,
            expiry_date=payload.expiry_date,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    short_url = f"{settings.base_url}/{url_obj.short_code}"
    qr_url = f"{settings.base_url}/qr/{url_obj.short_code}"

    return ShortenResponse(
        short_code=url_obj.short_code,
        short_url=short_url,
        long_url=url_obj.long_url,
        created_at=url_obj.created_at or datetime.now(tz=timezone.utc),
        expiry_date=url_obj.expiry_date,
        qr_url=qr_url,
    )


# ---------------------------------------------------------------------------
# POST /shorten/bulk — bulk URL shortening
# ---------------------------------------------------------------------------

@router.post(
    "/shorten/bulk",
    response_model=BulkShortenResponse,
    status_code=status.HTTP_200_OK,
    summary="Bulk shorten URLs",
    description="Accept up to 50 URLs and return shortened URLs for each. Partial failures are reported individually.",
)
async def bulk_shorten_urls(
    payload: BulkShortenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_rate_limiter),
) -> BulkShortenResponse:
    """POST /shorten/bulk — shorten multiple URLs in one call."""
    user_id = get_current_user_optional(request)
    raw_results = await url_service.create_bulk_short_urls(payload.urls, db, user_id=user_id)

    result_items: list[BulkShortenResultItem] = []
    succeeded = 0
    failed = 0

    for r in raw_results:
        if r["success"]:
            url_obj = r["url_obj"]
            short_url = f"{settings.base_url}/{url_obj.short_code}"
            qr_url = f"{settings.base_url}/qr/{url_obj.short_code}"
            result_items.append(
                BulkShortenResultItem(
                    index=r["index"],
                    success=True,
                    data=ShortenResponse(
                        short_code=url_obj.short_code,
                        short_url=short_url,
                        long_url=url_obj.long_url,
                        created_at=url_obj.created_at or datetime.now(tz=timezone.utc),
                        expiry_date=url_obj.expiry_date,
                        qr_url=qr_url,
                    ),
                )
            )
            succeeded += 1
        else:
            result_items.append(
                BulkShortenResultItem(
                    index=r["index"],
                    success=False,
                    error=r.get("error", "Unknown error"),
                )
            )
            failed += 1

    return BulkShortenResponse(
        total=len(raw_results),
        succeeded=succeeded,
        failed=failed,
        results=result_items,
    )


# ---------------------------------------------------------------------------
# PATCH /links/{short_code} — edit a link
# ---------------------------------------------------------------------------

@router.patch(
    "/links/{short_code}",
    response_model=ShortenResponse,
    summary="Edit a short link",
    description="Modify the long URL, custom alias, or expiry date. Cache is updated automatically.",
)
async def update_link(
    short_code: str,
    payload: UpdateLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ShortenResponse:
    """PATCH /links/{short_code} — update link properties."""
    try:
        user_id = get_current_user_optional(request)
        url_obj = await url_service.update_short_url(
            short_code=short_code,
            db=db,
            long_url=payload.long_url,
            custom_alias=payload.custom_alias,
            expiry_date=payload.expiry_date,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    short_url = f"{settings.base_url}/{url_obj.short_code}"
    qr_url = f"{settings.base_url}/qr/{url_obj.short_code}"

    return ShortenResponse(
        short_code=url_obj.short_code,
        short_url=short_url,
        long_url=url_obj.long_url,
        created_at=url_obj.created_at or datetime.now(tz=timezone.utc),
        expiry_date=url_obj.expiry_date,
        qr_url=qr_url,
    )


# ---------------------------------------------------------------------------
# DELETE /links/{short_code} — delete a link
# ---------------------------------------------------------------------------

@router.delete(
    "/links/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a short link",
    description="Permanently delete a short link and all its analytics. Cache is evicted.",
)
async def delete_link(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """DELETE /links/{short_code} — remove link from DB and cache."""
    try:
        user_id = get_current_user_optional(request)
        await url_service.delete_short_url(short_code, db, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /{short_code} — redirect
# ---------------------------------------------------------------------------

@router.get(
    "/{short_code}",
    status_code=status.HTTP_302_FOUND,
    summary="Redirect to original URL",
    description="Resolve a short code to its long URL and redirect (HTTP 302). Queues an analytics event async.",
)
async def redirect_url(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_rate_limiter),
) -> RedirectResponse:
    """GET /{short_code} — cache-first redirect."""
    try:
        long_url = await url_service.resolve_short_url(short_code, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Build analytics event — fire and forget (do not await in request path)
    ua_string = request.headers.get("user-agent", "")
    parsed_ua = ua_parse(ua_string)
    client_ip = _get_client_ip(request)

    async def _fire_analytics() -> None:
        geo = await get_geo_info(client_ip)
        event = {
            "short_code": short_code,
            "ip_address": client_ip,
            "user_agent": ua_string,
            "device_type": _device_type(parsed_ua),
            "browser": parsed_ua.browser.family,
            "os": parsed_ua.os.family,
            "geo_country": geo.get("country"),
            "geo_city": geo.get("city"),
            "referer": request.headers.get("referer"),
        }
        await analytics_service.push_analytics_event(event)

    # Schedule as background task — does not block the redirect
    asyncio.ensure_future(_fire_analytics())

    return RedirectResponse(url=long_url, status_code=status.HTTP_302_FOUND)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _device_type(ua) -> str:  # type: ignore[no-untyped-def]
    if ua.is_mobile:
        return "mobile"
    if ua.is_tablet:
        return "tablet"
    if ua.is_pc:
        return "desktop"
    if ua.is_bot:
        return "bot"
    return "other"
