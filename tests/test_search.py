import pytest
from unittest.mock import patch
from app.scrapers.base import ScraperUnavailableError


def test_search_requires_auth(client):
    resp = client.get("/search?name=Smith&state=CA")
    assert resp.status_code == 401


def test_search_ca_free_tier(client, free_headers, mock_search_results):
    with patch("app.routers.search.search_licenses", return_value=mock_search_results):
        resp = client.get("/search?name=Smith&state=CA", headers=free_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "CA"
    assert data["query"] == "Smith"
    assert len(data["results"]) == 2
    assert data["total_results"] == 2
    assert "searched_at" in data


def test_search_tx_blocked_on_free_tier(client, free_headers):
    resp = client.get("/search?name=Smith&state=TX", headers=free_headers)
    assert resp.status_code == 403


def test_search_tx_on_basic_tier(client, basic_headers, mock_search_results):
    with patch("app.routers.search.search_licenses", return_value=mock_search_results):
        resp = client.get("/search?name=Smith&state=TX", headers=basic_headers)
    assert resp.status_code == 200


def test_search_fl_on_pro_tier(client, pro_headers, mock_search_results):
    with patch("app.routers.search.search_licenses", return_value=mock_search_results):
        resp = client.get("/search?name=Smith&state=FL", headers=pro_headers)
    assert resp.status_code == 200


def test_search_ny_returns_501(client, enterprise_headers):
    resp = client.get("/search?name=Smith&state=NY", headers=enterprise_headers)
    assert resp.status_code == 501


def test_search_invalid_state(client, pro_headers):
    resp = client.get("/search?name=Smith&state=ZZ", headers=pro_headers)
    assert resp.status_code == 422


def test_search_missing_name(client, pro_headers):
    resp = client.get("/search?state=CA", headers=pro_headers)
    assert resp.status_code == 422


def test_search_limit_enforced(client, pro_headers):
    large_results = [
        {"license_number": str(i), "business_name": f"Co {i}", "status": "Active",
         "license_type": "General", "expiration_date": "2027-01-01"}
        for i in range(30)
    ]
    with patch("app.routers.search.search_licenses", return_value=large_results):
        resp = client.get("/search?name=Smith&state=CA&limit=5", headers=pro_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) <= 5


def test_search_limit_max_50(client, pro_headers):
    resp = client.get("/search?name=Smith&state=CA&limit=100", headers=pro_headers)
    # FastAPI validates ge/le constraints — returns 422
    assert resp.status_code == 422


def test_search_scraper_unavailable(client, pro_headers):
    with patch("app.routers.search.search_licenses", side_effect=ScraperUnavailableError("Down")):
        resp = client.get("/search?name=Smith&state=CA", headers=pro_headers)
    assert resp.status_code == 503


def test_search_empty_results(client, pro_headers):
    with patch("app.routers.search.search_licenses", return_value=[]):
        resp = client.get("/search?name=NoOneByThisName&state=CA", headers=pro_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == []
    assert data["total_results"] == 0


def test_search_result_item_structure(client, pro_headers, mock_search_results):
    with patch("app.routers.search.search_licenses", return_value=mock_search_results):
        resp = client.get("/search?name=Smith&state=CA", headers=pro_headers)
    data = resp.json()
    for item in data["results"]:
        assert "license_number" in item
        assert "status" in item
