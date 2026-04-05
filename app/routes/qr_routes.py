"""
QR code endpoint.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database.database import get_db
from app.database.models import URL
from app.utils.qr_generator import generate_qr_bytes

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["QR Code"])


@router.get(
    "/qr/{short_code}",
    response_class=Response,
    summary="Get QR code for a short URL",
    description="Returns a PNG image of the QR code encoding the short URL.",
    responses={
        200: {"content": {"image/png": {}}, "description": "PNG QR code image"},
        404: {"description": "Short URL not found"},
    },
)
async def get_qr_code(
    short_code: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """GET /qr/{short_code} — return a PNG QR code for the short URL."""
    url_obj = await db.scalar(select(URL).where(URL.short_code == short_code))
    if url_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short URL '{short_code}' not found.",
        )

    short_url = f"{settings.base_url}/{short_code}"
    png_bytes = generate_qr_bytes(short_url)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
