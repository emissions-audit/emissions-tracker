import uuid

from fastapi import APIRouter, Query
from sqlalchemy import desc as sa_desc
from sqlalchemy.orm import Session

from src.shared.models import CrossValidation, SourceEntry, Company
from src.shared.schemas import CrossValidationResponse, DiscrepancyResponse, PaginatedResponse


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["validation"])

    @router.get("/v1/companies/{company_id}/validation", response_model=list[CrossValidationResponse])
    def company_validation(company_id: uuid.UUID, db: Session = get_db):
        cvs = db.query(CrossValidation).filter(CrossValidation.company_id == company_id).all()
        results = []
        for cv in cvs:
            entries = db.query(SourceEntry).filter(SourceEntry.cross_validation_id == cv.id).all()
            resp = CrossValidationResponse.model_validate(cv)
            resp.entries = [
                {"source_type": e.source_type, "value_mt_co2e": float(e.value_mt_co2e), "filing_id": e.filing_id}
                for e in entries
            ]
            results.append(resp)
        return results

    @router.get("/v1/discrepancies", response_model=PaginatedResponse)
    def list_discrepancies(
        db: Session = get_db,
        flag: str | None = Query(None),
        year: int | None = Query(None),
        sector: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        query = db.query(CrossValidation, Company.name).join(
            Company, CrossValidation.company_id == Company.id
        )
        if flag:
            query = query.filter(CrossValidation.flag == flag)
        if year:
            query = query.filter(CrossValidation.year == year)
        if sector:
            query = query.filter(Company.sector == sector)
        if not flag:
            query = query.filter(CrossValidation.flag.in_(["yellow", "red"]))
        total = query.count()
        rows = query.order_by(sa_desc(CrossValidation.spread_pct)).offset(offset).limit(limit).all()
        items = [
            DiscrepancyResponse(
                company_id=cv.company_id,
                company_name=name,
                year=cv.year,
                scope=cv.scope,
                spread_pct=float(cv.spread_pct),
                flag=cv.flag,
                source_count=cv.source_count,
                min_value=float(cv.min_value),
                max_value=float(cv.max_value),
            )
            for cv, name in rows
        ]
        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    @router.get("/v1/discrepancies/top", response_model=list[DiscrepancyResponse])
    def top_discrepancies(db: Session = get_db, limit: int = Query(10, ge=1, le=50)):
        rows = (
            db.query(CrossValidation, Company.name)
            .join(Company, CrossValidation.company_id == Company.id)
            .filter(CrossValidation.flag.in_(["yellow", "red"]))
            .order_by(sa_desc(CrossValidation.spread_pct))
            .limit(limit)
            .all()
        )
        return [
            DiscrepancyResponse(
                company_id=cv.company_id,
                company_name=name,
                year=cv.year,
                scope=cv.scope,
                spread_pct=float(cv.spread_pct),
                flag=cv.flag,
                source_count=cv.source_count,
                min_value=float(cv.min_value),
                max_value=float(cv.max_value),
            )
            for cv, name in rows
        ]

    return router
