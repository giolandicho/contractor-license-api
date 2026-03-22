# Contractor License Verification API

Real-time contractor license lookup from official US government sources. Pass a license number or business name and get back verified status, expiration date, license type, and disciplinary history — scraped live from CSLB (CA), TDLR (TX), and DBPR (FL).

## Quick Start

```bash
# Verify a license
curl "https://your-api-host/verify?license_number=1087351&state=CA" \
  -H "X-API-Key: your-api-key"

# Search by name
curl "https://your-api-host/search?name=Smith+Construction&state=CA&limit=10" \
  -H "X-API-Key: your-api-key"
```

## Authentication

Pass your API key in the `X-API-Key` header on every request.

- Missing or invalid key → `401 Unauthorized`
- Valid key but state not included in your tier → `403 Forbidden`

## Tiers & Pricing

| Tier | Price | Included | Overage | States | Rate limit |
|------|-------|----------|---------|--------|------------|
| **BASIC** | $0/month | 50 req/month | — | CA | 10 req/min |
| **PRO** | $49/month | 1,000 req/month | $0.10 each | CA, TX | 60 req/min |
| **ULTRA** | $99/month | 5,000 req/month | $0.08 each | CA, TX, FL | 120 req/min |
| **MEGA** | $249/month | 25,000 req/month | $0.02 each | All | 300 req/min |

Monthly quotas are enforced per API key and reset on the 1st of each month.

## Supported States

| State | Agency | Status |
|-------|--------|--------|
| CA | Contractors State License Board (CSLB) | Active |
| TX | Texas Department of Licensing and Regulation (TDLR) | Active |
| FL | Florida Department of Business and Professional Regulation (DBPR) | Active |
| NY | New York Department of State | Coming soon (scraper in development) |

## Endpoints

### `GET /verify`

Look up a single license by number.

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `license_number` | string | yes | The contractor license number | `1087351` |
| `state` | string | yes | State code: `CA`, `TX`, `FL` | `CA` |

**Success (`200`):**
```json
{
  "license_number": "1087351",
  "state": "CA",
  "status": "Active",
  "expiration_date": "2026-06-30",
  "license_type": "General Building (B)",
  "business_name": "SMITH CONSTRUCTION INC",
  "owner_name": "JOHN SMITH",
  "address": "123 MAIN ST, LOS ANGELES CA 90001",
  "disciplinary_actions": [],
  "disciplinary_actions_available": true,
  "verified_at": "2024-01-15T18:30:00Z",
  "source_url": "https://www.cslb.ca.gov/...",
  "cache_hit": false
}
```

**`disciplinary_actions` field:**
- CA and FL: list (`[]` if none on record); `disciplinary_actions_available: true`
- TX: `null` — disciplinary data is not published by TDLR; `disciplinary_actions_available: false`

---

### `GET /search`

Search for licenses by business or owner name.

| Parameter | Type | Required | Default | Description | Example |
|-----------|------|----------|---------|-------------|---------|
| `name` | string | yes | — | Business or owner name to search | `Smith Construction` |
| `state` | string | yes | — | State code: `CA`, `TX`, `FL` | `CA` |
| `limit` | integer | no | `10` | Max results to return (1–50) | `10` |

No results returns `200` with an empty `results` array — never `404`.

**Success with results (`200`):**
```json
{
  "state": "CA",
  "query": "Smith Construction",
  "results": [
    {
      "license_number": "1087351",
      "business_name": "SMITH CONSTRUCTION INC",
      "owner_name": "JOHN SMITH",
      "status": "Active",
      "license_type": "General Building (B)",
      "expiration_date": "2026-06-30"
    }
  ],
  "total_results": 1,
  "searched_at": "2024-01-15T18:30:00Z"
}
```

**No matches (`200`):**
```json
{
  "state": "CA",
  "query": "Nonexistent Corp",
  "results": [],
  "total_results": 0,
  "searched_at": "2024-01-15T18:30:00Z"
}
```

---

### `GET /health`

Returns per-state scraper health. No authentication required.

### `GET /states`

Returns the list of supported states, their agencies, license types, and availability status. No authentication required.

### `GET /status`

Returns per-state pipeline health derived from real traffic — not a synthetic probe. Each state reports `operational` (successful scrape within 60 min), `degraded` (last success >60 min ago), or `unknown` (no traffic since last deploy). No authentication required.

UptimeRobot keyword: **`states`** (structural key, always present).

### `GET /probe`

Reachability probe: performs a live HTTP request to the state portal and verifies it responds. Accepts `?state=CA` (default), `?state=TX`, or `?state=FL`. Returns `{"status": "ok"}` on success, `503` on failure. No authentication required.

- CA: returns `503` during the maintenance window (Sundays 8pm – Mondays 6am PT)
- TX and FL: no scheduled maintenance windows; `503` indicates an unexpected upstream outage

UptimeRobot keyword: **`ok`**. Recommended monitor interval: 15 minutes.

### `GET /probe/verify`

Full parse probe: performs a live scrape for a known seed license number and validates the full verification pipeline (HTTP request + HTML parse + schema extraction). Requires `PROBE_LICENSE_{STATE}` environment variable to be set. Returns `{"status": "ok", "state": "CA", "license_number": "..."}` on success, `503` on failure. No authentication required.

Use this in addition to `/probe` to catch scraper breakage caused by government portal HTML changes.

UptimeRobot keyword: **`ok`**. Recommended monitor interval: 15 minutes.

### `GET /metrics`

Prometheus metrics endpoint. Exposes request duration histograms by endpoint, method, and status code — use these to compute p95/p99 latency. No authentication required.

---

## Error Codes

| Status | Cause | Recommended action |
|--------|-------|--------------------|
| `401` | Missing or invalid `X-API-Key` header | Check that your API key is correct and included in the header |
| `403` | Your tier does not include the requested state | Upgrade to a higher tier; see `/states` for tier-to-state mapping |
| `404` | License number not found in the requested state | Verify the license number directly on the issuing agency's website |
| `422` | Invalid request parameters (bad state code, limit out of range) | Check that `state` is `CA`/`TX`/`FL` and `limit` is between 1–50 |
| `429` | Rate limit exceeded (per-minute or monthly) | See examples below |
| `501` | State recognized but not yet supported (NY) | Check `/states` for availability updates |
| `503` | State scraper unavailable | See `error_code` field for retry strategy (table below) |

All errors return `{"detail": "explanation string"}`.

**`401` example** (missing or invalid API key):
```json
{"detail": "Invalid or missing API key. Provide your key in the X-API-Key header."}
```

**`403` example** (state not in your tier):
```json
{"detail": "State TX not available on BASIC tier. Upgrade to access more states."}
```

**`404` example** (license number not found):
```json
{"detail": "No CA license found for 9999999"}
```

**`503` responses also include an `error_code` field** to enable precise retry logic:

| `error_code` | Cause | Retry strategy |
|---|---|---|
| `maintenance_window` | CA scheduled maintenance (Sundays 8pm – Mondays 6am PT) | Do not retry until Monday 6am PT |
| `circuit_open` | Too many recent failures — circuit breaker open | Retry after 30 seconds |
| `concurrency_limit` | Too many simultaneous requests to this state | Retry immediately |
| `scraper_unavailable` | Upstream site unreachable or returned unexpected HTML | Retry after 10 minutes; check `/status` |
| `state_disabled` | State temporarily disabled by operator | Check `/status`; do not retry |

Example `503` response:
```json
{"detail": "CA scraper circuit open — too many recent failures. Retrying in 30s.", "error_code": "circuit_open"}
```

**`429` — two causes:**

Per-minute limit (back off and retry after 60 seconds):
```json
{"detail": "Rate limit exceeded: 10 per 1 minute"}
```

Monthly quota exhausted (upgrade or contact support):
```json
{"detail": "Monthly limit exceeded: 50 requests for 2026-03. Upgrade your plan or contact support."}
```

**`422` example** (invalid state code):
```json
{
  "detail": [{"loc": ["query", "state"], "msg": "value is not a valid enumeration member", "type": "type_error.enum"}]
}
```

**`501` example** (NY not yet supported):
```json
{"detail": "NY support coming soon"}
```

---

## Performance

All responses include an `X-Response-Time` header with the server-side duration in milliseconds.

**Cache hit** (`cache_hit: true`): <100ms for all states.

**Cache miss** (live scrape) — p50 and p95 by state:

| State | p50 | p95 | Notes |
|-------|-----|-----|-------|
| CA | ~4s | ~8s | Two-step ASP.NET ViewState form — requires GET + POST to CSLB |
| TX | ~2s | ~5s | Single POST to TDLR search |
| FL | ~2s | ~6s | Single GET to DBPR |

**Cache-miss requests are not covered by a 5-second SLA.** Build retry/timeout logic accordingly.

- **Cache TTLs:** 20 min for `/verify`, 15 min for `/search`
- **CA maintenance window:** Sundays 8pm – Mondays 6am PT; CA requests return `503`
- **TX and FL:** No scheduled maintenance windows
- **Prometheus p95:** Use `/metrics` with Prometheus/Grafana to track per-endpoint latency percentiles

### Stale data fallback

When a state portal is temporarily unreachable (circuit breaker open, maintenance window, upstream timeout), `/verify` returns a **200 with the last-known result** rather than a `503` — if a prior result for that license is available in the stale cache. The response will include:

```json
{"data_freshness": "stale", "cache_hit": true, ...}
```

| `data_freshness` value | Meaning |
|---|---|
| `null` | Live data — scraped in this request or served from the fresh 20-minute cache |
| `"stale"` | Served from the stale backing store; data may be up to 24 hours old |

Stale results are retained for up to **24 hours**. If no prior result exists and the scraper is unavailable, the endpoint returns `503` as normal.

## Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Interactive docs: `http://localhost:8000/docs` | Metrics: `http://localhost:8000/metrics`

```bash
pytest          # run all tests
pytest -v       # verbose
```

**Production note:** Set `REDIS_URL` in production to enable shared rate limiting and enforce monthly quotas. Without Redis, per-minute limits are in-memory per-process and monthly quotas are not applied.

## Deployment

### Gateway

This API does not include a network-level gateway. Gateway-level DDoS protection and IP-rate limiting depend on the distribution channel:

- **RapidAPI channel:** Gateway-level protection, schema validation, and key management are provided by the RapidAPI platform.
- **Direct enterprise customers:** Front the Railway deployment with [Cloudflare](https://cloudflare.com) (free tier provides DDoS protection and WAF) or AWS API Gateway as a passthrough proxy.

### Monitoring Setup

UptimeRobot monitors are configured via `scripts/setup_uptimerobot.py`. Run once with your UptimeRobot API key to create all five monitors (health, status, and per-state probes):

```bash
UPTIMEROBOT_API_KEY=your_key python scripts/setup_uptimerobot.py
```

After setup, confirm all monitors are active in the UptimeRobot dashboard and add the public status page URL to your API documentation.
