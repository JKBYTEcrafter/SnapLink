"""
IP geolocation helper using the free ipapi.co API.
Falls back gracefully on network or parsing errors.
"""
import logging

import httpx

logger = logging.getLogger(__name__)

_IPAPI_URL = "https://ipapi.co/{ip}/json/"
_TIMEOUT = 3.0  # seconds — must not block redirect path


async def get_geo_info(ip: str) -> dict[str, str | None]:
    """
    Fetch country and city for the given IP address.

    Returns a dict with keys 'country' and 'city'.
    Both values are None if the lookup fails or the IP is private.
    """
    if not ip or ip in ("127.0.0.1", "::1", "testclient"):
        return {"country": None, "city": None}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(_IPAPI_URL.format(ip=ip))
            response.raise_for_status()
            data = response.json()
            return {
                "country": data.get("country_name"),
                "city": data.get("city"),
            }
    except Exception as exc:
        logger.warning("Geo lookup failed for IP %s: %s", ip, exc)
        return {"country": None, "city": None}
