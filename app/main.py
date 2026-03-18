import time
import logging
import json
from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO, format="%(message)s")
_metrics_logger = logging.getLogger("api.metrics")
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.middleware.auth import APIKeyMiddleware
from app.dependencies import limiter
from app.routers import health, states, verify, search, status, probe

app = FastAPI(
    title="Contractor License Verification API",
    description="""
Verify contractor licenses in real-time from official government sources.

**Supported states:** California (CSLB), Texas (TDLR), Florida (DBPR)

**Authentication:** Pass your API key in the `X-API-Key` header.

**Tiers:**
| Tier | States | Rate limit |
|------|--------|------------|
| `free` | CA | 10 req/min |
| `basic` | CA, TX | 60 req/min |
| `pro` | CA, TX, FL | 120 req/min |
| `enterprise` | All | 300 req/min |

---

**Performance:**
- **Cache hit:** <100ms (`cache_hit: true` in response)
- **Cache miss (live scrape):** 3–10 seconds — data is fetched in real time from government portals
- **Cache TTLs:** 20 min for `/verify`, 15 min for `/search`
- **California maintenance window:** Sundays 8pm – Mondays 6am PT; `/verify` and `/search` return `503` during this window
- All response times are visible in the `X-Response-Time` header

---

**`disciplinary_actions` field:**
- CA and FL: returns a list (empty `[]` if none on record)
- TX: returns `null` — disciplinary data is not available from the TDLR portal

---

**Data sources:** Official government portals. All data is public record.
    """,
    version="1.0.0",
    contact={"name": "API Support"},
    license_info={"name": "Commercial"},
)

# Rate limit state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Auth middleware
app.add_middleware(APIKeyMiddleware)


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
