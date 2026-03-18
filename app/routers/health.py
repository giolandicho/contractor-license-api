import time
from datetime import datetime, timezone
from fastapi import APIRouter, Response
from app.models.responses import HealthResponse
from app.services.verification import check_state_health
from app.config import settings

router = APIRouter(tags=["Health"])

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health(response: Response):
    state_statuses = {}
    for state in ["CA", "TX", "FL"]:
        if state in settings.disabled_states_list:
            state_statuses[state] = "disabled"
        else:
            state_statuses[state] = check_state_health(state)
    state_statuses["NY"] = "coming_soon"

    response.headers["Cache-Control"] = "no-cache"
    return HealthResponse(
        status="ok",
        version="1.0.0",
        uptime_seconds=round(time.time() - _start_time, 2),
        states=state_statuses,
        checked_at=datetime.now(tz=timezone.utc),
    )
