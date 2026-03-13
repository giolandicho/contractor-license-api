import threading
from cachetools import TTLCache
from app.config import settings

_verify_cache = TTLCache(maxsize=1000, ttl=settings.cache_ttl_verify)
_search_cache = TTLCache(maxsize=500, ttl=settings.cache_ttl_search)

_verify_lock = threading.Lock()
_search_lock = threading.Lock()


def get_cached_verification(key: str):
    with _verify_lock:
        return _verify_cache.get(key)


def set_cached_verification(key: str, value: dict):
    with _verify_lock:
        _verify_cache[key] = value


def get_cached_search(key: str):
    with _search_lock:
        return _search_cache.get(key)


def set_cached_search(key: str, value: list):
    with _search_lock:
        _search_cache[key] = value
