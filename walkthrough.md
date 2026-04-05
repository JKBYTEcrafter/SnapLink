# Distributed URL Shortener — Walkthrough

A production-grade Bitly-style URL shortener fully implemented with FastAPI, PostgreSQL, Redis, Celery, and Docker.

---

## What Was Built

### System Architecture
```
Client → FastAPI (4 Uvicorn workers) → Redis Cache → PostgreSQL
                                              ↓
                                    Analytics Queue (Redis)
                                              ↓
                                    Celery Worker → PostgreSQL
```

### Files Created (24 files)

```
f:/Projects/URL1/
├── .env / .env.example          # Environment configuration
├── .gitignore
├── requirements.txt             # All Python deps
├── pytest.ini                   # Test configuration
├── docker-compose.yml           # Full orchestration
│
├── app/
│   ├── config.py                # Pydantic-settings singleton
│   ├── main.py                  # FastAPI app + lifespan
│   ├── database/
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   └── models.py            # URL + Analytics ORM models
│   ├── schemas/
│   │   └── url.py               # Pydantic request/response schemas
│   ├── utils/
│   │   ├── base62.py            # Encode/decode (0-9a-zA-Z)
│   │   ├── id_generator.py      # Snowflake distributed ID
│   │   ├── validators.py        # URL + private IP security
│   │   ├── qr_generator.py      # PNG QR code generation
│   │   └── geo.py               # Async IP geolocation
│   ├── services/
│   │   ├── cache_service.py     # Cache-aside Redis service
│   │   ├── url_service.py       # Core shortening + resolution
│   │   ├── analytics_service.py # Fire-and-forget queue push
│   │   └── rate_limiter.py      # Sliding-window per-IP limiter
│   └── routes/
│       ├── url_routes.py        # POST /shorten, GET /{code}
│       ├── analytics_routes.py  # GET /analytics/{code}
│       └── qr_routes.py         # GET /qr/{code}
│
├── worker/
│   ├── celery_app.py            # Celery config (Redis broker)
│   └── tasks.py                 # Analytics DB writer task
│
├── docker/
│   ├── Dockerfile.api           # Multi-stage API image
│   └── Dockerfile.worker        # Multi-stage worker image
│
└── tests/
    ├── conftest.py              # SQLite + mock Redis fixtures
    ├── test_base62.py           # 11 Base62 unit tests
    ├── test_api.py              # 15 API endpoint tests
    └── test_integration.py      # 4 real-DB integration tests
```

---

## Key Design Decisions

| Concern | Decision | Why |
|---|---|---|
| ID generation | Snowflake (64-bit) | No DB round-trip, no collisions |
| Encoding | Base62 (0-9a-zA-Z) | Deterministic, URL-safe, compact |
| Cache | Redis cache-aside + negative cache | Prevents DB hammering on misses |
| Analytics | Async Celery task | Zero latency impact on redirect |
| Rate limiting | Sliding window (Redis sorted sets) | Accurate, no race conditions |
| Geo lookup | ipapi.co with 3s timeout | Free, async, graceful fallback |

---

## Database Schema

```sql
-- URL mappings
CREATE TABLE urls (
    id           BIGINT PRIMARY KEY,           -- Snowflake ID
    long_url     TEXT NOT NULL,
    short_code   VARCHAR(20) UNIQUE NOT NULL,  -- Base62 encoded
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    expiry_date  TIMESTAMPTZ,                  -- NULL = never expires
    click_count  INTEGER DEFAULT 0
);
CREATE INDEX ix_urls_short_code ON urls (short_code);

-- Per-click analytics
CREATE TABLE analytics (
    id           BIGSERIAL PRIMARY KEY,
    short_code   VARCHAR(20) NOT NULL,
    timestamp    TIMESTAMPTZ DEFAULT NOW(),
    ip_address   VARCHAR(45),
    user_agent   TEXT,
    device_type  VARCHAR(50),
    browser      VARCHAR(100),
    os           VARCHAR(100),
    geo_country  VARCHAR(100),
    geo_city     VARCHAR(100),
    referer      TEXT
);
CREATE INDEX ix_analytics_short_code_ts ON analytics (short_code, timestamp);
```

---

## Setup & Running

### Option A: Docker Compose (Recommended)

```bash
# 1. Clone or enter project directory
cd f:/Projects/URL1

# 2. Start all services
docker-compose up --build

# Services:
#   API:     http://localhost:8000
#   Flower:  http://localhost:5555 (Celery monitor)
#   Swagger: http://localhost:8000/docs
```

### Option B: Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start PostgreSQL and Redis (Docker)
docker run -d -p 5432:5432 -e POSTGRES_DB=urlshortener \
  -e POSTGRES_PASSWORD=password postgres:16-alpine
docker run -d -p 6379:6379 redis:7-alpine

# 3. Copy and edit .env
copy .env.example .env

# 4. Run API
uvicorn app.main:app --reload --port 8000

# 5. Run Celery worker (separate terminal)
celery -A worker.celery_app:celery_app worker --loglevel=info
```

---

## API Usage Examples (cURL)

### 1. Shorten a URL
```bash
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"long_url": "https://www.google.com"}'
```
**Response:**
```json
{
  "short_code": "3bkJvnQ",
  "short_url": "http://localhost:8000/3bkJvnQ",
  "long_url": "https://www.google.com",
  "created_at": "2026-04-05T02:10:00Z",
  "expiry_date": null,
  "qr_url": "http://localhost:8000/qr/3bkJvnQ"
}
```

### 2. Shorten with Custom Alias and Expiry
```bash
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{
    "long_url": "https://www.example.com/very-long-path",
    "custom_alias": "my-link",
    "expiry_date": "2026-12-31T23:59:59Z"
  }'
```

### 3. Redirect (HTTP 302)
```bash
# -L follows the redirect
curl -L http://localhost:8000/3bkJvnQ

# Without following (see 302 headers)
curl -v http://localhost:8000/3bkJvnQ
```

### 4. Get Analytics
```bash
curl http://localhost:8000/analytics/3bkJvnQ
```
**Response:**
```json
{
  "short_code": "3bkJvnQ",
  "long_url": "https://www.google.com",
  "total_clicks": 42,
  "by_country": [{"country": "India", "clicks": 30}],
  "by_device": [{"device": "mobile", "clicks": 25}],
  "recent_clicks": [...]
}
```

### 5. Get QR Code (PNG)
```bash
curl http://localhost:8000/qr/3bkJvnQ --output qr.png
# Open qr.png in any image viewer
```

### 6. Health Check
```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "url-shortener", "version": "1.0.0"}
```

---

## Running Tests

```bash
# Unit tests only (no Docker needed)
pytest tests/test_base62.py tests/test_api.py -v

# All unit + integration tests (needs Postgres + Redis)
docker-compose up -d postgres redis
pytest tests/ -v

# Skip integration tests
pytest tests/ -v -m "not integration"
```

### Test Coverage
| Test File | Tests | Covers |
|---|---|---|
| [test_base62.py](file:///f:/Projects/URL1/tests/test_base62.py) | 11 | encode/decode, round-trips, edge cases |
| [test_api.py](file:///f:/Projects/URL1/tests/test_api.py) | 15 | all endpoints, error cases, validation |
| [test_integration.py](file:///f:/Projects/URL1/tests/test_integration.py) | 4 | full pipeline with real DB + Redis |

---

## Swagger UI

Interactive API docs available at: **http://localhost:8000/docs**
ReDoc: **http://localhost:8000/redoc**

---

## Security Features

- ✅ Blocks [localhost](file:///f:/Projects/URL1/tests/test_api.py#39-44), `127.0.0.1`, `::1`, and all RFC 1918 private IPs
- ✅ Enforces `http/https` scheme only
- ✅ Max URL length: 2048 chars
- ✅ Custom alias: 3-20 alphanumeric chars only
- ✅ Per-IP rate limiting: 60 req/min (sliding window via Redis)
- ✅ Negative cache: prevents repeated DB queries for non-existent codes
- ✅ Late ACK on Celery tasks: no event lost on worker crash
