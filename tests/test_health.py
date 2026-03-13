from unittest.mock import patch


def test_health_returns_ok(client):
    with patch("app.routers.health.check_state_health", return_value="healthy"):
        resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "uptime_seconds" in data
    assert "states" in data
    assert "checked_at" in data


def test_health_includes_all_states(client):
    with patch("app.routers.health.check_state_health", return_value="healthy"):
        resp = client.get("/health")
    data = resp.json()
    states = data["states"]
    assert "CA" in states
    assert "TX" in states
    assert "FL" in states
    assert "NY" in states


def test_health_ny_always_coming_soon(client):
    with patch("app.routers.health.check_state_health", return_value="healthy"):
        resp = client.get("/health")
    data = resp.json()
    assert data["states"]["NY"] == "coming_soon"


def test_health_no_auth_required(client):
    with patch("app.routers.health.check_state_health", return_value="healthy"):
        resp = client.get("/health")
    assert resp.status_code == 200


def test_health_uptime_is_positive(client):
    with patch("app.routers.health.check_state_health", return_value="healthy"):
        resp = client.get("/health")
    data = resp.json()
    assert data["uptime_seconds"] >= 0
