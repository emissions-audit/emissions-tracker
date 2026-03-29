import hashlib
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from src.shared.models import ApiCallLog

SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/favicon.ico"}


class AnalyticsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000

        self._log_request(request, response, duration_ms)
        return response

    def _log_request(self, request: Request, response: Response, duration_ms: float) -> None:
        if not self.db_session_factory:
            return

        api_key = request.headers.get("X-API-Key")
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16] if api_key else None
        tier = getattr(request.state, "tier", "anonymous")
        client_ip = request.client.host if request.client else None

        db = self.db_session_factory()
        try:
            log = ApiCallLog(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=round(duration_ms, 2),
                api_key_hash=api_key_hash,
                tier=tier,
                client_ip=client_ip,
            )
            db.add(log)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
