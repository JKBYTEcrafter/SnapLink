"""
URL validation helpers.
"""
import ipaddress
import re
from urllib.parse import urlparse

BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
}

# Regex for a very minimal valid URL pattern (relies on urlparse for the rest)
_URL_REGEX = re.compile(
    r"^(https?://)?"          # scheme
    r"(\S+)"                  # rest
    r"$",
    re.IGNORECASE,
)


def _is_private_ip(host: str) -> bool:
    """Return True if host is a private / loopback / link-local IP address."""
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        return False


def validate_url(url: str) -> str:
    """
    Validate and normalise a URL.

    - Must have http or https scheme.
    - Must not point to localhost or private IP ranges.
    - Returns the normalised URL string.

    Raises:
        ValueError: With a descriptive message if the URL is invalid.
    """
    if not url or not url.strip():
        raise ValueError("URL must not be empty.")

    # Ensure scheme is present for parsing
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme '{parsed.scheme}'. Use http or https.")

    if not parsed.netloc:
        raise ValueError("URL must contain a valid host.")

    host = parsed.hostname or ""

    if host in BLOCKED_HOSTS or _is_private_ip(host):
        raise ValueError(f"URLs pointing to private/local addresses are not allowed: {host}")

    if len(url) > 2048:
        raise ValueError("URL exceeds maximum allowed length of 2048 characters.")

    return url.strip()
