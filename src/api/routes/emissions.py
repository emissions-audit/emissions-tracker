import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select, func, desc as sa_desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.corrections import apply_value, build_provenance, get_corrections
from src.shared.models import Emission, Company
from src.shared.schemas import (
    CompareRow,
    EmissionResponse,
    PaginatedResponse,
    ProvenanceResponse,
)

router = APIRouter(tags=["emissions"])


def _annotate(e: Emission, ticker: str | None, corrections: list) -> EmissionResponse:
    base = EmissionResponse.model_validate(e)
    base.value_mt_co2e = float(
        apply_value(
            "value_mt_co2e",
            base.value_mt_co2e,
            ticker,
            base.year,
            base.scope,
            corrections,
        )
    )
    prov = build_provenance(ticker, base.year, base.scope, corrections)
    if prov is not None:
        base.provenance = ProvenanceResponse.model_validate(prov)
    return base


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with all emission routes bound to get_db."""
    r = APIRouter(tags=["emissions"])

    @r.get("/v1/companies/{company_id}/emissions", response_model=PaginatedResponse)
    async def company_emissions(
        company_id: uuid.UUID,
        db: AsyncSession = get_db,
        year: int | None = Query(None),
        scope: str | None = Query(None),
        verified: bool | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        stmt = select(Emission).where(Emission.company_id == company_id)
        if year:
            stmt = stmt.where(Emission.year == year)
        if scope:
            stmt = stmt.where(Emission.scope == scope)
        if verified is not None:
            stmt = stmt.where(Emission.verified == verified)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0
        items = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()

        ticker_row = (
            await db.execute(select(Company.ticker).where(Company.id == company_id))
        ).first()
        ticker = ticker_row[0] if ticker_row else None
        corrections = get_corrections()

        return PaginatedResponse(
            items=[_annotate(e, ticker, corrections) for e in items],
            total=total, limit=limit, offset=offset,
        )

    @r.get("/v1/emissions", response_model=PaginatedResponse)
    async def list_emissions(
        db: AsyncSession = get_db,
        year: int | None = Query(None),
        scope: str | None = Query(None),
        sector: str | None = Query(None),
        sort: str | None = Query(None),
        order: str = Query("asc"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        stmt = select(Emission)
        if year:
            stmt = stmt.where(Emission.year == year)
        if scope:
            stmt = stmt.where(Emission.scope == scope)
        if sector:
            stmt = stmt.join(Company).where(Company.sector == sector)

        if sort == "value_mt_co2e":
            col = Emission.value_mt_co2e
            stmt = stmt.order_by(sa_desc(col) if order == "desc" else col)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0
        items = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()

        company_ids = list({e.company_id for e in items})
        ticker_map: dict[uuid.UUID, str | None] = {}
        if company_ids:
            rows = (
                await db.execute(
                    select(Company.id, Company.ticker).where(Company.id.in_(company_ids))
                )
            ).all()
            ticker_map = {cid: ticker for cid, ticker in rows}
        corrections = get_corrections()

        return PaginatedResponse(
            items=[_annotate(e, ticker_map.get(e.company_id), corrections) for e in items],
            total=total, limit=limit, offset=offset,
        )

    @r.get("/v1/emissions/compare", response_model=list[CompareRow])
    async def compare_emissions(
        db: AsyncSession = get_db,
        companies: str = Query(..., description="Comma-separated company UUIDs"),
        scopes: str = Query("1", description="Comma-separated scopes"),
        years: str = Query(..., description="Comma-separated years"),
    ):
        company_ids = [uuid.UUID(c.strip()) for c in companies.split(",")]
        scope_list = [s.strip() for s in scopes.split(",")]
        year_list = [int(y.strip()) for y in years.split(",")]

        stmt = (
            select(Emission, Company.name, Company.ticker)
            .join(Company)
            .where(
                Emission.company_id.in_(company_ids),
                Emission.scope.in_(scope_list),
                Emission.year.in_(year_list),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()
        corrections = get_corrections()

        return [
            CompareRow(
                company_id=e.company_id,
                company_name=name,
                year=e.year,
                scope=e.scope,
                value_mt_co2e=float(
                    apply_value(
                        "value_mt_co2e",
                        e.value_mt_co2e,
                        ticker,
                        e.year,
                        e.scope,
                        corrections,
                    )
                ),
            )
            for e, name, ticker in rows
        ]

    return r
