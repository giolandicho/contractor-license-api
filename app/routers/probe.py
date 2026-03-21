from fastapi import APIRouter, HTTPException, Query, Response
from app.scrapers.ca import CAScraper, _is_maintenance_window
from app.scrapers.tx import TXScraper
from app.scrapers.fl import FLScraper

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
