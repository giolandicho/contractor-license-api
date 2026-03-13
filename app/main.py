from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.middleware.auth import APIKeyMiddleware
from app.dependencies import limiter
from app.routers import health, states, verify, search

app = FastAPI(
    title="Contractor License Verification API",
    description="""
Verify contractor licenses in real-time from official government sources.

**Supported states:** California (CSLB), Texas (TDLR), Florida (DBPR)

**Authentication:** Pass your API key in the `X-API-Key` header.

**Tiers:**
- `free` — CA only, 10 req/min
- `basic` — CA + TX, 60 req/min
- `pro` — CA + TX + FL, 120 req/min
- `enterprise` — All states, 300 req/min

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

# Routers
app.include_router(health.router)
app.include_router(states.router)
app.include_router(verify.router)
app.include_router(search.router)
