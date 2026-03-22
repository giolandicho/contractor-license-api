from fastapi import APIRouter, HTTPException, Query, Response
from app.scrapers.ca import CAScraper, _is_maintenance_window
from app.scrapers.tx import TXScraper
from app.scrapers.fl import FLScraper
from app.scrapers.base import ScraperUnavailableError
from app.config import settings

router = APIRouter(tags=["Probe"])

_scrapers = {
    "CA": CAScraper(),
    "TX": TXScraper(),
    "FL": FLScraper(),
}


@router.get(
    "/probe",
    responses={
        200: {
            "description": "Pipeline is reachable and responding.",
            "content": {"application/json": {"example": {"status": "ok", "state": "CA"}}},
        },
        422: {
            "description": "Unsupported state for probe.",
            "content": {"application/json": {"example": {"detail": "Unsupported state for probe: 'NY'. Use CA, TX, or FL."}}},
        },
        503: {
            "description": "Scraper is unreachable or in maintenance window.",
            "content": {"application/json": {"example": {"detail": "CA scraper offline: maintenance window (Sundays 8pm – Mondays 6am PT)"}}},
        },
    },
)
async def probe(
    response: Response,
    state: str = Query(default="CA", description="State pipeline to probe: CA, TX, or FL"),
):
    """
    End-to-end pipeline probe for UptimeRobot synthetic monitoring.
    No authentication required.

    Performs a live HTTP request to the specified state portal and verifies the
    site is reachable and responding. Returns `{"status": "ok"}` on success.

    UptimeRobot keyword monitor: use `"ok"` as the keyword.
    Recommended monitor interval: 15 minutes.

    During the CA maintenance window (Sundays 8pm – Mondays 6am PT) this
    endpoint returns 503 for state=CA. TX and FL have no scheduled maintenance
    windows; a 503 for those states indicates an unexpected upstream outage.
    """
    state = state.upper()
    if state not in _scrapers:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported state for probe: {state!r}. Use CA, TX, or FL.",
        )

    scraper = _scrapers[state]
    try:
        ok = scraper.health_check()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"{state} probe failed: {e}")

    if not ok:
        if state == "CA" and _is_maintenance_window():
            raise HTTPException(
                status_code=503,
                detail="CA scraper offline: maintenance window (Sundays 8pm – Mondays 6am PT)",
            )
        raise HTTPException(status_code=503, detail=f"{state} scraper health check failed")

    response.headers["Cache-Control"] = "no-cache"
    return {"status": "ok", "state": state}


@router.get(
    "/probe/verify",
    responses={
        200: {
            "description": "Full verify round-trip succeeded — portal reachable and parser working.",
            "content": {"application/json": {"example": {"status": "ok", "state": "CA", "license_number": "1087351"}}},
        },
        422: {
            "description": "Unsupported state for probe.",
            "content": {"application/json": {"example": {"detail": "Unsupported state for probe: 'NY'. Use CA, TX, or FL."}}},
        },
        503: {
            "description": "Scraper unavailable or seed license not configured.",
            "content": {"application/json": {"examples": {
                "not_configured": {"summary": "Seed not set", "value": {"detail": "PROBE_LICENSE_CA not configured. Set it in environment to enable /probe/verify."}},
                "scraper_down": {"summary": "Scraper failed", "value": {"detail": "CA scraper circuit open — too many recent failures. Retrying in 30s."}},
            }}},
        },
    },
)
async def probe_verify(
    response: Response,
    state: str = Query(default="CA", description="State pipeline to probe: CA, TX, or FL"),
):
    """
    Full verify probe: performs a live scrape for a known seed license number.

    Unlike `/probe` (which only checks portal reachability), this endpoint runs the
    complete verification pipeline — HTTP request, HTML parse, and schema extraction —
    ensuring the scraper is fully functional, not just reachable.

    Requires `PROBE_LICENSE_{STATE}` environment variable to be set with a known-good
    license number for the target state.

    UptimeRobot keyword monitor: use `"ok"` as the keyword.
    Recommended monitor interval: 15 minutes.
    """
    state = state.upper()
    if state not in _scrapers:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported state for probe: {state!r}. Use CA, TX, or FL.",
        )

    seed = getattr(settings, f"probe_license_{state.lower()}", None)
    if not seed:
        raise HTTPException(
            status_code=503,
            detail=f"PROBE_LICENSE_{state} not configured. Set it in environment to enable /probe/verify.",
        )

    scraper = _scrapers[state]
    try:
        scraper.verify(seed)
    except ScraperUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"{state} full verify probe failed: {e}")

    response.headers["Cache-Control"] = "no-cache"
    return {"status": "ok", "state": state, "license_number": seed}
