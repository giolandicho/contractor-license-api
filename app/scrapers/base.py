from abc import ABC, abstractmethod
from typing import Optional


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
        import httpx
        try:
            from app.data.state_info import STATE_INFO
            url = STATE_INFO[self.state_code]["source_url"]
            resp = httpx.get(url, timeout=5.0, follow_redirects=True)
            return resp.status_code < 500
        except Exception:
            return False
