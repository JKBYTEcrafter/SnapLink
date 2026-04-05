"""
Social preview image endpoint.
GET /preview/{short_code} → returns a PNG preview card.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.database import get_db
from app.database.models import URL
from app.utils.preview_generator import generate_preview_card

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Preview"])


@router.get(
    "/preview/{short_code}",
    response_class=Response,
    summary="Get social preview card for a short URL",
    description="Returns a PNG social preview card showing the short URL, destination, and QR code.",
    responses={
        200: {"content": {"image/png": {}}, "description": "PNG preview card"},
        404: {"description": "Short URL not found"},
    },
)
async def get_preview(
    short_code: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """GET /preview/{short_code} — return a PNG social preview card."""
    url_obj = await db.scalar(select(URL).where(URL.short_code == short_code))
    if url_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short URL '{short_code}' not found.",
        )

    short_url = f"{settings.base_url}/{short_code}"
    try:
        png_bytes = generate_preview_card(
            short_url=short_url,
            long_url=url_obj.long_url,
            click_count=url_obj.click_count,
        )
    except Exception as exc:
        logger.error("Preview generation failed for %s: %s", short_code, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate preview image.",
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )
