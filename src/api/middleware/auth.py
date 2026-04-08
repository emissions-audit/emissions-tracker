import hashlib

from fastapi import Request
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from src.shared.models import ApiKey


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        api_key = request.headers.get("X-API-Key")
        if api_key is None:
            request.state.tier = "anonymous"
            request.state.rate_limit = 100
        else:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            if not self.db_session_factory:
                return JSONResponse(status_code=500, content={"detail": "No DB configured"})
            async with self.db_session_factory() as db:
                result = await db.execute(
                    select(ApiKey).filter(ApiKey.key_hash == key_hash)
                )
                db_key = result.scalar_one_or_none()
                if db_key is None:
                    return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
                request.state.tier = db_key.tier
                request.state.rate_limit = db_key.rate_limit
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit)
        return response
