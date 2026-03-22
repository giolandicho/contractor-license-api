import threading
import pybreaker
from app.scrapers.ca import CAScraper
from app.scrapers.tx import TXScraper
from app.scrapers.fl import FLScraper
from app.scrapers.base import ScraperUnavailableError, LicenseNotFoundError
from app.cache.ttl_cache import (
    get_cached_verification,
    set_cached_verification,
    get_stale_verification,
    get_cached_search,
    set_cached_search,
    get_stale_search,
)
from app.cache.state_status import record_success, record_failure
from app.circuit_breaker import _breakers

_scrapers = {
    "CA": CAScraper(),
    "TX": TXScraper(),
    "FL": FLScraper(),
}

# Per-state concurrency limits. acquire(blocking=False) fails immediately when exhausted,
# returning 503 rather than queuing threads indefinitely.
_semaphores = {
    "CA": threading.Semaphore(5),
    "TX": threading.Semaphore(5),
    "FL": threading.Semaphore(5),
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
    breaker = _breakers.get(state.upper())
    sem = _semaphores.get(state.upper())

    if sem and not sem.acquire(blocking=False):
        stale = get_stale_verification(cache_key)
        if stale:
            return {**stale, "cache_hit": True, "data_freshness": "stale"}
        raise ScraperUnavailableError(
            f"{state} is handling too many concurrent requests. Try again in a moment.",
            error_code="concurrency_limit",
        )
    try:
        if breaker:
            result = breaker.call(scraper.verify, license_number)
        else:
            result = scraper.verify(license_number)
    except pybreaker.CircuitBreakerError:
        record_failure(state)
        stale = get_stale_verification(cache_key)
        if stale:
            return {**stale, "cache_hit": True, "data_freshness": "stale"}
        raise ScraperUnavailableError(
            f"{state} scraper circuit open — too many recent failures. Retrying in 30s.",
            error_code="circuit_open",
        )
    except ScraperUnavailableError:
        record_failure(state)
        stale = get_stale_verification(cache_key)
        if stale:
            return {**stale, "cache_hit": True, "data_freshness": "stale"}
        raise
    except Exception:
        record_failure(state)
        raise
    finally:
        if sem:
            sem.release()

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
    breaker = _breakers.get(state.upper())
    sem = _semaphores.get(state.upper())

    if sem and not sem.acquire(blocking=False):
        stale = get_stale_search(cache_key)
        if stale is not None:
            return stale[:limit]
        raise ScraperUnavailableError(
            f"{state} is handling too many concurrent requests. Try again in a moment.",
            error_code="concurrency_limit",
        )
    try:
        if breaker:
            results = breaker.call(scraper.search, name, limit)
        else:
            results = scraper.search(name, limit)
    except pybreaker.CircuitBreakerError:
        record_failure(state)
        stale = get_stale_search(cache_key)
        if stale is not None:
            return stale[:limit]
        raise ScraperUnavailableError(
            f"{state} scraper circuit open — too many recent failures. Retrying in 30s.",
            error_code="circuit_open",
        )
    except ScraperUnavailableError:
        record_failure(state)
        stale = get_stale_search(cache_key)
        if stale is not None:
            return stale[:limit]
        raise
    except Exception:
        record_failure(state)
        raise
    finally:
        if sem:
            sem.release()

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
