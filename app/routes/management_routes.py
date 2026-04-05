"""
Link management dashboard routes — list all links with search/filter/pagination.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.database import get_db
from app.schemas.url import LinkListItem, LinkListResponse
from app.services import url_service
from app.utils.security import get_current_user_optional

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Link Management"])


def _is_expired(expiry_date_str: Optional[str]) -> bool:
    if not expiry_date_str:
        return False
    try:
        expiry = datetime.fromisoformat(expiry_date_str)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return datetime.now(tz=timezone.utc) > expiry
    except Exception:
        return False


@router.get(
    "/links",
    response_model=LinkListResponse,
    summary="List all short links",
    description=(
        "Returns a paginated list of all created short links. "
        "Supports full-text search on URL/short code and filtering by active/expired status."
    ),
)
async def list_links(
    request: Request,
    q: Optional[str] = Query(None, description="Search in long_url or short_code"),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter: 'active' | 'expired'"),
    db: AsyncSession = Depends(get_db),
) -> LinkListResponse:
    """GET /links — return paginated link list with optional search/filter."""
    user_id = get_current_user_optional(request)
    data = await url_service.list_all_urls(
        db=db,
        search=q,
        page=page,
        limit=limit,
        filter_status=status,
        user_id=user_id,
    )

    items: list[LinkListItem] = []
    for url_obj in data["items"]:
        expiry_str = url_obj.expiry_date.isoformat() if url_obj.expiry_date else None
        expired = _is_expired(expiry_str)
        items.append(
            LinkListItem(
                short_code=url_obj.short_code,
                short_url=f"{settings.base_url}/{url_obj.short_code}",
                long_url=url_obj.long_url,
                click_count=url_obj.click_count,
                created_at=url_obj.created_at.isoformat() if url_obj.created_at else None,
                expiry_date=expiry_str,
                is_expired=expired,
                qr_url=f"{settings.base_url}/qr/{url_obj.short_code}",
                preview_url=f"{settings.base_url}/preview/{url_obj.short_code}",
            )
        )

    return LinkListResponse(
        items=items,
        total=data["total"],
        page=data["page"],
        limit=data["limit"],
        pages=data["pages"],
    )
