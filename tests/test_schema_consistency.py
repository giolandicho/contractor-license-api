"""
Schema consistency tests: assert that all three states return identical field shapes,
correct types, and documented semantic contracts (e.g. disciplinary_actions nullability).
"""
import re
import pytest
from unittest.mock import patch
from app.scrapers.base import normalize_date

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

VERIFY_REQUIRED_FIELDS = {
    "license_number", "state", "status", "expiration_date", "license_type",
    "business_name", "owner_name", "address", "disciplinary_actions",
    "disciplinary_actions_available", "verified_at", "source_url", "cache_hit",
}

SEARCH_ITEM_REQUIRED_FIELDS = {
    "license_number", "business_name", "owner_name", "status",
    "license_type", "expiration_date",
}


# ---------------------------------------------------------------------------
# Verify endpoint — field shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state,license_number,fixture_name,scraper_path", [
    ("CA", "1082000", "mock_ca_verify", "app.routers.verify.verify_license"),
    ("TX", "TACLA12345E", "mock_tx_verify", "app.routers.verify.verify_license"),
    ("FL", "CGC1234567", "mock_fl_verify", "app.routers.verify.verify_license"),
])
def test_verify_response_fields_consistent(
    client, enterprise_headers, request, state, license_number, fixture_name, scraper_path
):
    mock_data = request.getfixturevalue(fixture_name)
    with patch(scraper_path, return_value=mock_data):
        resp = client.get(f"/verify?license_number={license_number}&state={state}", headers=enterprise_headers)
    assert resp.status_code == 200
    data = resp.json()
    missing = VERIFY_REQUIRED_FIELDS - set(data.keys())
    assert not missing, f"State {state} response missing fields: {missing}"


# ---------------------------------------------------------------------------
# Verify endpoint — field types
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state,license_number,fixture_name", [
    ("CA", "1082000", "mock_ca_verify"),
    ("TX", "TACLA12345E", "mock_tx_verify"),
    ("FL", "CGC1234567", "mock_fl_verify"),
])
def test_verify_field_types(client, enterprise_headers, request, state, license_number, fixture_name):
    mock_data = request.getfixturevalue(fixture_name)
    with patch("app.routers.verify.verify_license", return_value=mock_data):
        resp = client.get(f"/verify?license_number={license_number}&state={state}", headers=enterprise_headers)
    data = resp.json()
    assert isinstance(data["license_number"], str)
    assert isinstance(data["state"], str)
    assert isinstance(data["cache_hit"], bool)
    assert isinstance(data["source_url"], str)
    assert isinstance(data["verified_at"], str)
    # Optional string fields must be str or null
    for field in ("status", "license_type", "business_name", "owner_name", "address"):
        assert data[field] is None or isinstance(data[field], str), \
            f"State {state}: field '{field}' must be str or null, got {type(data[field])}"
    # expiration_date must be ISO 8601 (YYYY-MM-DD) or null
    exp = data["expiration_date"]
    assert exp is None or ISO_DATE_RE.match(exp), \
        f"State {state}: expiration_date '{exp}' is not ISO 8601 (YYYY-MM-DD)"


# ---------------------------------------------------------------------------
# disciplinary_actions semantics
# ---------------------------------------------------------------------------

def test_disciplinary_actions_is_list_for_ca(client, enterprise_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=enterprise_headers)
    data = resp.json()
    assert isinstance(data["disciplinary_actions"], list), \
        "CA disciplinary_actions must be a list ([] when none on record)"


def test_disciplinary_actions_is_list_for_fl(client, enterprise_headers, mock_fl_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_fl_verify):
        resp = client.get("/verify?license_number=CGC1234567&state=FL", headers=enterprise_headers)
    data = resp.json()
    assert isinstance(data["disciplinary_actions"], list), \
        "FL disciplinary_actions must be a list ([] when none on record)"


def test_disciplinary_actions_is_null_for_tx(client, enterprise_headers, mock_tx_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_tx_verify):
        resp = client.get("/verify?license_number=TACLA12345E&state=TX", headers=enterprise_headers)
    data = resp.json()
    assert data["disciplinary_actions"] is None, \
        "TX disciplinary_actions must be null — TDLR does not expose disciplinary data"


def test_disciplinary_actions_available_true_for_ca(client, enterprise_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=enterprise_headers)
    data = resp.json()
    assert data["disciplinary_actions_available"] is True, \
        "CA disciplinary_actions_available must be True"


def test_disciplinary_actions_available_true_for_fl(client, enterprise_headers, mock_fl_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_fl_verify):
        resp = client.get("/verify?license_number=CGC1234567&state=FL", headers=enterprise_headers)
    data = resp.json()
    assert data["disciplinary_actions_available"] is True, \
        "FL disciplinary_actions_available must be True"


def test_disciplinary_actions_available_false_for_tx(client, enterprise_headers, mock_tx_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_tx_verify):
        resp = client.get("/verify?license_number=TACLA12345E&state=TX", headers=enterprise_headers)
    data = resp.json()
    assert data["disciplinary_actions_available"] is False, \
        "TX disciplinary_actions_available must be False — TDLR does not expose disciplinary data"


# ---------------------------------------------------------------------------
# Search endpoint — field shape
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state,scraper_path", [
    ("CA", "app.routers.search.search_licenses"),
    ("TX", "app.routers.search.search_licenses"),
    ("FL", "app.routers.search.search_licenses"),
])
def test_search_result_fields_consistent(
    client, enterprise_headers, mock_search_results, state, scraper_path
):
    with patch(scraper_path, return_value=mock_search_results):
        resp = client.get(f"/search?name=Smith&state={state}", headers=enterprise_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total_results" in data
    assert "state" in data
    assert "query" in data
    assert "searched_at" in data
    for item in data["results"]:
        missing = SEARCH_ITEM_REQUIRED_FIELDS - set(item.keys())
        assert not missing, f"State {state} search result missing fields: {missing}"


# ---------------------------------------------------------------------------
# X-Response-Time header
# ---------------------------------------------------------------------------

def test_response_time_header_present_on_verify(client, enterprise_headers, mock_ca_verify):
    with patch("app.routers.verify.verify_license", return_value=mock_ca_verify):
        resp = client.get("/verify?license_number=1082000&state=CA", headers=enterprise_headers)
    assert "x-response-time" in resp.headers, "X-Response-Time header must be present on all responses"
    assert resp.headers["x-response-time"].endswith("ms")


def test_response_time_header_present_on_health(client):
    resp = client.get("/health")
    assert "x-response-time" in resp.headers


# ---------------------------------------------------------------------------
# normalize_date unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("06/30/2026",      "2026-06-30"),   # MM/DD/YYYY — most common US gov format
    ("2026-06-30",      "2026-06-30"),   # already ISO 8601
    ("June 30, 2026",   "2026-06-30"),   # full month name
    ("Jun 30, 2026",    "2026-06-30"),   # abbreviated month
    ("06-30-2026",      "2026-06-30"),   # MM-DD-YYYY
    ("30-Jun-2026",     "2026-06-30"),   # DD-Mon-YYYY
    ("06/30/26",        "2026-06-30"),   # two-digit year
    ("",                None),           # empty string → None
    (None,              None),           # None → None
    ("not-a-date",      "not-a-date"),   # unrecognized → pass through unchanged
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected
