import httpx
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

_DATE_FORMATS = [
    "%m/%d/%Y",    # 06/30/2026  — most common US government format
    "%Y-%m-%d",    # 2026-06-30  — already ISO, pass through
    "%B %d, %Y",   # June 30, 2026
    "%b %d, %Y",   # Jun 30, 2026
    "%m-%d-%Y",    # 06-30-2026
    "%d-%b-%Y",    # 30-Jun-2026
    "%m/%d/%y",    # 06/30/26    — two-digit year
]


def normalize_date(value):
    """
    Parse a date string from any common US government portal format and
    return an ISO 8601 string (YYYY-MM-DD). Returns None if the input is
    None/empty or does not match any recognized format.
    """
    if not value:
        return None
    cleaned = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None  # unrecognized format — null is safer than a non-ISO string


class ScraperUnavailableError(Exception):
    """Raised when the government portal is unreachable or returns unexpected HTML."""
    pass


class LicenseNotFoundError(Exception):
    """Raised when no license matching the query is found."""
    pass


class BaseScraper(ABC):
    state_code: str

    @abstractmethod
    def verify(self, license_number: str) -> dict:
        """Look up a single license by number. Returns a dict matching LicenseDetail fields."""
        ...

    @abstractmethod
    def search(self, name: str, limit: int) -> list:
        """Search licenses by name. Returns list of dicts matching SearchResultItem fields."""
        ...

    def health_check(self) -> bool:
        """Probe the source URL. Returns True if reachable."""
        try:
            from app.data.state_info import STATE_INFO
            url = STATE_INFO[self.state_code]["source_url"]
            resp = httpx.get(url, timeout=httpx.Timeout(5.0, connect=3.0, read=5.0), follow_redirects=True)
            return resp.status_code < 500
        except Exception:
            return False
