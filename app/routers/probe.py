from fastapi import APIRouter, HTTPException, Response
from app.scrapers.ca import CAScraper, _is_maintenance_window
from app.scrapers.base import ScraperUnavailableError

router = APIRouter(tags=["Probe"])

_scraper = CAScraper()


@router.get(
    "/probe",
    responses={
        200: {
            "description": "CA pipeline is reachable and responding.",
            "content": {"application/json": {"example": {"status": "ok", "state": "CA"}}},
        },
        503: {
            "description": "CA scraper is unreachable or in maintenance window.",
            "content": {"application/json": {"example": {"detail": "CSLB offline for maintenance (Sundays 8pm – Mondays 6am PT)"}}},
        },
    },
)
async def probe(response: Response):
    """
    End-to-end pipeline probe for UptimeRobot synthetic monitoring.
    No authentication required.

    Performs a live HTTP request to the CA (CSLB) portal and verifies the
    site is reachable and responding. Returns `{"status": "ok"}` on success.

    UptimeRobot keyword monitor: use `"ok"` as the keyword.
    Monitor interval: 15 minutes.

    During the CA maintenance window (Sundays 8pm – Mondays 6am PT) this
    endpoint returns 503 — configure UptimeRobot to suppress alerts during
    that window if needed.
    """
    try:
        ok = _scraper.health_check()
    except ScraperUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))

    if not ok:
        if _is_maintenance_window():
            raise HTTPException(
                status_code=503,
                detail="CA scraper offline: maintenance window (Sundays 8pm – Mondays 6am PT)",
            )
        raise HTTPException(status_code=503, detail="CA scraper health check failed")

    response.headers["Cache-Control"] = "no-cache"
    return {"status": "ok", "state": "CA"}
