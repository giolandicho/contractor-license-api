from fastapi import APIRouter, Response
from app.models.responses import StatesResponse, StateInfo
from app.data.state_info import STATE_INFO
from app.config import settings

router = APIRouter(tags=["States"])


@router.get("/states", response_model=StatesResponse)
async def get_states(response: Response):
    supported = []
    for code in ["CA", "TX", "FL", "NY"]:
        info = STATE_INFO[code]
        if code in settings.disabled_states_list:
            status = "disabled"
        elif code == "NY":
            status = "coming_soon"
        else:
            status = "active"
        supported.append(StateInfo(
            code=code,
            name=info["name"],
            agency=info["agency"],
            license_types=info.get("license_types", []),
            status=status,
            source_url=info["source_url"],
        ))
    response.headers["Cache-Control"] = "public, max-age=3600"
    return StatesResponse(supported_states=supported)
