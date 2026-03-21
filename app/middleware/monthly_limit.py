import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings

logger = logging.getLogger(__name__)

# Monthly request caps per tier. None = unlimited.
_MONTHLY_LIMITS: Dict[str, Optional[int]] = {
    "BASIC": 50,
    "PRO": 1_000,
    "ULTRA": 5_000,
    "MEGA": None,
}

_EXCLUDED_PATHS = {
    "/health", "/states", "/status", "/probe",
    "/docs", "/openapi.json", "/redoc", "/metrics",
}

# Module-level async Redis client — lazily initialised, shared via connection pool
_redis = None


async def _get_redis():
    global _redis
    if _redis is None and settings.redis_url:
        try:
            import redis.asyncio as aioredis
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception as exc:
            logger.warning("Monthly limiter: failed to create Redis client (%s)", exc)
    return _redis


def _key_tier(api_key: str) -> str:
    if api_key in settings.enterprise_keys_list:
        return "MEGA"
    if api_key in settings.pro_keys_list:
        return "ULTRA"
    if api_key in settings.basic_keys_list:
        return "PRO"
    return "BASIC"


class MonthlyLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-API-key monthly request quotas using Redis.

    Fails open if Redis is not configured or unavailable — monthly limits are
    a billing constraint, not a security gate.
    RapidAPI requests are skipped (quota managed by RapidAPI platform).
    Unlimited-tier (MEGA) keys are skipped entirely.
    """

    async def dispatch(self, request, call_next):
        if request.url.path.rstrip("/") in _EXCLUDED_PATHS:
            return await call_next(request)

        # RapidAPI manages its own billing
        if request.headers.get("X-RapidAPI-User"):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return await call_next(request)

        tier = _key_tier(api_key)
        monthly_limit = _MONTHLY_LIMITS.get(tier)
        if monthly_limit is None:
            return await call_next(request)  # unlimited tier

        r = await _get_redis()
        if r is None:
            return await call_next(request)  # fail-open: no Redis configured

        try:
            month = datetime.now(tz=timezone.utc).strftime("%Y-%m")
            redis_key = f"monthly:{month}:{api_key}"
            count = await r.incr(redis_key)
            if count == 1:
                # First request this month — set TTL so the key self-cleans after rollover
                await r.expire(redis_key, 35 * 24 * 3600)
        except Exception as exc:
            logger.warning("Monthly limit check failed (%s) — allowing request", exc)
            return await call_next(request)

        if count > monthly_limit:
            month_label = datetime.now(tz=timezone.utc).strftime("%Y-%m")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Monthly limit exceeded: {monthly_limit} requests for {month_label}. "
                        "Upgrade your plan or contact support."
                    )
                },
            )

        return await call_next(request)
