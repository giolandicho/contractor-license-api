from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Query
from app.dependencies import limiter, get_tier, get_rate_limit, get_allowed_states
from app.models.responses import SearchResponse, SearchResultItem
from app.models.requests import StateCode
from app.services.verification import search_licenses
from app.scrapers.base import ScraperUnavailableError, LicenseNotFoundError
from app.config import settings

router = APIRouter(tags=["Search"])


@router.get("/search", response_model=SearchResponse)
@limiter.limit(get_rate_limit)
async def search(
    request: Request,
    name: str = Query(..., description="Contractor or business name to search"),
    state: StateCode = Query(..., description="State code: CA, TX, FL"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results (1-50)"),
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
        raw_results = search_licenses(name, state.value, limit)
    except ScraperUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LicenseNotFoundError:
        raw_results = []

    results = [
        SearchResultItem(
            license_number=r.get("license_number", ""),
            business_name=r.get("business_name"),
            owner_name=r.get("owner_name"),
            status=r.get("status"),
            license_type=r.get("license_type"),
            expiration_date=r.get("expiration_date"),
        )
        for r in raw_results[:limit]
        if r.get("license_number")
    ]

    return SearchResponse(
        state=state.value,
        query=name,
        results=results,
        total_results=len(results),
        searched_at=datetime.now(tz=timezone.utc),
    )
