from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import CoverageSnapshot
from src.shared.schemas import (
    CoverageResponse,
    CoverageSummary,
    CoverageAlertResponse,
    CoverageHealthResponse,
    CoverageHistoryResponse,
    CoverageHistoryEntry,
)


def _sources_active(by_source_year: dict) -> int:
    return sum(1 for years in by_source_year.values() if years)


def build_router(get_db) -> APIRouter:
    r = APIRouter(tags=["coverage"])

    @r.get("/v1/coverage", response_model=CoverageResponse)
    async def coverage(
        db: AsyncSession = get_db,
        view: Optional[str] = Query(None, pattern="^(source_year|company_source|company_year)$"),
        alerts_only: bool = Query(False),
    ):
        result = await db.execute(
            select(CoverageSnapshot)
            .order_by(CoverageSnapshot.computed_at.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            return CoverageResponse(
                computed_at=datetime.utcnow(),
                trigger="none",
                summary=CoverageSummary(
                    total_companies=0, total_emissions=0, total_filings=0,
                    total_cross_validations=0, year_range={"min": None, "max": None},
                    cv_coverage_pct=0.0, sources_active=0, sources_total=0,
                ),
                by_source_year={}, by_company_source={}, by_company_year={},
                cv_by_flag={"green": 0, "yellow": 0, "red": 0},
                alerts=[],
            )

        alerts = [CoverageAlertResponse(**a) for a in (snapshot.alerts or [])]

        summary = CoverageSummary(
            total_companies=snapshot.total_companies,
            total_emissions=snapshot.total_emissions,
            total_filings=snapshot.total_filings,
            total_cross_validations=snapshot.total_cross_validations,
            year_range={"min": snapshot.year_min, "max": snapshot.year_max},
            cv_coverage_pct=float(snapshot.cv_coverage_pct),
            sources_active=_sources_active(snapshot.by_source_year),
            sources_total=len(snapshot.by_source_year),
        )

        if alerts_only:
            return CoverageResponse(
                computed_at=snapshot.computed_at, trigger=snapshot.trigger,
                summary=summary,
                by_source_year=None, by_company_source=None, by_company_year=None,
                cv_by_flag=snapshot.cv_by_flag, alerts=alerts,
            )

        by_source_year = snapshot.by_source_year if view in (None, "source_year") else None
        by_company_source = snapshot.by_company_source if view in (None, "company_source") else None
        by_company_year = snapshot.by_company_year if view in (None, "company_year") else None

        return CoverageResponse(
            computed_at=snapshot.computed_at, trigger=snapshot.trigger,
            summary=summary,
            by_source_year=by_source_year,
            by_company_source=by_company_source,
            by_company_year=by_company_year,
            cv_by_flag=snapshot.cv_by_flag, alerts=alerts,
        )

    @r.get("/v1/coverage/health", response_model=CoverageHealthResponse)
    async def coverage_health(db: AsyncSession = get_db):
        result = await db.execute(
            select(CoverageSnapshot)
            .order_by(CoverageSnapshot.computed_at.desc())
            .limit(1)
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            return CoverageHealthResponse(
                status="healthy", computed_at=None,
                alerts_critical=0, alerts_warning=0, alerts_info=0, alerts=[],
            )

        alerts = snapshot.alerts or []
        counts = {"critical": 0, "warning": 0, "info": 0}
        for a in alerts:
            counts[a.get("severity", "info")] += 1

        if counts["critical"] > 0:
            status = "critical"
        elif counts["warning"] > 0:
            status = "warning"
        elif counts["info"] > 0:
            status = "info"
        else:
            status = "healthy"

        return CoverageHealthResponse(
            status=status,
            computed_at=snapshot.computed_at,
            alerts_critical=counts["critical"],
            alerts_warning=counts["warning"],
            alerts_info=counts["info"],
            alerts=[CoverageAlertResponse(**a) for a in alerts],
        )

    @r.get("/v1/coverage/history", response_model=CoverageHistoryResponse)
    async def coverage_history(
        db: AsyncSession = get_db,
        days: int = Query(30, ge=1, le=365),
    ):
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(CoverageSnapshot)
            .where(CoverageSnapshot.computed_at >= cutoff)
            .order_by(CoverageSnapshot.computed_at.desc())
        )
        snapshots = result.scalars().all()

        entries = [
            CoverageHistoryEntry(
                computed_at=s.computed_at,
                total_emissions=s.total_emissions,
                sources_active=_sources_active(s.by_source_year),
                cv_coverage_pct=float(s.cv_coverage_pct),
                cv_by_flag=s.cv_by_flag,
                alert_count=len(s.alerts or []),
            )
            for s in snapshots
        ]

        return CoverageHistoryResponse(snapshots=entries)

    return r
