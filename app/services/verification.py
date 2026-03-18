from datetime import datetime, timezone
from app.scrapers.ca import CAScraper
from app.scrapers.tx import TXScraper
from app.scrapers.fl import FLScraper
from app.scrapers.base import ScraperUnavailableError, LicenseNotFoundError
from app.cache.ttl_cache import (
    get_cached_verification,
    set_cached_verification,
    get_cached_search,
    set_cached_search,
)
from app.cache.state_status import record_success, record_failure

_scrapers = {
    "CA": CAScraper(),
    "TX": TXScraper(),
    "FL": FLScraper(),
}


def get_scraper(state: str):
    scraper = _scrapers.get(state.upper())
    if not scraper:
        raise ScraperUnavailableError(f"State {state} is not supported")
    return scraper


def verify_license(license_number: str, state: str) -> dict:
    cache_key = f"verify:{state.upper()}:{license_number.strip()}"
    cached = get_cached_verification(cache_key)
    if cached:
        result = dict(cached)
        result["cache_hit"] = True
        return result

    scraper = get_scraper(state)
    try:
        result = scraper.verify(license_number)
    except Exception:
        record_failure(state)
        raise
    record_success(state)
    set_cached_verification(cache_key, result)
    return result


def search_licenses(name: str, state: str, limit: int) -> list:
    normalized = name.strip().lower()
    cache_key = f"search:{state.upper()}:{normalized}"
    cached = get_cached_search(cache_key)
    if cached is not None:
        return cached[:limit]

    scraper = get_scraper(state)
    try:
        results = scraper.search(name, limit)
    except Exception:
        record_failure(state)
        raise
    record_success(state)
    set_cached_search(cache_key, results)
    return results


def check_state_health(state: str) -> str:
    scraper = _scrapers.get(state.upper())
    if not scraper:
        return "coming_soon"
    try:
        ok = scraper.health_check()
        return "healthy" if ok else "degraded"
    except Exception:
        return "degraded"
