import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Company
from src.shared.schemas import CompanyResponse, PaginatedResponse
from src.api.deps import PaginationParams


router = APIRouter(prefix="/v1/companies", tags=["companies"])


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with routes bound to the given get_db dependency."""
    r = APIRouter(prefix="/v1/companies", tags=["companies"])

    @r.get("", response_model=PaginatedResponse)
    async def list_companies(
        db: AsyncSession = get_db,
        sector: str | None = Query(None),
        country: str | None = Query(None),
        subsector: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        stmt = select(Company)
        if sector:
            stmt = stmt.where(Company.sector == sector)
        if country:
            stmt = stmt.where(Company.country == country)
        if subsector:
            stmt = stmt.where(Company.subsector == subsector)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0
        items_result = await db.execute(stmt.offset(offset).limit(limit))
        items = items_result.scalars().all()
        return PaginatedResponse(
            items=[CompanyResponse.model_validate(c) for c in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    @r.get("/{company_id}", response_model=CompanyResponse)
    async def get_company(company_id: uuid.UUID, db: AsyncSession = get_db):
        result = await db.execute(select(Company).where(Company.id == company_id))
        company = result.scalars().first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return CompanyResponse.model_validate(company)

    return r
