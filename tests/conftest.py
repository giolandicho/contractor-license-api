import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def configure_settings():
    settings.api_keys = "test-free-key"
    settings.basic_keys = "test-basic-key"
    settings.pro_keys = "test-pro-key"
    settings.enterprise_keys = "test-ent-key"
    settings.disabled_states = ""


@pytest.fixture(scope="session")
def client(configure_settings):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def free_headers():
    return {"X-API-Key": "test-free-key"}


@pytest.fixture
def basic_headers():
    return {"X-API-Key": "test-basic-key"}


@pytest.fixture
def pro_headers():
    return {"X-API-Key": "test-pro-key"}


@pytest.fixture
def enterprise_headers():
    return {"X-API-Key": "test-ent-key"}


@pytest.fixture
def mock_ca_verify():
    return {
        "license_number": "1082000",
        "state": "CA",
        "status": "Active",
        "expiration_date": "2026-06-30",
        "license_type": "General Building Contractor (B)",
        "business_name": "Acme Construction Inc",
        "owner_name": "John Smith",
        "address": "123 Main St, Los Angeles, CA 90001",
        "disciplinary_actions": [],
        "bond_status": "Bonded",
        "bond_amount": "$15,000",
        "bond_expiration": "2027-01-01",
        "workers_comp_status": "Insured",
        "workers_comp_expiration": "2026-12-31",
        "verified_at": "2026-03-12T10:00:00+00:00",
        "source_url": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx",
        "cache_hit": False,
    }


@pytest.fixture
def mock_tx_verify():
    return {
        "license_number": "TACLA12345E",
        "state": "TX",
        "status": "Active",
        "expiration_date": "2027-01-31",
        "license_type": "Air Conditioning and Refrigeration Contractor",
        "business_name": "Cool Air TX LLC",
        "owner_name": "Bob Johnson",
        "address": "456 Oak Ave, Austin, TX 78701",
        "disciplinary_actions": None,
        "verified_at": "2026-03-12T10:00:00+00:00",
        "source_url": "https://www.tdlr.texas.gov/LicenseSearch/",
        "cache_hit": False,
    }


@pytest.fixture
def mock_fl_verify():
    return {
        "license_number": "CGC1234567",
        "state": "FL",
        "status": "Active",
        "expiration_date": "2026-08-31",
        "license_type": "Certified General Contractor (CGC)",
        "business_name": "Sunshine Builders FL Inc",
        "owner_name": "Maria Garcia",
        "address": "789 Palm Ave, Miami, FL 33101",
        "disciplinary_actions": [],
        "verified_at": "2026-03-12T10:00:00+00:00",
        "source_url": "https://www.myfloridalicense.com/LicenseDetail.asp",
        "cache_hit": False,
    }


@pytest.fixture
def mock_search_results():
    return [
        {
            "license_number": "1082000",
            "business_name": "Smith Construction Inc",
            "owner_name": "John Smith",
            "status": "Active",
            "license_type": "General Building Contractor (B)",
            "expiration_date": "2026-06-30",
        },
        {
            "license_number": "9876543",
            "business_name": "Smith Electric Co",
            "owner_name": "Jane Smith",
            "status": "Active",
            "license_type": "Electrical (C-10)",
            "expiration_date": "2025-12-31",
        },
    ]
