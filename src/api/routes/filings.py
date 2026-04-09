import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Filing
from src.shared.schemas import FilingResponse, PaginatedResponse


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["filings"])

    @router.get("/v1/companies/{company_id}/filings", response_model=PaginatedResponse)
    async def company_filings(
        company_id: uuid.UUID,
        db: AsyncSession = get_db,
        year: int | None = Query(None),
        filing_type: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        stmt = select(Filing).where(Filing.company_id == company_id)
        if year:
            stmt = stmt.where(Filing.year == year)
        if filing_type:
            stmt = stmt.where(Filing.filing_type == filing_type)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0
        items = (await db.execute(stmt.offset(offset).limit(limit))).scalars().all()
        return PaginatedResponse(
            items=[FilingResponse.model_validate(f) for f in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    return router
