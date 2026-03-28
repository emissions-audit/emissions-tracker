import hashlib

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from sqlalchemy.orm import Session

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
            db = self._get_db()
            try:
                db_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
                if db_key is None:
                    return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
                request.state.tier = db_key.tier
                request.state.rate_limit = db_key.rate_limit
            finally:
                if self.db_session_factory:
                    db.close()
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit)
        return response

    def _get_db(self):
        if self.db_session_factory:
            return self.db_session_factory()
        raise RuntimeError("No DB session factory configured")
