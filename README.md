<div align="center">

<img src="https://img.shields.io/badge/SnapLink-URL%20Shortener-6C63FF?style=for-the-badge&logo=link&logoColor=white" alt="SnapLink"/>

# SnapLink ⚡

### Production-Grade Distributed URL Shortener

**A blazing-fast, async URL shortener built with FastAPI & MongoDB — featuring analytics, QR codes, link management, and social previews out of the box.**

<br/>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248?style=flat-square&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![API Docs](https://img.shields.io/badge/API-Swagger%20UI-85EA2D?style=flat-square&logo=swagger&logoColor=black)](http://localhost:8000/docs)
[![Deploy on Render](https://img.shields.io/badge/Deploy-Render-46E3B7?style=flat-square&logo=render&logoColor=white)](https://render.com)

<br/>

[Features](#-features) • [Tech Stack](#%EF%B8%8F-tech-stack) • [Quick Start](#-quick-start) • [API Reference](#-api-reference) • [Deployment](#-deployment) • [Contributing](#-contributing)

</div>

---

## 📖 Overview

**SnapLink** is a self-hostable, production-ready URL shortener engineered for performance and scale. Built on a fully asynchronous Python stack, it replaces the complexity of traditional Redis/Celery/PostgreSQL setups with a single, unified **MongoDB** backend — achieving lower latency with fewer moving parts.

Every component, from ID generation to analytics ingestion, is designed to be non-blocking. Short URLs are generated using a **Snowflake-inspired distributed ID algorithm** encoded in Base62, guaranteeing global uniqueness across horizontally scaled deployments.

---

## ✨ Features

| Feature | Description |
|---|---|
| ⚡ **Instant Redirects** | Fully async redirect pipeline with in-process MongoDB document caching |
| 🔑 **Snowflake ID + Base62** | Distributed, collision-free short code generation — no counters, no locking |
| 📊 **Rich Analytics** | Click counts, geolocation (country/city), referrers, device & browser breakdown |
| 🖥️ **Built-in Dashboard** | Manage all your links and view live stats from an integrated web UI |
| 🔐 **JWT Authentication** | Secure bcrypt password hashing and signed JWT tokens for protected endpoints |
| 🛡️ **Rate Limiting** | Configurable per-IP rate limits to protect against abuse |
| 📱 **QR Code Generation** | On-demand PNG QR codes for any shortened link |
| 🔗 **Social Preview Cards** | Auto-generated Open Graph meta-tag previews for rich social sharing |
| 📦 **Bulk Shortening** | Shorten dozens of URLs in a single API call |
| 🐳 **Docker-First** | One-command local stack with Docker Compose; Render Blueprint for cloud |

---

## 🛠️ Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        SnapLink v3.0                        │
├──────────────────┬──────────────────┬───────────────────────┤
│   Web Framework  │    Database      │     Auth & Security   │
│   FastAPI 0.111  │   MongoDB 7.0    │   JWT + bcrypt        │
│   Uvicorn (ASGI) │   Motor (async)  │   PyJWT + passlib     │
├──────────────────┼──────────────────┼───────────────────────┤
│   ID Generation  │   HTTP Client    │   Utilities           │
│   Snowflake algo │   httpx          │   qrcode, Pillow      │
│   Base62 encode  │   (geo-lookup)   │   user-agents, pydantic│
└──────────────────┴──────────────────┴───────────────────────┘
```

| Layer | Technology |
|---|---|
| **Runtime** | Python 3.10+, Uvicorn (ASGI) |
| **Framework** | FastAPI 0.111 |
| **Database** | MongoDB 7.0 via `motor` async driver |
| **Auth** | JWT (`PyJWT 2.8`), password hashing (`passlib[bcrypt]`) |
| **Config** | `pydantic-settings`, `python-dotenv` |
| **QR Codes** | `qrcode[pil]`, `Pillow` |
| **Analytics** | `httpx` (geo-lookup), `user-agents` (UA parsing) |
| **Testing** | `pytest`, `pytest-asyncio`, `httpx` |
| **Deployment** | Docker, Docker Compose, Render |

---

## 🚀 Quick Start

### Prerequisites

- **Python** 3.10 or higher
- **MongoDB** 7.0+ (local or [MongoDB Atlas](https://www.mongodb.com/cloud/atlas))
- **Docker & Docker Compose** *(optional — recommended for fastest setup)*

---

### Option A: Docker Compose *(Recommended)*

Spin up the full stack (API + MongoDB) with a single command — no Python environment setup needed.

```bash
# 1. Clone the repository
git clone https://github.com/JKBYTEcrafter/SnapLink.git
cd SnapLink

# 2. Launch all services
docker-compose up -d --build
```

| Service | URL |
|---|---|
| API & Dashboard | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health Check | http://localhost:8000/health |

---

### Option B: Local Development

```bash
# 1. Clone the repository
git clone https://github.com/JKBYTEcrafter/SnapLink.git
cd SnapLink

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env — set MONGODB_URL to your instance

# 5. Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### Environment Variables

Copy `.env.example` to `.env` and configure the following:

| Variable | Required | Default | Description |
|---|---|---|---|
| `MONGODB_URL` | ✅ | — | MongoDB connection string (local or Atlas URI) |
| `SECRET_KEY` | ✅ | — | Strong random string for JWT signing |
| `BASE_URL` | ✅ | `http://localhost:8000` | Public base URL for generated short links |
| `ENVIRONMENT` | ❌ | `development` | `development` or `production` |
| `RATE_LIMIT_MAX_REQUESTS` | ❌ | `60` | Max requests per window per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | ❌ | `60` | Rate limit window in seconds |
| `CACHE_DEFAULT_TTL` | ❌ | `3600` | In-process cache TTL in seconds |
| `MACHINE_ID` | ❌ | `1` | Node ID for Snowflake ID generator (0–1023) |

---

## 📁 Project Structure

```
SnapLink/
├── app/
│   ├── config.py           # Pydantic settings (env-var binding)
│   ├── main.py             # FastAPI app factory, lifespan, routers
│   ├── database/
│   │   └── database.py     # Motor client, index creation, lifecycle
│   ├── routes/
│   │   ├── url_routes.py       # POST /shorten  •  GET /{code}
│   │   ├── analytics_routes.py # GET /analytics/{code}
│   │   ├── auth_routes.py      # POST /auth/register  •  POST /auth/token
│   │   ├── management_routes.py# GET /links  •  DELETE /links/{code}
│   │   ├── qr_routes.py        # GET /qr/{code}
│   │   └── preview_routes.py   # GET /preview/{code}
│   ├── services/
│   │   ├── url_service.py      # Core URL creation & redirect logic
│   │   ├── auth_service.py     # JWT issuance & verification
│   │   └── cache_service.py    # In-process document cache
│   ├── schemas/                # Pydantic request/response models
│   ├── utils/
│   │   ├── id_generator.py     # Snowflake-inspired distributed ID gen
│   │   ├── base62.py           # Base62 encoder/decoder
│   │   └── ip_tracker.py       # GeoIP lookup via httpx
│   └── static/
│       ├── index.html          # Landing page & shortener UI
│       └── dashboard.html      # Link management dashboard
├── docker/
│   └── Dockerfile.api          # Production-hardened multi-stage image
├── tests/                      # pytest async test suite
├── .env.example                # Environment variable template
├── docker-compose.yml          # Local full-stack (API + MongoDB)
├── render.yaml                 # Render.com Blueprint for cloud deploy
├── pytest.ini                  # Test configuration
└── requirements.txt            # Pinned Python dependencies
```

---

## 📖 API Reference

Interactive documentation is auto-generated by FastAPI:

- **Swagger UI** → [`/docs`](http://localhost:8000/docs)
- **ReDoc** → [`/redoc`](http://localhost:8000/redoc)

### Endpoints at a Glance

#### 🔗 URL Operations

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/shorten` | Optional | Shorten a single URL (supports custom alias & expiry) |
| `POST` | `/shorten/bulk` | ✅ JWT | Shorten multiple URLs in one request |
| `GET` | `/{code}` | — | Redirect to the original URL |

#### 📊 Analytics

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/analytics/{code}` | ✅ JWT | Clicks, geo, referrer & device breakdown |

#### 🖥️ Link Management

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/links` | ✅ JWT | List all links for the authenticated user |
| `DELETE` | `/links/{code}` | ✅ JWT | Delete a short link |

#### 📱 QR & Previews

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/qr/{code}` | — | Returns a PNG QR code image |
| `GET` | `/preview/{code}` | — | Returns Open Graph HTML preview card |

#### 🔐 Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user account |
| `POST` | `/auth/token` | Obtain a JWT access token |

#### ⚙️ System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe — returns `{"status": "ok"}` |

---

### Example: Shorten a URL

```bash
curl -X POST http://localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.example.com/very/long/path"}'
```

**Response:**
```json
{
  "short_url": "http://localhost:8000/aB3xZ9",
  "code": "aB3xZ9",
  "original_url": "https://www.example.com/very/long/path",
  "created_at": "2025-01-15T10:30:00Z"
}
```

---

## 🧪 Testing

The test suite uses `pytest` with async support via `pytest-asyncio`.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_url_routes.py
```

> **Note:** Configure a test MongoDB instance or mock the database layer as per `pytest.ini` settings before running tests.

---

## 🚢 Deployment

### Deploy to Render *(Free tier supported)*

SnapLink ships with a `render.yaml` Blueprint for zero-config cloud deployment:

1. Fork this repository
2. Connect your fork to [Render](https://render.com)
3. Import the Blueprint — Render will detect `render.yaml` automatically
4. Set the **`MONGODB_URL`** environment variable in the Render dashboard (point it to your [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) cluster)
5. Deploy — your service will be live in minutes

### Production Checklist

- [ ] Set a strong, unique `SECRET_KEY` (minimum 32 characters)
- [ ] Use a managed MongoDB Atlas cluster with appropriate tier
- [ ] Set `ENVIRONMENT=production` to enable INFO-level logging
- [ ] Configure `BASE_URL` to your real domain (e.g., `https://snap.yourdomain.com`)
- [ ] Adjust `RATE_LIMIT_MAX_REQUESTS` to suit your traffic expectations
- [ ] Set unique `MACHINE_ID` per replica for distributed ID uniqueness
- [ ] Enable HTTPS at the reverse proxy / CDN layer

---

## 🤝 Contributing

Contributions are welcome! Please follow this workflow:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/your-feature`
3. **Commit** your changes: `git commit -m "feat: add your feature"`
4. **Push** to your fork: `git push origin feat/your-feature`
5. **Open** a Pull Request against `main`

Please ensure all new features include corresponding tests and that `pytest` passes before submitting.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built with ❤️ by [JKBYTEcrafter](https://github.com/JKBYTEcrafter)

⭐ If you find SnapLink useful, please consider giving it a star!

</div>
