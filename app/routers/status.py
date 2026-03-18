from datetime import datetime, timezone
from fastapi import APIRouter, Response
from app.cache.state_status import get_all

router = APIRouter(tags=["Status"])


@router.get(
    "/status",
    responses={
        200: {
            "description": "Per-state pipeline health. `status` per state: `operational`, `degraded`, or `unknown`.",
            "content": {"application/json": {"example": {
                "states": {
                    "CA": {"status": "operational", "last_success": "2024-01-15T18:00:00+00:00", "last_failure": None},
                    "TX": {"status": "unknown", "last_success": None, "last_failure": None},
                    "FL": {"status": "degraded", "last_success": "2024-01-15T10:00:00+00:00", "last_failure": "2024-01-15T17:00:00+00:00"},
                },
                "checked_at": "2024-01-15T18:30:00+00:00",
            }}},
        },
    },
)
async def status(response: Response):
    """
    Per-state pipeline health based on recent live traffic.

    Status values per state:
    - `operational` — successful scrape within the last 60 minutes
    - `degraded` — last successful scrape was more than 60 minutes ago
    - `unknown` — no traffic recorded since last deploy

    UptimeRobot keyword monitor: use `"states"` as the keyword (structural key,
    always present regardless of per-state values).
    """
    response.headers["Cache-Control"] = "no-cache"
    return {
        "states": get_all(),
        "checked_at": datetime.now(tz=timezone.utc).isoformat(),
    }
