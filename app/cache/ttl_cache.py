import threading
from cachetools import TTLCache
from app.config import settings

_verify_cache = TTLCache(maxsize=1000, ttl=settings.cache_ttl_verify)
_search_cache = TTLCache(maxsize=500, ttl=settings.cache_ttl_search)

# Stale backing stores: retain the last-known results for up to 24 hours so that
# callers can receive degraded-but-valid data when a state portal is unavailable.
_verify_stale = TTLCache(maxsize=1000, ttl=86400)
_search_stale = TTLCache(maxsize=500, ttl=86400)

_verify_lock = threading.Lock()
_search_lock = threading.Lock()
_stale_lock = threading.Lock()
_search_stale_lock = threading.Lock()


def get_cached_verification(key: str):
    with _verify_lock:
        return _verify_cache.get(key)


def set_cached_verification(key: str, value: dict):
    with _verify_lock:
        _verify_cache[key] = value
    with _stale_lock:
        _verify_stale[key] = value


def get_stale_verification(key: str):
    with _stale_lock:
        return _verify_stale.get(key)


def get_cached_search(key: str):
    with _search_lock:
        return _search_cache.get(key)


def set_cached_search(key: str, value: list):
    with _search_lock:
        _search_cache[key] = value
    with _search_stale_lock:
        _search_stale[key] = value


def get_stale_search(key: str):
    with _search_stale_lock:
        return _search_stale.get(key)
