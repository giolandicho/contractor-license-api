from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, HTTPException, Query
from app.dependencies import limiter, get_tier, get_rate_limit, get_allowed_states
from app.models.responses import SearchResponse, SearchResultItem
from app.models.requests import StateCode
from app.services.verification import search_licenses
from app.scrapers.base import ScraperUnavailableError, LicenseNotFoundError
from app.config import settings

router = APIRouter(tags=["Search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    responses={
        200: {
            "description": "Search completed. Returns empty results array if no matches found — never 404.",
            "content": {"application/json": {"examples": {
                "with_results": {"summary": "Results found", "value": {
                    "state": "CA", "query": "Smith Construction",
                    "results": [{"license_number": "1087351", "business_name": "SMITH CONSTRUCTION INC",
                                 "owner_name": "JOHN SMITH", "status": "Active",
                                 "license_type": "General Building (B)", "expiration_date": "2026-06-30"}],
                    "total_results": 1, "searched_at": "2024-01-15T18:30:00Z",
                }},
                "no_results": {"summary": "No matches found", "value": {
                    "state": "CA", "query": "Nonexistent Corp",
                    "results": [], "total_results": 0, "searched_at": "2024-01-15T18:30:00Z",
                }},
            }}},
        },
        401: {
            "description": "Missing or invalid API key",
            "content": {"application/json": {"example": {"detail": "Invalid or missing API key. Provide your key in the X-API-Key header."}}},
        },
        403: {
            "description": "Requested state is not available on your tier",
            "content": {"application/json": {"example": {"detail": "State TX not available on BASIC tier. Upgrade to access more states."}}},
        },
        422: {
            "description": "Invalid or missing request parameters",
            "content": {"application/json": {"example": {"detail": [{"loc": ["query", "limit"], "msg": "ensure this value is less than or equal to 50", "type": "value_error.number.not_le"}]}}},
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
            "description": "State scraper is unavailable (maintenance window or upstream site unreachable). Retry after 10 minutes or check /status.",
            "content": {"application/json": {"example": {"detail": "CSLB offline for maintenance (Sundays 8pm – Mondays 6am PT)"}}},
        },
    },
)
@limiter.limit(get_rate_limit)
async def search(
    request: Request,
    response: Response,
    name: str = Query(..., description="Contractor or business name to search", openapi_examples={"default": {"value": "Smith Construction"}}),
    state: StateCode = Query(..., description="State code: CA, TX, FL", openapi_examples={"default": {"value": "CA"}}),
    limit: int = Query(default=10, ge=1, le=50, description="Max results (1-50)"),
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

    response.headers["Cache-Control"] = "public, max-age=900"
    return SearchResponse(
        state=state.value,
        query=name,
        results=results,
        total_results=len(results),
        searched_at=datetime.now(tz=timezone.utc),
    )
