from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.shared.models import Company, Emission, Filing
from src.shared.schemas import StatsResponse


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with meta/stats routes bound to get_db."""
    r = APIRouter(tags=["meta"])

    @r.get("/v1/stats", response_model=StatsResponse)
    def stats(db: Session = get_db):
        company_count = db.query(func.count(Company.id)).scalar() or 0
        filing_count = db.query(func.count(Filing.id)).scalar() or 0
        emission_count = db.query(func.count(Emission.id)).scalar() or 0
        min_year = db.query(func.min(Emission.year)).scalar() or 0
        max_year = db.query(func.max(Emission.year)).scalar() or 0
        last_filing = db.query(func.max(Filing.fetched_at)).scalar() or datetime.utcnow()

        return StatsResponse(
            company_count=company_count,
            filing_count=filing_count,
            emission_count=emission_count,
            year_range={"min": min_year, "max": max_year},
            last_updated=last_filing,
        )

    @r.get("/v1/meta/sectors")
    def meta_sectors(db: Session = get_db):
        rows = (
            db.query(Company.sector, Company.subsector, func.count(Company.id))
            .group_by(Company.sector, Company.subsector)
            .all()
        )
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

    return r
