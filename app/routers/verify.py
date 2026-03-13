from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Query
from app.dependencies import limiter, get_tier, get_rate_limit, get_api_key, get_allowed_states
from app.models.responses import LicenseDetail
from app.models.requests import StateCode
from app.services.verification import verify_license
from app.scrapers.base import ScraperUnavailableError, LicenseNotFoundError
from app.config import settings

router = APIRouter(tags=["Verify"])


@router.get("/verify", response_model=LicenseDetail)
@limiter.limit(get_rate_limit)
async def verify(
    request: Request,
    license_number: str = Query(..., description="Contractor license number"),
    state: StateCode = Query(..., description="State code: CA, TX, FL"),
):
    tier = get_tier(request)
    allowed = get_allowed_states(tier)

    if state.value in settings.disabled_states_list:
        raise HTTPException(status_code=503, detail=f"State {state.value} is currently disabled")

    if state.value not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"State {state.value} not available on {tier} tier. Upgrade to access more states.",
        )

    if state.value == "NY":
        raise HTTPException(status_code=501, detail="NY support coming soon")

    try:
        result = verify_license(license_number, state.value)
    except LicenseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ScraperUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

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
