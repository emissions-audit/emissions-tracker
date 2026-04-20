"""ET-79: First-call instrumentation middleware.

Stamps ``ApiKey.first_api_call_at`` the first time an authenticated request
arrives for a given key. Idempotent — only the first call writes; subsequent
calls are a no-op because the SQL-level ``WHERE first_api_call_at IS NULL``
guard blocks the update.

Runs *after* :class:`src.api.middleware.auth.ApiKeyMiddleware` has resolved
``request.state.api_key_id`` — so in ``create_app`` this middleware must be
registered BEFORE ``ApiKeyMiddleware`` (Starlette wraps in reverse: the last
added is outermost, so added-first means inner to auth and sees the resolved
state).

Fire-and-forget: any DB error is swallowed (logged). The user's request MUST
NOT fail because analytics instrumentation couldn't write.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import Request
from sqlalchemy import update
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from src.shared.models import ApiKey

logger = logging.getLogger(__name__)


class FirstCallTrackingMiddleware(BaseHTTPMiddleware):
    """Stamps ``ApiKey.first_api_call_at`` exactly once per key."""

    def __init__(self, app, db_session_factory=None):
        super().__init__(app)
        self.db_session_factory = db_session_factory

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Let the request proceed first; instrumentation must never block or
        # slow the response path.
        response = await call_next(request)

        api_key_id = getattr(request.state, "api_key_id", None)
        if api_key_id is None or self.db_session_factory is None:
            return response

        try:
            async with self.db_session_factory() as db:
                # Atomic single-row UPDATE with a NULL guard — avoids the
                # race condition of load-then-set (two concurrent first calls
                # from the same key would otherwise both write). The WHERE
                # clause makes the update a no-op on any call after the first.
                stmt = (
                    update(ApiKey)
                    .where(ApiKey.id == api_key_id)
                    .where(ApiKey.first_api_call_at.is_(None))
                    .values(first_api_call_at=datetime.utcnow())
                )
                await db.execute(stmt)
                await db.commit()
        except Exception:
            # Fire-and-forget: analytics failures must not affect the response.
            logger.exception("first_call_tracking: failed to stamp first_api_call_at")

        return response
