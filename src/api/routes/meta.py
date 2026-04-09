from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Company, Emission, Filing, ApiCallLog
from src.shared.schemas import StatsResponse, AnalyticsSummaryResponse


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with meta/stats routes bound to get_db."""
    r = APIRouter(tags=["meta"])

    @r.get("/v1/stats", response_model=StatsResponse)
    async def stats(db: AsyncSession = get_db):
        company_count = (await db.execute(select(func.count(Company.id)))).scalar() or 0
        filing_count = (await db.execute(select(func.count(Filing.id)))).scalar() or 0
        emission_count = (await db.execute(select(func.count(Emission.id)))).scalar() or 0
        min_year = (await db.execute(select(func.min(Emission.year)))).scalar() or 0
        max_year = (await db.execute(select(func.max(Emission.year)))).scalar() or 0
        last_filing = (await db.execute(select(func.max(Filing.fetched_at)))).scalar() or datetime.utcnow()

        return StatsResponse(
            company_count=company_count,
            filing_count=filing_count,
            emission_count=emission_count,
            year_range={"min": min_year, "max": max_year},
            last_updated=last_filing,
        )

    @r.get("/v1/meta/sectors")
    async def meta_sectors(db: AsyncSession = get_db):
        stmt = (
            select(Company.sector, Company.subsector, func.count(Company.id))
            .group_by(Company.sector, Company.subsector)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {"sector": sector, "subsector": subsector, "company_count": count}
            for sector, subsector, count in rows
        ]

    @r.get("/v1/meta/methodology")
    def meta_methodology():
        return {
            "normalization": {
                "unit": "mt_co2e (metric tons CO2 equivalent)",
                "scopes": ["1", "2", "3", "1+2", "total"],
                "methodology_standards": ["ghg_protocol", "iso_14064"],
            },
            "sources": [
                {"name": "SEC EDGAR", "type": "regulatory", "trust_rank": 1,
                 "description": "XBRL filings from US-listed companies"},
                {"name": "Climate TRACE", "type": "satellite", "trust_rank": 2,
                 "description": "Satellite-derived facility-level emissions"},
                {"name": "CDP", "type": "voluntary", "trust_rank": 3,
                 "description": "Self-reported standardized disclosures"},
                {"name": "Sustainability Reports", "type": "self_reported", "trust_rank": 4,
                 "description": "Company-published PDF reports, LLM-extracted"},
            ],
            "cross_validation": {
                "green": "< 10% spread between sources",
                "yellow": "10-30% spread",
                "red": "> 30% spread — major discrepancy",
            },
        }

    @r.get("/v1/analytics/summary", response_model=AnalyticsSummaryResponse)
    async def analytics_summary(db: AsyncSession = get_db, days: int = 30):
        cutoff = datetime.utcnow() - timedelta(days=days)

        total_calls = (await db.execute(
            select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at >= cutoff)
        )).scalar() or 0

        unique_keys = (await db.execute(
            select(func.count(func.distinct(ApiCallLog.api_key_hash)))
            .where(ApiCallLog.created_at >= cutoff, ApiCallLog.api_key_hash.isnot(None))
        )).scalar() or 0

        avg_rt = (await db.execute(
            select(func.avg(ApiCallLog.response_time_ms)).where(ApiCallLog.created_at >= cutoff)
        )).scalar() or 0.0

        top_endpoints = (await db.execute(
            select(ApiCallLog.endpoint, func.count(ApiCallLog.id).label("calls"))
            .where(ApiCallLog.created_at >= cutoff)
            .group_by(ApiCallLog.endpoint)
            .order_by(func.count(ApiCallLog.id).desc())
            .limit(10)
        )).all()

        tier_counts = (await db.execute(
            select(ApiCallLog.tier, func.count(ApiCallLog.id))
            .where(ApiCallLog.created_at >= cutoff)
            .group_by(ApiCallLog.tier)
        )).all()

        return AnalyticsSummaryResponse(
            period_days=days,
            total_calls=total_calls,
            unique_api_keys=unique_keys,
            avg_response_time_ms=round(float(avg_rt), 2),
            top_endpoints=[
                {"endpoint": ep, "calls": count}
                for ep, count in top_endpoints
            ],
            calls_by_tier={tier: count for tier, count in tier_counts},
        )

    return r
