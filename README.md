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

Pass your API key in the `X-API-Key` header on every request. Requests without a valid key return `403`.

## Tiers & Pricing

| Tier | Price | Included | Overage | States |
|------|-------|----------|---------|--------|
| **BASIC** | $0/month | 50 req/month | — | CA |
| **PRO** | $49/month | 1,000 req/month | $0.10 each | CA, TX |
| **ULTRA** | $99/month | 5,000 req/month | $0.08 each | CA, TX, FL |
| **MEGA** | $249/month | 25,000 req/month | $0.02 each | All |

## Endpoints

### `GET /verify`

Look up a single license by number.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `license_number` | string | yes | The contractor license number |
| `state` | string | yes | State code: `CA`, `TX`, `FL` |

**Success response (`200`):**
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
  "verified_at": "2024-01-15T18:30:00Z",
  "source_url": "https://www.cslb.ca.gov/...",
  "cache_hit": false
}
```

> **`disciplinary_actions`:** Returns a list for CA and FL (`[]` if none on record). Returns `null` for TX — disciplinary data is not available from the TDLR portal.

---

### `GET /search`

Search for licenses by business or owner name.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | yes | — | Business or owner name to search |
| `state` | string | yes | — | State code: `CA`, `TX`, `FL` |
| `limit` | integer | no | `10` | Max results to return (1–50) |

No results returns `200` with an empty `results` array — not `404`.

**Success response (`200`):**
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

---

### `GET /health`

Returns per-state scraper health. No authentication required.

### `GET /states`

Returns the list of supported states, their agencies, license types, and availability status. No authentication required.

### `GET /status`

Returns per-state pipeline health derived from real traffic — not a synthetic probe. Each state reports `operational` (successful scrape within 60 min), `degraded` (last success >60 min ago), or `unknown` (no traffic since last deploy). No authentication required.

UptimeRobot keyword: **`states`** (structural key, always present).

### `GET /probe`

Live end-to-end pipeline probe: performs a real HTTP request to the CA (CSLB) portal and returns `{"status": "ok"}` on success, `503` on failure. No authentication required. Returns `503` during the CA maintenance window (Sundays 8pm – Mondays 6am PT).

UptimeRobot keyword: **`ok`**. Recommended monitor interval: 15 minutes.

---

## Error Codes

| Status | Meaning | What to do |
|--------|---------|------------|
| `403` | Missing or invalid API key, or state not available on your tier | Check your `X-API-Key` header; upgrade tier to access more states |
| `404` | License number not found in the requested state | Verify the license number is correct |
| `422` | Invalid request parameters | Check that `state` is a valid code and `limit` is between 1–50 |
| `429` | Rate limit exceeded | Back off and retry; see your tier's limit above |
| `501` | State not yet supported (e.g. NY) | Check `/states` for availability updates |
| `503` | State scraper unavailable | Government site is unreachable or in a maintenance window; retry later |

All errors return `{"detail": "explanation string"}`.

---

## Performance

All responses include an `X-Response-Time` header with the server-side duration.

- **Cache hit** (`cache_hit: true`): <100ms
- **Cache miss** (live scrape): 3–10 seconds — data is fetched in real time from government portals
- **Cache TTLs:** 20 min for `/verify`, 15 min for `/search`
- **California maintenance window:** Sundays 8pm – Mondays 6am PT; CA requests return `503` during this window

## Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Interactive docs available at `http://localhost:8000/docs`.

```bash
pytest          # run all tests
pytest -v       # verbose
```
