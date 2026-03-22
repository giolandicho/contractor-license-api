import pytest
from unittest.mock import patch
from app.scrapers.base import LicenseNotFoundError, ScraperUnavailableError


def test_verify_requires_auth(client):
    resp = client.get("/verify?license_number=1082000&state=CA")
    assert resp.status_code == 401


def test_verify_ca_free_tier(client, free_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=free_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["license_number"] == "1082000"
    assert data["state"] == "CA"
    assert data["status"] == "Active"
    assert "verified_at" in data
    assert "source_url" in data
    assert "cache_hit" in data


def test_verify_tx_blocked_on_free_tier(client, free_headers):
    resp = client.get("/verify?license_number=TACLA12345E&state=TX", headers=free_headers)
    assert resp.status_code == 403
    assert "upgrade" in resp.json()["detail"].lower()


def test_verify_fl_blocked_on_basic_tier(client, basic_headers):
    resp = client.get("/verify?license_number=CGC1234567&state=FL", headers=basic_headers)
    assert resp.status_code == 403


def test_verify_tx_on_basic_tier(client, basic_headers, mock_tx_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_tx_verify):
        resp = client.get("/verify?license_number=TACLA12345E&state=TX", headers=basic_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "TX"


def test_verify_fl_on_pro_tier(client, pro_headers, mock_fl_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_fl_verify):
        resp = client.get("/verify?license_number=CGC1234567&state=FL", headers=pro_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "FL"


def test_verify_all_states_on_enterprise(client, enterprise_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=enterprise_headers)
    assert resp.status_code == 200


def test_verify_ny_returns_501(client, enterprise_headers):
    resp = client.get("/verify?license_number=12345&state=NY", headers=enterprise_headers)
    assert resp.status_code == 501
    assert "coming soon" in resp.json()["detail"].lower()


def test_verify_license_not_found(client, pro_headers):
    with patch("app.routers.verify.verify_license", side_effect=LicenseNotFoundError("Not found")):
        resp = client.get("/verify?license_number=9999999&state=CA", headers=pro_headers)
    assert resp.status_code == 404


def test_verify_scraper_unavailable(client, pro_headers):
    with patch("app.routers.verify.verify_license", side_effect=ScraperUnavailableError("Down")):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 503


def test_verify_invalid_state(client, pro_headers):
    resp = client.get("/verify?license_number=1082000&state=ZZ", headers=pro_headers)
    assert resp.status_code == 422


def test_verify_missing_license_number(client, pro_headers):
    resp = client.get("/verify?state=CA", headers=pro_headers)
    assert resp.status_code == 422


def test_verify_cache_hit_field(client, pro_headers, mock_ca_verify):
    cached = dict(mock_ca_verify)
    cached["cache_hit"] = True
    with patch("app.routers.verify.verify_license", return_value=cached):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 200
    # cache_hit comes from the result dict
    data = resp.json()
    assert "cache_hit" in data


def test_verify_response_has_all_fields(client, pro_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    data = resp.json()
    for field in ["license_number", "state", "status", "expiration_date", "license_type",
                  "business_name", "owner_name", "address", "disciplinary_actions",
                  "disciplinary_actions_available", "bond_status", "bond_amount",
                  "bond_expiration", "workers_comp_status", "workers_comp_expiration",
                  "data_freshness", "verified_at", "source_url", "cache_hit"]:
        assert field in data, f"Missing field: {field}"


def test_verify_ca_bond_and_workers_comp_fields(client, pro_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["bond_status"] == "Bonded"
    assert data["bond_amount"] == "$15,000"
    assert data["bond_expiration"] == "2027-01-01"
    assert data["workers_comp_status"] == "Insured"
    assert data["workers_comp_expiration"] == "2026-12-31"


def test_verify_tx_bond_fields_are_null(client, basic_headers, mock_tx_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_tx_verify):
        resp = client.get("/verify?license_number=TACLA12345E&state=TX", headers=basic_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["bond_status"] is None
    assert data["workers_comp_status"] is None


def test_verify_fl_bond_fields_are_null(client, pro_headers, mock_fl_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_fl_verify):
        resp = client.get("/verify?license_number=CGC1234567&state=FL", headers=pro_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["bond_status"] is None
    assert data["workers_comp_status"] is None


def test_verify_stale_fallback_returns_200(client, pro_headers, mock_ca_verify):
    stale = dict(mock_ca_verify)
    stale["data_freshness"] = "stale"
    with patch("app.routers.verify.verify_license", return_value=stale):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_freshness"] == "stale"
    assert data["license_number"] == "1082000"


def test_verify_fresh_scrape_has_null_data_freshness(client, pro_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 200
    assert resp.json()["data_freshness"] is None


def test_verify_503_includes_error_code(client, pro_headers):
    from app.scrapers.base import ScraperUnavailableError as SUE
    err = SUE("circuit open", error_code="circuit_open")
    with patch("app.routers.verify.verify_license", side_effect=err):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 503
    data = resp.json()
    assert data["error_code"] == "circuit_open"
    assert "detail" in data


def test_verify_503_concurrency_error_code(client, pro_headers):
    from app.scrapers.base import ScraperUnavailableError as SUE
    err = SUE("too many concurrent requests", error_code="concurrency_limit")
    with patch("app.routers.verify.verify_license", side_effect=err):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 503
    assert resp.json()["error_code"] == "concurrency_limit"


def test_verify_503_maintenance_error_code(client, pro_headers):
    from app.scrapers.base import ScraperUnavailableError as SUE
    err = SUE("CSLB offline for maintenance", error_code="maintenance_window")
    with patch("app.routers.verify.verify_license", side_effect=err):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=pro_headers)
    assert resp.status_code == 503
    assert resp.json()["error_code"] == "maintenance_window"
