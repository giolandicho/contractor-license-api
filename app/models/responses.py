from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime


class LicenseDetail(BaseModel):
    license_number: str
    state: str
    status: Optional[str] = None
    expiration_date: Optional[str] = None
    license_type: Optional[str] = None
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    address: Optional[str] = None
    disciplinary_actions: List[str] = []
    verified_at: datetime
    source_url: str
    cache_hit: bool = False


class SearchResultItem(BaseModel):
    license_number: str
    business_name: Optional[str] = None
    owner_name: Optional[str] = None
    status: Optional[str] = None
    license_type: Optional[str] = None
    expiration_date: Optional[str] = None


class SearchResponse(BaseModel):
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
    status: str
    version: str
    uptime_seconds: float
    states: dict
    checked_at: datetime
