import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_id = self._get_client_id(request)
        rate_limit = getattr(request.state, "rate_limit", 100)
        now = time.time()
        window = self._requests[client_id]
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= rate_limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        window.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(rate_limit - len(window))
        return response

    def _get_client_id(self, request: Request) -> str:
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key[:8]}"
        return f"ip:{request.client.host if request.client else 'unknown'}"
