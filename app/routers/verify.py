from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, HTTPException, Query
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
        403: {
            "description": "Invalid API key, or requested state is not available on your tier",
            "content": {"application/json": {"example": {"detail": "State TX not available on free tier. Upgrade to access more states."}}},
        },
        404: {
            "description": "No license found for the given license number in the requested state",
            "content": {"application/json": {"example": {"detail": "No CA license found for 9999999"}}},
        },
        429: {
            "description": "Rate limit exceeded for your tier",
            "content": {"application/json": {"example": {"detail": "Rate limit exceeded: 10 per 1 minute"}}},
        },
        501: {
            "description": "State is recognized but not yet supported",
            "content": {"application/json": {"example": {"detail": "NY support coming soon"}}},
        },
        503: {
            "description": "State scraper is unavailable (maintenance window or upstream site unreachable)",
            "content": {"application/json": {"example": {"detail": "CSLB offline for maintenance (Sundays 8pm – Mondays 6am PT)"}}},
        },
        422: {
            "description": "Invalid or missing request parameters",
            "content": {"application/json": {"example": {"detail": [{"loc": ["query", "state"], "msg": "value is not a valid enumeration member", "type": "type_error.enum"}]}}},
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
        raise HTTPException(status_code=503, detail=f"State {state.value} is currently disabled")

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
        raise HTTPException(status_code=503, detail=str(e))

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
        verified_at=datetime.now(tz=timezone.utc),
        source_url=result.get("source_url", ""),
        cache_hit=result.get("cache_hit", False),
    )
