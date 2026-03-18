# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Setup:**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Run (development):**
```bash
uvicorn app.main:app --reload
```

**Tests:**
```bash
pytest                          # all tests
pytest tests/test_verify.py     # single file
pytest -v                       # verbose
```

## Architecture

FastAPI app that verifies contractor licenses by scraping official government portals (CA/TX/FL). No database — all data is fetched live and cached in-memory.

**Request flow:** Middleware auth → rate limiter → router → verification service → TTL cache (hit) or scraper (miss) → government site HTML → BeautifulSoup parse → Pydantic response model.

**Key design points:**

- `app/scrapers/` — one file per state, each implements `verify()`, `search()`, `health_check()`. CA scraper handles ASP.NET ViewState forms. All extend `BaseScraper`.
- `app/services/verification.py` — routes to the right scraper, manages cache reads/writes.
- `app/dependencies.py` — defines tier system (free/basic/pro/enterprise), maps tiers to allowed states (`TIER_STATES`), and returns rate limit strings for SlowAPI.
- `app/middleware/auth.py` — validates `X-API-Key` header; also handles RapidAPI proxy auth via `RAPIDAPI_PROXY_SECRET`.
- `app/cache/ttl_cache.py` — thread-safe TTLCache wrappers; default 1200s for verify, 900s for search.
- `app/data/state_info.py` — static metadata per state (agency name, license types, source URL). NY is defined but disabled by default via `DISABLED_STATES`.

**Auth tiers and state access:**
| Tier | States | Rate limit |
|------|--------|------------|
| free | CA | 10 req/min |
| basic | CA, TX | 60 req/min |
| pro | CA, TX, FL | 120 req/min |
| enterprise | all | 300 req/min |

**Unauthenticated paths:** `/health`, `/states`, `/docs`, `/openapi.json`, `/redoc`

**Error mapping:** `LicenseNotFoundError` → 404, `ScraperUnavailableError` → 503. Search with no results returns 200 with empty array.

**CA maintenance window:** Sundays 8pm – Mondays 6am PT; scraper raises `ScraperUnavailableError` during this window.

## Environment Variables

See `.env.example`. API keys for each tier are comma-separated lists (`API_KEYS`, `BASIC_KEYS`, `PRO_KEYS`, `ENTERPRISE_KEYS`). `DISABLED_STATES` defaults to `NY`.

## Tests

Tests use FastAPI `TestClient` with mocked scrapers (`unittest.mock.patch`). Fixtures in `conftest.py` provide API keys per tier and mock license data for CA/TX/FL. Always mock scrapers — tests do not hit live government sites.
