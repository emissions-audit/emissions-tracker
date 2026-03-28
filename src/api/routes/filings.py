import uuid

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from src.shared.models import Filing
from src.shared.schemas import FilingResponse, PaginatedResponse


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["filings"])

    @router.get("/v1/companies/{company_id}/filings", response_model=PaginatedResponse)
    def company_filings(
        company_id: uuid.UUID,
        db: Session = get_db,
        year: int | None = Query(None),
        filing_type: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        query = db.query(Filing).filter(Filing.company_id == company_id)
        if year:
            query = query.filter(Filing.year == year)
        if filing_type:
            query = query.filter(Filing.filing_type == filing_type)
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return PaginatedResponse(
            items=[FilingResponse.model_validate(f) for f in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    return router
