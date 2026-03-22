"""
Per-state circuit breakers for government portal scrapers.

Opens after 5 consecutive failures within a request window; half-opens after 30s.
LicenseNotFoundError is excluded — a 404 is a valid result, not a scraper failure.
"""
import pybreaker
from app.scrapers.base import LicenseNotFoundError

_breakers = {
    "CA": pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30, exclude=[LicenseNotFoundError]),
    "TX": pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30, exclude=[LicenseNotFoundError]),
    "FL": pybreaker.CircuitBreaker(fail_max=5, reset_timeout=30, exclude=[LicenseNotFoundError]),
}
