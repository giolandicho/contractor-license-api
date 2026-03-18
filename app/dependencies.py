from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings


def get_api_key(request: Request) -> str:
    return request.headers.get("X-API-Key", get_remote_address(request))


def get_tier(request: Request) -> str:
    key = request.headers.get("X-API-Key", "")
    if key in settings.enterprise_keys_list:
        return "enterprise"
    if key in settings.pro_keys_list:
        return "pro"
    if key in settings.basic_keys_list:
        return "basic"
    return "free"


def get_rate_limit(key: str) -> str:
    if key in settings.enterprise_keys_list:
        return "300/minute"
    if key in settings.pro_keys_list:
        return "120/minute"
    if key in settings.basic_keys_list:
        return "60/minute"
    return "10/minute"


# Tier → allowed states
TIER_STATES = {
    "free": {"CA"},
    "basic": {"CA", "TX"},
    "pro": {"CA", "TX", "FL"},
    "enterprise": {"CA", "TX", "FL"},
}


def get_allowed_states(tier: str) -> set:
    return TIER_STATES.get(tier, {"CA"})


limiter = Limiter(
    key_func=get_api_key,
    storage_uri=settings.redis_url or "memory://",
)
