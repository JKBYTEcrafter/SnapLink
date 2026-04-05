"""
API endpoint tests using the async test client.
"""
import pytest


@pytest.mark.asyncio
class TestShortenEndpoint:
    async def test_shorten_valid_url(self, client):
        response = await client.post("/shorten", json={"long_url": "https://www.google.com"})
        assert response.status_code == 201
        data = response.json()
        assert "short_code" in data
        assert "short_url" in data
        assert data["long_url"] == "https://www.google.com"
        assert data["qr_url"].endswith(f"/qr/{data['short_code']}")

    async def test_shorten_with_custom_alias(self, client):
        response = await client.post(
            "/shorten",
            json={"long_url": "https://www.github.com", "custom_alias": "gh-home"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["short_code"] == "gh-home"

    async def test_shorten_duplicate_alias_rejected(self, client):
        payload = {"long_url": "https://www.example.com", "custom_alias": "unique"}
        await client.post("/shorten", json=payload)
        # Second call with same alias should fail
        response = await client.post("/shorten", json=payload)
        assert response.status_code == 422
        assert "already taken" in response.json()["detail"]

    async def test_shorten_invalid_url_rejected(self, client):
        response = await client.post("/shorten", json={"long_url": "not-a-url"})
        assert response.status_code == 422

    async def test_shorten_localhost_rejected(self, client):
        response = await client.post(
            "/shorten", json={"long_url": "http://localhost/evil"}
        )
        assert response.status_code == 422

    async def test_shorten_private_ip_rejected(self, client):
        response = await client.post(
            "/shorten", json={"long_url": "http://192.168.1.1/path"}
        )
        assert response.status_code == 422

    async def test_shorten_invalid_alias_too_short(self, client):
        response = await client.post(
            "/shorten",
            json={"long_url": "https://www.example.com", "custom_alias": "ab"},
        )
        assert response.status_code == 422

    async def test_shorten_invalid_alias_special_chars(self, client):
        response = await client.post(
            "/shorten",
            json={"long_url": "https://www.example.com", "custom_alias": "bad alias!"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestRedirectEndpoint:
    async def test_redirect_returns_302(self, client):
        # Create short URL first
        create_resp = await client.post(
            "/shorten", json={"long_url": "https://www.python.org"}
        )
        short_code = create_resp.json()["short_code"]

        # Follow redirect (don't follow redirects to inspect status)
        response = await client.get(f"/{short_code}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == "https://www.python.org"

    async def test_redirect_nonexistent_returns_404(self, client):
        response = await client.get("/nonexistent-code", follow_redirects=False)
        assert response.status_code == 404

    async def test_redirect_custom_alias(self, client):
        await client.post(
            "/shorten",
            json={"long_url": "https://www.fastapi.tiangolo.com", "custom_alias": "fapi"},
        )
        response = await client.get("/fapi", follow_redirects=False)
        assert response.status_code == 302
        assert "fastapi" in response.headers["location"]


@pytest.mark.asyncio
class TestAnalyticsEndpoint:
    async def test_analytics_returns_data(self, client):
        create_resp = await client.post(
            "/shorten", json={"long_url": "https://www.wikipedia.org"}
        )
        short_code = create_resp.json()["short_code"]

        response = await client.get(f"/analytics/{short_code}")
        assert response.status_code == 200
        data = response.json()
        assert data["short_code"] == short_code
        assert data["long_url"] == "https://www.wikipedia.org"
        assert "total_clicks" in data
        assert "by_country" in data
        assert "by_device" in data

    async def test_analytics_nonexistent_returns_404(self, client):
        response = await client.get("/analytics/doesnotexist")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestQREndpoint:
    async def test_qr_returns_png(self, client):
        create_resp = await client.post(
            "/shorten", json={"long_url": "https://www.stackoverflow.com"}
        )
        short_code = create_resp.json()["short_code"]

        response = await client.get(f"/qr/{short_code}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        # PNG magic bytes: \x89PNG
        assert response.content[:4] == b"\x89PNG"

    async def test_qr_nonexistent_returns_404(self, client):
        response = await client.get("/qr/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
