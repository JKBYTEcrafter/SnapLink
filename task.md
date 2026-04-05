# Distributed URL Shortener — Task Checklist

## Planning
- [x] Create task.md
- [x] Write implementation_plan.md
- [x] Get user approval

## Project Scaffold
- [x] Create directory structure (app/, worker/, docker/, tests/)
- [x] Create requirements.txt and .env.example
- [x] Create docker-compose.yml

## Database Layer (app/database/)
- [x] database.py — SQLAlchemy async engine + session factory
- [x] models.py — URL, Analytics ORM models

## Schemas (app/schemas/)
- [x] url.py — Pydantic request/response schemas

## Utils (app/utils/)
- [x] base62.py — Base62 encode/decode
- [x] id_generator.py — Snowflake-style distributed ID generator
- [x] validators.py — URL validation helpers
- [x] qr_generator.py — QR code generation
- [x] geo.py — IP geolocation helper

## Services (app/services/)
- [x] url_service.py — Shorten, lookup, expiry, custom alias
- [x] cache_service.py — Redis cache-aside helpers
- [x] analytics_service.py — Queue push + DB write
- [x] rate_limiter.py — Sliding-window per-IP rate limiting

## Routes (app/routes/)
- [x] url_routes.py — POST /shorten, GET /{short_code}
- [x] analytics_routes.py — GET /analytics/{short_code}
- [x] qr_routes.py — GET /qr/{short_code}

## Main App (app/)
- [x] main.py — FastAPI app, lifespan, middleware, routers

## Worker (worker/)
- [x] celery_app.py — Celery config + Redis broker
- [x] tasks.py — Analytics consumer task

## Docker
- [x] docker/Dockerfile.api
- [x] docker/Dockerfile.worker
- [x] docker-compose.yml

## Tests (tests/)
- [x] test_base62.py — Unit tests for encoding logic
- [x] test_api.py — API endpoint tests (httpx + pytest)
- [x] test_integration.py — DB + Redis integration tests
- [x] conftest.py — Fixtures

## Verification
- [x] File structure verified via directory listing
- [x] Walkthrough created with cURL examples and setup guide
- [ ] Run unit tests (pip install in progress)
