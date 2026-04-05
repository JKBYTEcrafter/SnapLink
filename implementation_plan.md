# Distributed URL Shortener — Implementation Plan

A production-grade URL shortener system (Bitly-style) built with **FastAPI**, **PostgreSQL**, **Redis**, **Celery**, and **Docker**. The system supports Base62 encoding, async analytics, per-IP rate limiting, QR code generation, and expiry links.

## Architecture

```
Client → FastAPI (API Server) → Redis Cache → PostgreSQL
                                     ↓
                             Analytics Queue (Redis)
                                     ↓
                             Celery Worker → PostgreSQL (analytics)
```

---

## Proposed Changes

### Project Root

#### [NEW] [requirements.txt](file:///f:/Projects/URL1/requirements.txt)
All Python dependencies: FastAPI, SQLAlchemy (async), asyncpg, aioredis, Celery, qrcode, user-agents, geoip2, httpx, pytest, etc.

#### [NEW] [.env.example](file:///f:/Projects/URL1/.env.example)
Environment variable template (DB URL, Redis URL, secret key, base domain, etc.)

#### [NEW] [docker-compose.yml](file:///f:/Projects/URL1/docker-compose.yml)
Orchestrates: API, Celery worker, PostgreSQL, Redis.

---

### app/database/

#### [NEW] [database.py](file:///f:/Projects/URL1/app/database/database.py)
- Async SQLAlchemy engine (`create_async_engine`)
- `AsyncSession` factory
- `Base` declarative base

#### [NEW] [models.py](file:///f:/Projects/URL1/app/database/models.py)
- `URL` model: `id`, `long_url`, `short_code`, `custom_alias`, `created_at`, `expiry_date`, `click_count`
- `Analytics` model: `id`, `short_code`, `timestamp`, `ip_address`, `user_agent`, `device_type`, `geo_country`, `geo_city`

---

### app/schemas/

#### [NEW] [url.py](file:///f:/Projects/URL1/app/schemas/url.py)
Pydantic v2 models: `ShortenRequest`, `ShortenResponse`, `AnalyticsResponse`

---

### app/utils/

#### [NEW] [base62.py](file:///f:/Projects/URL1/app/utils/base62.py)
- `encode(n: int) → str` — converts integer ID to Base62 string
- `decode(s: str) → int` — inverse operation

#### [NEW] [id_generator.py](file:///f:/Projects/URL1/app/utils/id_generator.py)
- Snowflake-style distributed ID generator (41-bit timestamp + 10-bit machine ID + 12-bit sequence)

#### [NEW] [validators.py](file:///f:/Projects/URL1/app/utils/validators.py)
- URL validation (scheme check, domain validation, block localhost/private IPs)

#### [NEW] [qr_generator.py](file:///f:/Projects/URL1/app/utils/qr_generator.py)
- `generate_qr_bytes(url: str) → bytes` — returns PNG bytes for a QR code

#### [NEW] [geo.py](file:///f:/Projects/URL1/app/utils/geo.py)
- IP geolocation via `ipapi.co` free API (async HTTP call)

---

### app/services/

#### [NEW] [cache_service.py](file:///f:/Projects/URL1/app/services/cache_service.py)
- `get_cached_url(short_code)`, `set_cached_url(short_code, long_url, ttl)`
- Cache-aside pattern using `aioredis`

#### [NEW] [url_service.py](file:///f:/Projects/URL1/app/services/url_service.py)
- `create_short_url(req, db, redis)` — generates ID → encodes to Base62 → stores in PostgreSQL + Redis
- `resolve_short_url(short_code, db, redis)` — cache-first lookup, expiry check
- `get_analytics(short_code, db)` — aggregate analytics query

#### [NEW] [analytics_service.py](file:///f:/Projects/URL1/app/services/analytics_service.py)
- `push_analytics_event(event_dict)` — pushes JSON event to Redis list (Celery task queue)

#### [NEW] [rate_limiter.py](file:///f:/Projects/URL1/app/services/rate_limiter.py)
- Sliding-window rate limiter using Redis sorted sets
- FastAPI dependency: `RateLimiter(max_requests=60, window_seconds=60)`

---

### app/routes/

#### [NEW] [url_routes.py](file:///f:/Projects/URL1/app/routes/url_routes.py)
- `POST /shorten` — shorten a URL
- `GET /{short_code}` — redirect (HTTP 302)

#### [NEW] [analytics_routes.py](file:///f:/Projects/URL1/app/routes/analytics_routes.py)
- `GET /analytics/{short_code}` — return analytics data

#### [NEW] [qr_routes.py](file:///f:/Projects/URL1/app/routes/qr_routes.py)
- `GET /qr/{short_code}` — return PNG QR code image

---

### app/

#### [NEW] [main.py](file:///f:/Projects/URL1/app/main.py)
- FastAPI app with lifespan (DB tables creation, Redis pool init)
- CORS middleware
- Include all routers
- Global exception handlers

#### [NEW] [config.py](file:///f:/Projects/URL1/app/config.py)
- `Settings` class using `pydantic-settings`

---

### worker/

#### [NEW] [celery_app.py](file:///f:/Projects/URL1/worker/celery_app.py)
- Celery app configured with Redis broker and backend

#### [NEW] [tasks.py](file:///f:/Projects/URL1/worker/tasks.py)
- `process_analytics_event(event_dict)` — Celery task that writes analytics row to PostgreSQL

---

### docker/

#### [NEW] [Dockerfile.api](file:///f:/Projects/URL1/docker/Dockerfile.api)
Multi-stage Python Docker image for the API server.

#### [NEW] [Dockerfile.worker](file:///f:/Projects/URL1/docker/Dockerfile.worker)
Docker image for the Celery worker.

---

### tests/

#### [NEW] [conftest.py](file:///f:/Projects/URL1/tests/conftest.py)
- pytest fixtures: in-memory SQLite DB override, mock Redis client

#### [NEW] [test_base62.py](file:///f:/Projects/URL1/tests/test_base62.py)
- Unit tests: `encode(0)`, `encode(1)`, `encode(3844000000)`, round-trip `decode(encode(n)) == n`

#### [NEW] [test_api.py](file:///f:/Projects/URL1/tests/test_api.py)
- Tests: `POST /shorten`, `GET /{short_code}` redirect, custom alias, expiry, invalid URL rejection

#### [NEW] [test_integration.py](file:///f:/Projects/URL1/tests/test_integration.py)
- Tests: full shorten→resolve pipeline with real Redis + DB (via `testcontainers`)

---

## Verification Plan

### Automated Tests

All tests live in `tests/`. Run with:

```bash
# Install deps
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run only unit tests (no Docker required)
pytest tests/test_base62.py tests/test_api.py -v
```

### Integration Tests (requires Docker)

```bash
# Start dependencies
docker-compose up -d postgres redis

# Run integration tests  
pytest tests/test_integration.py -v
```

### Full-Stack Smoke Test (Docker Compose)

```bash
docker-compose up --build

# Shorten a URL
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://www.google.com"}'

# Follow redirect
curl -L http://localhost:8000/<short_code>

# Get analytics
curl http://localhost:8000/analytics/<short_code>

# Get QR code
curl http://localhost:8000/qr/<short_code> --output qr.png
```
