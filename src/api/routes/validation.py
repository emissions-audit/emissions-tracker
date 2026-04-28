import csv
import io
import uuid

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc as sa_desc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import CrossValidation, SourceEntry, Company, Filing
from src.shared.schemas import CrossValidationResponse, DiscrepancyResponse, DiscrepancySourceDetail, PaginatedResponse


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["validation"])

    @router.get("/v1/companies/{company_id}/validation", response_model=list[CrossValidationResponse])
    async def company_validation(company_id: uuid.UUID, db: AsyncSession = get_db):
        cvs = (await db.execute(
            select(CrossValidation).where(CrossValidation.company_id == company_id)
        )).scalars().all()
        results = []
        for cv in cvs:
            entries = (await db.execute(
                select(SourceEntry).where(SourceEntry.cross_validation_id == cv.id)
            )).scalars().all()
            # Load filing URLs for provenance
            filing_ids = [e.filing_id for e in entries if e.filing_id]
            filings = {}
            if filing_ids:
                filing_rows = (await db.execute(
                    select(Filing).where(Filing.id.in_(filing_ids))
                )).scalars().all()
                filings = {f.id: f for f in filing_rows}
            resp = CrossValidationResponse.model_validate(cv)
            resp.entries = [
                {
                    "source_type": e.source_type,
                    "value_t_co2e": float(e.value_t_co2e),
                    "filing_id": e.filing_id,
                    "filing_url": filings[e.filing_id].source_url if e.filing_id and e.filing_id in filings else None,
                }
                for e in entries
            ]
            results.append(resp)
        return results

    @router.get("/v1/discrepancies", response_model=PaginatedResponse)
    async def list_discrepancies(
        db: AsyncSession = get_db,
        flag: str | None = Query(None),
        year: int | None = Query(None),
        sector: str | None = Query(None),
        company: str | None = Query(None, description="Company name substring"),
        ticker: str | None = Query(None, description="Exact ticker symbol"),
        min_delta: float | None = Query(None, ge=0, description="Minimum absolute delta (MtCO2e)"),
        sort: str = Query("spread_pct", pattern="^(spread_pct|delta|ticker)$"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        base = (
            select(CrossValidation, Company.name, Company.ticker)
            .join(Company, CrossValidation.company_id == Company.id)
        )
        if flag:
            base = base.where(CrossValidation.flag == flag)
        else:
            base = base.where(CrossValidation.flag.in_(["yellow", "red"]))
        if year:
            base = base.where(CrossValidation.year == year)
        if sector:
            base = base.where(Company.sector == sector)
        if company:
            base = base.where(Company.name.ilike(f"%{company}%"))
        if ticker:
            base = base.where(Company.ticker == ticker)
        if min_delta is not None:
            base = base.where(
                (CrossValidation.max_value - CrossValidation.min_value) >= min_delta
            )

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        sort_col = {
            "spread_pct": sa_desc(CrossValidation.spread_pct),
            "delta": sa_desc(CrossValidation.max_value - CrossValidation.min_value),
            "ticker": Company.ticker,
        }[sort]

        data_stmt = (
            base
            .order_by(sort_col)
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(data_stmt)).all()

        items = []
        for cv, name, tkr in rows:
            entries = (await db.execute(
                select(SourceEntry).where(SourceEntry.cross_validation_id == cv.id)
            )).scalars().all()
            sources = []
            for e in entries:
                filing_url = None
                if e.filing_id:
                    filing = (await db.execute(
                        select(Filing).where(Filing.id == e.filing_id)
                    )).scalar_one_or_none()
                    if filing:
                        filing_url = filing.source_url
                sources.append(DiscrepancySourceDetail(
                    source_type=e.source_type,
                    value_t_co2e=float(e.value_t_co2e),
                    filing_url=filing_url,
                ))
            items.append(DiscrepancyResponse(
                company_id=cv.company_id,
                company_name=name,
                ticker=tkr,
                year=cv.year,
                scope=cv.scope,
                spread_pct=float(cv.spread_pct),
                delta_mt_co2e=float(cv.max_value - cv.min_value),
                flag=cv.flag,
                source_count=cv.source_count,
                min_value=float(cv.min_value),
                max_value=float(cv.max_value),
                sources=sources,
            ))
        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    @router.get("/v1/discrepancies/top", response_model=list[DiscrepancyResponse])
    async def top_discrepancies(db: AsyncSession = get_db, limit: int = Query(10, ge=1, le=50)):
        stmt = (
            select(CrossValidation, Company.name, Company.ticker)
            .join(Company, CrossValidation.company_id == Company.id)
            .where(CrossValidation.flag.in_(["yellow", "red"]))
            .order_by(sa_desc(CrossValidation.spread_pct))
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        items = []
        for cv, name, tkr in rows:
            entries = (await db.execute(
                select(SourceEntry).where(SourceEntry.cross_validation_id == cv.id)
            )).scalars().all()
            sources = []
            for e in entries:
                filing_url = None
                if e.filing_id:
                    filing = (await db.execute(
                        select(Filing).where(Filing.id == e.filing_id)
                    )).scalar_one_or_none()
                    if filing:
                        filing_url = filing.source_url
                sources.append(DiscrepancySourceDetail(
                    source_type=e.source_type,
                    value_t_co2e=float(e.value_t_co2e),
                    filing_url=filing_url,
                ))
            items.append(DiscrepancyResponse(
                company_id=cv.company_id,
                company_name=name,
                ticker=tkr,
                year=cv.year,
                scope=cv.scope,
                spread_pct=float(cv.spread_pct),
                delta_mt_co2e=float(cv.max_value - cv.min_value),
                flag=cv.flag,
                source_count=cv.source_count,
                min_value=float(cv.min_value),
                max_value=float(cv.max_value),
                sources=sources,
            ))
        return items

    @router.get("/v1/discrepancies.csv")
    async def discrepancies_csv(
        db: AsyncSession = get_db,
        flag: str | None = Query(None),
        year: int | None = Query(None),
        sector: str | None = Query(None),
    ):
        base = (
            select(CrossValidation, Company.name, Company.ticker)
            .join(Company, CrossValidation.company_id == Company.id)
        )
        if flag:
            base = base.where(CrossValidation.flag == flag)
        else:
            base = base.where(CrossValidation.flag.in_(["yellow", "red"]))
        if year:
            base = base.where(CrossValidation.year == year)
        if sector:
            base = base.where(Company.sector == sector)

        rows = (await db.execute(
            base.order_by(sa_desc(CrossValidation.spread_pct))
        )).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "company_name", "ticker", "year", "scope",
            "min_value_t_co2e", "spread_pct", "delta_mt_co2e",
            "max_value_t_co2e", "flag", "source_count",
        ])
        for cv, name, tkr in rows:
            writer.writerow([
                name, tkr, cv.year, cv.scope,
                float(cv.min_value), float(cv.spread_pct),
                float(cv.max_value - cv.min_value),
                float(cv.max_value), cv.flag, cv.source_count,
            ])

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=discrepancies.csv"},
        )

    return router
