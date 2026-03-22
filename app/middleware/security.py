"""
Application-layer request hardening middleware.

Provides defense-in-depth against malformed and oversized requests before they reach
FastAPI routing. Equivalent to gateway-level block-mode schema validation for an API
with no infrastructure gateway.

Also adds security response headers to every outgoing response.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from fastapi import Request
from app.config import settings

_MAX_CONTENT_LENGTH = 32_768   # 32KB — this API has no request bodies; anything larger is anomalous
_MAX_QUERY_STRING_LENGTH = 2_048  # 2KB — generous for any legitimate query param use

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    """Outermost middleware: runs before auth on every request."""

    async def dispatch(self, request: Request, call_next):
        # In production, enforce HTTPS via X-Forwarded-Proto (Railway/Heroku style).
        # Standard HTTPSRedirectMiddleware causes redirect loops when the load balancer
        # terminates TLS — this check only fires when the *external* client used plain HTTP.
        if settings.env == "production":
            proto = request.headers.get("x-forwarded-proto")
            if proto == "http":
                https_url = str(request.url).replace("http://", "https://", 1)
                return RedirectResponse(url=https_url, status_code=301)

        # Reject oversized Content-Length before the request body is read
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > _MAX_CONTENT_LENGTH:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"},
                    )
            except ValueError:
                pass  # malformed header — let FastAPI handle it

        # Reject excessively long query strings
        if len(request.url.query) > _MAX_QUERY_STRING_LENGTH:
            return JSONResponse(
                status_code=400,
                content={"detail": "Query string too long"},
            )

        response = await call_next(request)

        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value

        return response
