"""
Security hardening tests.
Covers request size limits, security response headers, and Retry-After on 429.
"""
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Request size limits
# ---------------------------------------------------------------------------

def test_oversized_content_length_rejected(client, enterprise_headers):
    """Requests with Content-Length > 32KB are rejected with 413 before reaching the app."""
    resp = client.post(
        "/verify",
        headers={**enterprise_headers, "Content-Length": "99999"},
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


def test_normal_content_length_allowed(client, enterprise_headers):
    """Requests with small or absent Content-Length pass through normally."""
    from app.scrapers.base import LicenseNotFoundError
    with patch("app.routers.verify.verify_license", side_effect=LicenseNotFoundError("not found")):
        resp = client.get("/verify?license_number=123&state=CA", headers=enterprise_headers)
    assert resp.status_code == 404  # reached the route handler


def test_oversized_query_string_rejected(client, enterprise_headers):
    """Requests with query strings > 2048 bytes are rejected with 400."""
    long_name = "A" * 3000
    resp = client.get(f"/search?name={long_name}&state=CA", headers=enterprise_headers)
    assert resp.status_code == 400
    assert "query string" in resp.json()["detail"].lower()


def test_normal_query_string_allowed(client, enterprise_headers):
    """Requests with query strings under 2KB pass through normally."""
    with patch("app.routers.search.search_licenses", return_value=[]):
        resp = client.get("/search?name=Smith+Construction&state=CA", headers=enterprise_headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Security response headers
# ---------------------------------------------------------------------------

def test_security_headers_on_health(client):
    resp = client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"


def test_security_headers_on_verify(client, enterprise_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=enterprise_headers)
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"


def test_security_headers_on_error_response(client):
    """Security headers must be present even on 401 error responses."""
    resp = client.get("/verify?license_number=123&state=CA")
    assert resp.status_code == 401
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


# ---------------------------------------------------------------------------
# Retry-After on 429
# ---------------------------------------------------------------------------

def test_rate_limit_429_has_retry_after():
    """All 429 responses from _rate_limit_handler must include Retry-After: 60."""
    import asyncio
    from unittest.mock import MagicMock
    from slowapi.errors import RateLimitExceeded
    from app.main import _rate_limit_handler

    # RateLimitExceeded requires a Limit-like object with .error_message and .detail
    mock_limit = MagicMock()
    mock_limit.error_message = None
    mock_limit.detail = "10 per 1 minute"
    mock_exc = RateLimitExceeded(mock_limit)

    mock_request = MagicMock()

    loop = asyncio.new_event_loop()
    response = loop.run_until_complete(_rate_limit_handler(mock_request, mock_exc))
    loop.close()

    assert response.status_code == 429
    assert "retry-after" in response.headers
    assert response.headers["retry-after"] == "60"
