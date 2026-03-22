from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, HTTPException, Query
from fastapi.responses import JSONResponse
from app.dependencies import limiter, get_tier, get_rate_limit, get_api_key, get_allowed_states
from app.models.responses import LicenseDetail
from app.models.requests import StateCode
from app.services.verification import verify_license
from app.scrapers.base import ScraperUnavailableError, LicenseNotFoundError
from app.config import settings

router = APIRouter(tags=["Verify"])


_ERROR = {"application/json": {"schema": {"type": "object", "properties": {"detail": {"type": "string"}}}}}

@router.get(
    "/verify",
    response_model=LicenseDetail,
    responses={
        200: {"description": "License found and verified"},
        401: {
            "description": "Missing or invalid API key",
            "content": {"application/json": {"example": {"detail": "Invalid or missing API key. Provide your key in the X-API-Key header."}}},
        },
        403: {
            "description": "Requested state is not available on your tier",
            "content": {"application/json": {"example": {"detail": "State TX not available on BASIC tier. Upgrade to access more states."}}},
        },
        404: {
            "description": "No license found for the given license number in the requested state",
            "content": {"application/json": {"example": {"detail": "No CA license found for 9999999"}}},
        },
        422: {
            "description": "Invalid or missing request parameters",
            "content": {"application/json": {"example": {"detail": [{"loc": ["query", "state"], "msg": "value is not a valid enumeration member", "type": "type_error.enum"}]}}},
        },
        429: {
            "description": "Per-minute rate limit or monthly quota exceeded",
            "content": {"application/json": {"examples": {
                "per_minute": {"summary": "Per-minute limit hit", "value": {"detail": "Rate limit exceeded: 10 per 1 minute"}},
                "monthly": {"summary": "Monthly quota exhausted", "value": {"detail": "Monthly limit exceeded: 50 requests for 2026-03. Upgrade your plan or contact support."}},
            }}},
        },
        501: {
            "description": "State is recognized but not yet supported (NY scraper is in development)",
            "content": {"application/json": {"example": {"detail": "NY support coming soon"}}},
        },
        503: {
            "description": "State scraper is unavailable. Check `error_code` to determine retry strategy: `maintenance_window` (do not retry until Monday 6am PT), `circuit_open` (retry after 30s), `concurrency_limit` (retry immediately), `scraper_unavailable` (retry after 10 minutes or check /status).",
            "content": {"application/json": {"examples": {
                "maintenance": {"summary": "Scheduled maintenance", "value": {"detail": "CSLB offline for maintenance (Sundays 8pm – Mondays 6am PT)", "error_code": "maintenance_window"}},
                "circuit_open": {"summary": "Circuit breaker open — retry in 30s", "value": {"detail": "CA scraper circuit open — too many recent failures. Retrying in 30s.", "error_code": "circuit_open"}},
                "concurrency": {"summary": "Too many concurrent requests — retry immediately", "value": {"detail": "CA is handling too many concurrent requests. Try again in a moment.", "error_code": "concurrency_limit"}},
                "unavailable": {"summary": "Upstream site unreachable", "value": {"detail": "CSLB request failed: ConnectTimeout", "error_code": "scraper_unavailable"}},
            }}},
        },
    },
)
@limiter.limit(get_rate_limit)
async def verify(
    request: Request,
    response: Response,
    license_number: str = Query(..., description="Contractor license number", openapi_examples={"default": {"value": "1087351"}}),
    state: StateCode = Query(..., description="State code: CA, TX, FL", openapi_examples={"default": {"value": "CA"}}),
):
    tier = get_tier(request)
    allowed = get_allowed_states(tier)

    if state.value == "NY":
        raise HTTPException(status_code=501, detail="NY support coming soon")

    if state.value in settings.disabled_states_list:
        return JSONResponse(status_code=503, content={"detail": f"State {state.value} is currently disabled", "error_code": "state_disabled"})

    if state.value not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"State {state.value} not available on {tier} tier. Upgrade to access more states.",
        )

    try:
        result = verify_license(license_number, state.value)
    except LicenseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ScraperUnavailableError as e:
        return JSONResponse(status_code=503, content={"detail": str(e), "error_code": e.error_code})

    response.headers["Cache-Control"] = "public, max-age=1200"
    return LicenseDetail(
        license_number=result.get("license_number", license_number),
        state=state.value,
        status=result.get("status"),
        expiration_date=result.get("expiration_date"),
        license_type=result.get("license_type"),
        business_name=result.get("business_name"),
        owner_name=result.get("owner_name"),
        address=result.get("address"),
        disciplinary_actions=result.get("disciplinary_actions", []),
        disciplinary_actions_available=state.value != "TX",
        bond_status=result.get("bond_status"),
        bond_amount=result.get("bond_amount"),
        bond_expiration=result.get("bond_expiration"),
        workers_comp_status=result.get("workers_comp_status"),
        workers_comp_expiration=result.get("workers_comp_expiration"),
        data_freshness=result.get("data_freshness"),
        verified_at=datetime.now(tz=timezone.utc),
        source_url=result.get("source_url", ""),
        cache_hit=result.get("cache_hit", False),
    )
