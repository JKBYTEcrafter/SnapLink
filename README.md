# SnapLink

A production-grade, highly scalable distributed URL shortener built with FastAPI and MongoDB. SnapLink provides lightning-fast redirection, robust analytics, QR code generation, bulk shortening, and an integrated link management dashboard.

## 🌟 Features

- **Blazing Fast Redirection**: Leveraging asynchronous Python and MongoDB for optimal performance.
- **Robust Base62 Encoding**: Generates short, unique URLs using a distributed Snowflake-inspired ID generator.
- **Comprehensive Analytics**: Tracks click counts, geographic location, referrers, and user-agents (device/browser) asynchronously.
- **Integrated Dashboard**: Manage links, view real-time statistics, and generate QR codes via a built-in web interface.
- **Security & Rate Limiting**: Built-in rate limiting and secure JWT-based authentication for the management API.
- **Social Previews**: Automatically generates rich link previews (Open Graph) for social media sharing.
- **Docker Ready**: Easy deployment with Docker and Docker Compose.
- **Bulk Operations**: Shorten multiple URLs in a single request.

## 🛠️ Technology Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn
- **Database**: MongoDB (via `motor` asynchronous driver)
- **Authentication**: JWT (JSON Web Tokens), `passlib` with bcrypt
- **Tools**: `qrcode` (QR Code generation), `httpx` (Geolocation lookup), `user-agents` (parsing)

*Note: SnapLink recently migrated from a PostgreSQL/Redis/Celery stack to a unified, high-performance MongoDB architecture for simplified deployment and lower latency.*

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- MongoDB 7.0+
- Docker & Docker Compose (optional, for containerized deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/JKBYTEcrafter/SnapLink.git
   cd SnapLink
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Copy the example `.env` file and adjust the values as needed.
   ```bash
   cp .env.example .env
   ```
   *Make sure `MONGODB_URL` points to your running MongoDB instance.*

5. **Run the FastAPI server**
   ```bash
   uvicorn app.main:app --reload
   ```
   The application will be available at `http://localhost:8000`.

### 🐳 Docker Deployment

The easiest way to run SnapLink is using Docker Compose, which will spin up the FastAPI server and a MongoDB container.

```bash
docker-compose up -d --build
```

Access the API at `http://localhost:8000` and the interactive API documentation at `http://localhost:8000/docs`.

## 📁 Project Structure

```text
SnapLink/
├── app/
│   ├── database/       # MongoDB initialization and operations
│   ├── routes/         # API endpoint definitions (auth, urls, analytics)
│   ├── services/       # Core business logic (URL, cache, auth)
│   ├── static/         # Frontend HTML/CSS/JS (Dashboard)
│   ├── utils/          # Helpers (Base62, ID generation, IP tracking)
│   ├── config.py       # Pydantic environment configuration
│   └── main.py         # FastAPI application entry point
├── docker/             # Dockerfiles for deployment
├── tests/              # Pytest test suite
├── .env.example        # Environment variables template
├── docker-compose.yml  # Multi-container Docker setup
└── requirements.txt    # Python dependencies
```

## 📖 API Documentation

Once the server is running, FastAPI provides interactive API documentation automatically. You can view it by navigating to:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Core Endpoints

- `POST /shorten` - Create a new short URL
- `GET /{code}` - Redirect to original URL
- `GET /analytics/{code}` - View statistics for a specific link
- `GET /qr/{code}` - Generate a QR code for the short link
- `POST /auth/token` - Authenticate and receive a JWT

## 🧪 Testing

To run the automated tests, simply execute:

```bash
pytest
```
Ensure you have a test MongoDB database configured or mock it appropriately as per the test settings.

## 📝 License

This project is licensed under the MIT License.
