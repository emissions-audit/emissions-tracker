from __future__ import annotations

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session, sessionmaker

from src.api.routes import companies, emissions
from src.api.routes import validation, pledges, filings
from src.api.routes import meta, export
from src.api.routes import health
from src.api.middleware.auth import ApiKeyMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.analytics import AnalyticsMiddleware


def create_app(db_session_override: Session | None = None) -> FastAPI:
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
        def _get_db() -> Session:
            return db_session_override
        # For middleware: create a factory from the test session's engine
        session_factory = sessionmaker(bind=db_session_override.get_bind())
    else:
        from src.shared.db import create_session_factory
        factory = create_session_factory()

        def _get_db() -> Session:
            return factory()
        session_factory = factory

    get_db = Depends(_get_db)

    # Middleware (last added = outermost = runs first)
    app.add_middleware(RateLimitMiddleware)
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
