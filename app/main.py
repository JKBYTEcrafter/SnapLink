"""
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os

from app.config import get_settings
from app.database.database import create_tables
from app.services.cache_service import close_redis, init_redis
from app.utils.id_generator import init_generator

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.environment == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("Starting URL Shortener Service...")
    init_generator(machine_id=settings.machine_id)
    init_redis(url=settings.redis_url)
    await create_tables()
    logger.info("Service ready.")

    yield

    # Shutdown
    logger.info("Shutting down URL Shortener Service...")
    await close_redis()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SnapLink API",
    description=(
        "A production-grade distributed URL shortener with Base62 encoding, "
        "Redis caching, async analytics, rate limiting, QR code generation, "
        "bulk shortening, link management dashboard, and social preview cards."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."},
    )


# ---------------------------------------------------------------------------
# Specific Routers
# ---------------------------------------------------------------------------

from app.routes import analytics_routes, auth_routes, management_routes, preview_routes, qr_routes, url_routes  # noqa: E402

app.include_router(auth_routes.router)         # POST /auth/*
app.include_router(management_routes.router)   # GET /links
app.include_router(analytics_routes.router)   # GET /analytics/{code}
app.include_router(qr_routes.router)          # GET /qr/{code}
app.include_router(preview_routes.router)     # GET /preview/{code}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"], summary="Health check")
async def health_check() -> dict:
    return {"status": "ok", "service": "snaplink", "version": "2.0.0"}


# ---------------------------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    return FileResponse(os.path.join(STATIC_DIR, "dashboard.html"))

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Catch-All Router (MUST BE LAST)
# ---------------------------------------------------------------------------

app.include_router(url_routes.router)         # POST /shorten, GET /{code}
