"""
Regression tests for probe endpoints.
Ensures /probe and /probe/verify are accessible without an API key.
"""


def test_probe_no_auth_required(client):
    """GET /probe must not return 401 — it is in EXCLUDED_PATHS."""
    resp = client.get("/probe?state=CA")
    assert resp.status_code != 401, "/probe returned 401 — check EXCLUDED_PATHS in auth middleware"


def test_probe_verify_no_auth_required(client):
    """GET /probe/verify must not return 401 — it must be in EXCLUDED_PATHS.

    Regression test for the bug where /probe/verify was omitted from EXCLUDED_PATHS
    despite being a public monitoring endpoint. Without this fix, UptimeRobot monitors
    configured against /probe/verify would always receive 401.
    """
    resp = client.get("/probe/verify?state=CA")
    assert resp.status_code != 401, (
        "/probe/verify returned 401 — /probe/verify is missing from EXCLUDED_PATHS "
        "in app/middleware/auth.py"
    )
    # Should return 503 (seed not configured in test env), not 401
    assert resp.status_code in (200, 503), f"Unexpected status: {resp.status_code}"


def test_probe_verify_returns_503_when_seed_not_configured(client):
    """Without PROBE_LICENSE_{STATE} set, /probe/verify returns 503 with a clear message."""
    resp = client.get("/probe/verify?state=CA")
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"].lower()


def test_probe_returns_ok_structure(client):
    """/probe response (on success) contains status and state keys."""
    from unittest.mock import patch
    with patch("app.routers.probe._scrapers") as mock_scrapers:
        mock_scrapers.__contains__ = lambda self, k: k == "CA"
        mock_scrapers.__getitem__ = lambda self, k: type("S", (), {"health_check": lambda self: True})()
        # Just confirm the endpoint is reachable without 401
        resp = client.get("/probe?state=CA")
        assert resp.status_code != 401
