from pydantic import BaseModel, ConfigDict
from typing import Dict, List, Optional, Any
from datetime import datetime


class LicenseDetail(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "license_number": "1087351",
            "state": "CA",
            "status": "Active",
            "expiration_date": "2026-06-30",
            "license_type": "General Building (B)",
            "business_name": "SMITH CONSTRUCTION INC",
            "owner_name": "JOHN SMITH",
            "address": "123 MAIN ST, LOS ANGELES CA 90001",
            "disciplinary_actions": [],  # null for TX (not supported); [] or populated list for CA/FL
            "verified_at": "2024-01-15T18:30:00Z",
            "source_url": "https://www.cslb.ca.gov/OnlineServices/CheckLicense/LicenseDetail.aspx?LicNum=1087351",
            "cache_hit": False,
        }
    })

    license_number: str
    state: str
    status: Optional[str] = None
    expiration_date: Optional[str] = None
    license_type: Optional[str] = None
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    address: Optional[str] = None
    disciplinary_actions: Optional[List[str]] = None
    verified_at: datetime
    source_url: str
    cache_hit: bool = False


class SearchResultItem(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "license_number": "1087351",
            "business_name": "SMITH CONSTRUCTION INC",
            "owner_name": "JOHN SMITH",
            "status": "Active",
            "license_type": "General Building (B)",
            "expiration_date": "2026-06-30",
        }
    })

    license_number: str
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    status: Optional[str] = None
    license_type: Optional[str] = None
    expiration_date: Optional[str] = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "state": "CA",
            "query": "Smith Construction",
            "results": [
                {
                    "license_number": "1087351",
                    "business_name": "SMITH CONSTRUCTION INC",
                    "owner_name": "JOHN SMITH",
                    "status": "Active",
                    "license_type": "General Building (B)",
                    "expiration_date": "2026-06-30",
                }
            ],
            "total_results": 1,
            "searched_at": "2024-01-15T18:30:00Z",
        }
    })

    state: str
    query: str
    results: List[SearchResultItem]
    total_results: int
    searched_at: datetime


class StateInfo(BaseModel):
    code: str
    name: str
    agency: str
    license_types: List[str]
    status: str
    source_url: str


class StatesResponse(BaseModel):
    supported_states: List[StateInfo]


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "ok",
            "version": "1.0.0",
            "uptime_seconds": 3641.87,
            "states": {
                "CA": "healthy",
                "TX": "healthy",
                "FL": "healthy",
                "NY": "coming_soon",
            },
            "checked_at": "2024-01-15T18:30:00Z",
        }
    })

    status: str
    version: str
    uptime_seconds: float
    states: Dict[str, str]
    checked_at: datetime
