from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import CoverageSnapshot


# Captured at import time. Good-enough uptime signal for launch readiness.
STARTED_AT = datetime.now(timezone.utc)
_VERSION = "0.1.0"


def _sources_active(by_source_year: dict | None) -> int:
    if not by_source_year:
        return 0
    return sum(1 for years in by_source_year.values() if years)


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["metrics"])

    @router.get("/v1/metrics")
    async def metrics(db: AsyncSession = get_db):
        now = datetime.now(timezone.utc)
        uptime = int((now - STARTED_AT).total_seconds())
        if uptime < 0:
            uptime = 0

        # Database connectivity probe (mirrors /ready).
        try:
            await db.execute(text("SELECT 1"))
            database_status = "connected"
        except Exception:
            database_status = "disconnected"

        # Latest coverage snapshot, if any.
        coverage_payload: dict | None
        try:
            result = await db.execute(
                select(CoverageSnapshot)
                .order_by(CoverageSnapshot.computed_at.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
        except Exception:
            snapshot = None

        if snapshot is None:
            coverage_payload = None
        else:
            by_source_year = snapshot.by_source_year or {}
            coverage_payload = {
                "sources_active": _sources_active(by_source_year),
                "sources_total": len(by_source_year),
                "total_emissions_rows": snapshot.total_emissions,
            }

        return {
            "uptime_seconds": uptime,
            "started_at": STARTED_AT.isoformat().replace("+00:00", "Z"),
            "version": _VERSION,
            "coverage": coverage_payload,
            "database": database_status,
        }

    return router
