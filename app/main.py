import time
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO, format="%(message)s")
_metrics_logger = logging.getLogger("api.metrics")
_logger = logging.getLogger(__name__)

from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from app.middleware.auth import APIKeyMiddleware
from app.middleware.monthly_limit import MonthlyLimitMiddleware
from app.middleware.security import SecurityMiddleware
from app.dependencies import limiter
from app.routers import health, states, verify, search, status, probe
from app.config import settings


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom 429 handler that adds Retry-After so integrators know when to retry."""
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )
    response.headers["Retry-After"] = "60"
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.redis_url:
        _logger.warning(
            "REDIS_URL not set — rate limiting is IN-MEMORY and PER-PROCESS. "
            "Monthly quotas will NOT be enforced. "
            "Multi-worker deployments will have separate rate-limit buckets per worker. "
            "Set REDIS_URL in production."
        )
    if settings.env == "production" and not settings.redis_url:
        raise RuntimeError(
            "REDIS_URL is required in production. "
            "Set it in your environment to enable shared rate limiting and monthly quotas."
        )
    yield


app = FastAPI(
    title="Contractor License Verification API",
    lifespan=lifespan,
    description="""
Verify contractor licenses in real-time from official government sources.

**Supported states:** California (CSLB), Texas (TDLR), Florida (DBPR)

**Authentication:** Pass your API key in the `X-API-Key` header. Missing or invalid keys return `401`. Valid keys with insufficient tier access return `403`.

**Tiers:**
| Tier | Price | Included | Overage | States |
|------|-------|----------|---------|--------|
| `BASIC` | $0/month | 50 req/month | — | CA |
| `PRO` | $49/month | 1,000 req/month | $0.10 each | CA, TX |
| `ULTRA` | $99/month | 5,000 req/month | $0.08 each | CA, TX, FL |
| `MEGA` | $249/month | 25,000 req/month | $0.02 each | All |

Monthly quotas are enforced per API key (requires Redis in production). Per-minute limits apply independently.

---

**Performance:**
- **Cache hit:** <100ms (`cache_hit: true` in response)
- **Cache miss (live scrape):** 3–10 seconds — data is fetched in real time from government portals. Cache-miss requests are **not** covered by a 5-second SLA.
- **Cache TTLs:** 20 min for `/verify`, 15 min for `/search`
- **California maintenance window:** Sundays 8pm – Mondays 6am PT; `/verify` and `/search` return `503` during this window
- **TX and FL** have no scheduled maintenance windows; a `503` for those states indicates an unexpected upstream outage
- All response times are visible in the `X-Response-Time` header
- Prometheus metrics available at `/metrics` (histogram of request duration by endpoint and status)

---

**`disciplinary_actions` field:**
- CA and FL: returns a list (empty `[]` if none on record); `disciplinary_actions_available: true`
- TX: returns `null` — disciplinary data is not available from the TDLR portal; `disciplinary_actions_available: false`

---

**New York (NY):** Support is in development. `/states` lists NY as `coming_soon`. Requests for NY return `501`.

---

**Data sources:** Official government portals. All data is public record.
    """,
    version="1.0.0",
    contact={"name": "API Support"},
    license_info={"name": "Commercial"},
)

# Prometheus metrics — exposes /metrics endpoint (no auth required)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Rate limit state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

# Middleware stack (first added = outermost = runs first on incoming requests)
# Order: MonthlyLimitMiddleware → APIKeyMiddleware → timing → route handler
app.add_middleware(MonthlyLimitMiddleware)  # innermost: runs after auth has validated the key
app.add_middleware(APIKeyMiddleware)         # middle: validates API key before monthly check
app.add_middleware(SecurityMiddleware)       # outermost: request hardening before any auth


@app.middleware("http")
async def add_response_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Response-Time"] = f"{duration_ms}ms"
    _metrics_logger.info(json.dumps({
        "type": "request",
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response

# Routers
app.include_router(health.router)
app.include_router(states.router)
app.include_router(status.router)
app.include_router(probe.router)
app.include_router(verify.router)
app.include_router(search.router)
