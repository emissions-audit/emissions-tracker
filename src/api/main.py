from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes import companies, emissions
from src.api.routes import validation, pledges, filings
from src.api.routes import meta, export
from src.api.routes import health, coverage
from src.api.routes import quickstart, metrics
from src.api.routes import launch_metrics
from src.api.routes import discrepancies_page
from src.api.routes import project_stats
from src.api.routes import landing
from src.api.routes import enterprise
from src.api.routes import pricing
from src.api.routes import webhooks
from src.api.middleware.auth import ApiKeyMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.analytics import AnalyticsMiddleware
from src.api.middleware.first_call_tracking import FirstCallTrackingMiddleware


def create_app(db_session_override: AsyncSession | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Parameters
    ----------
    db_session_override:
        When provided (e.g. in tests), every request uses this session directly
        instead of creating one from the production async engine.
    """
    app = FastAPI(
        title="Emissions Tracker API",
        description="Open-source corporate emissions transparency tracker",
        version="0.1.0",
    )

    if db_session_override is not None:
        async def _get_db() -> AsyncGenerator[AsyncSession, None]:
            yield db_session_override

        # Middleware expects a factory that returns an async context manager
        # yielding a session. Wrap the override so auth/analytics can run in
        # tests without spinning up a real async engine.
        @asynccontextmanager
        async def _override_factory():
            yield db_session_override

        session_factory = _override_factory
    else:
        from src.shared.db import create_session_factory
        factory = create_session_factory()

        async def _get_db() -> AsyncGenerator[AsyncSession, None]:
            async with factory() as session:
                yield session

        session_factory = factory

    get_db = Depends(_get_db)

    # Middleware (last added = outermost = runs first)
    app.add_middleware(RateLimitMiddleware)
    # ET-79: added before ApiKeyMiddleware so it's *inner* to auth — by the time
    # it runs, request.state.api_key_id has already been resolved.
    app.add_middleware(FirstCallTrackingMiddleware, db_session_factory=session_factory)
    app.add_middleware(ApiKeyMiddleware, db_session_factory=session_factory)
    app.add_middleware(AnalyticsMiddleware, db_session_factory=session_factory)

    # Build fresh routers for this app instance to avoid route accumulation
    # when create_app is called multiple times (e.g. once per test).
    app.include_router(companies.build_router(get_db))
    app.include_router(emissions.build_router(get_db))
    app.include_router(validation.build_router(get_db))
    app.include_router(pledges.build_router(get_db))
    app.include_router(filings.build_router(get_db))
    app.include_router(meta.build_router(get_db))
    app.include_router(export.build_router(get_db))
    app.include_router(health.build_router(get_db))
    app.include_router(coverage.build_router(get_db))
    app.include_router(quickstart.build_router(get_db))
    app.include_router(metrics.build_router(get_db))
    app.include_router(launch_metrics.build_router(get_db))
    app.include_router(discrepancies_page.build_router(get_db))
    app.include_router(project_stats.build_router(get_db))
    app.include_router(landing.build_router(get_db))
    app.include_router(enterprise.build_router(get_db))
    app.include_router(pricing.build_router(get_db))
    app.include_router(webhooks.build_router(get_db))

    return app


# Module-level app instance for production use (uvicorn src.api.main:app).
# Deferred so that importing this module during tests (where DATABASE_URL is
# not set) does not trigger Settings validation.
def _make_production_app() -> FastAPI:
    try:
        return create_app()
    except Exception:
        # Gracefully skip if env is not configured (e.g. during test collection).
        return FastAPI(title="Emissions Tracker API (unconfigured)")


app = _make_production_app()
