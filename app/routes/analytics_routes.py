"""
Analytics routes.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.schemas.url import AnalyticsResponse
from app.services import url_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/analytics/{short_code}",
    response_model=AnalyticsResponse,
    summary="Get analytics for a short URL",
    description="Returns click statistics, geo breakdown, device breakdown, and recent 20 click events.",
)
async def get_analytics(
    short_code: str,
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    """GET /analytics/{short_code} — return aggregated analytics data."""
    try:
        data = await url_service.get_url_analytics(short_code, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return AnalyticsResponse(**data)
