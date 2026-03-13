from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request
from app.config import settings

EXCLUDED_PATHS = {"/health", "/states", "/docs", "/openapi.json", "/redoc"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.rstrip("/") in EXCLUDED_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        rapidapi_secret = request.headers.get("X-RapidAPI-Proxy-Secret")

        if rapidapi_secret and settings.rapidapi_proxy_secret:
            if rapidapi_secret == settings.rapidapi_proxy_secret:
                return await call_next(request)

        if api_key and api_key in settings.all_valid_keys:
            return await call_next(request)

        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid or missing API key. Provide X-API-Key header."},
        )
