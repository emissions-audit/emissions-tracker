import uuid

from fastapi import APIRouter, Query
from sqlalchemy import desc as sa_desc
from sqlalchemy.orm import Session

from src.shared.models import Emission, Company
from src.shared.schemas import EmissionResponse, PaginatedResponse, CompareRow

router = APIRouter(tags=["emissions"])


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with all emission routes bound to get_db."""
    r = APIRouter(tags=["emissions"])

    @r.get("/v1/companies/{company_id}/emissions", response_model=PaginatedResponse)
    def company_emissions(
        company_id: uuid.UUID,
        db: Session = get_db,
        year: int | None = Query(None),
        scope: str | None = Query(None),
        verified: bool | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        query = db.query(Emission).filter(Emission.company_id == company_id)
        if year:
            query = query.filter(Emission.year == year)
        if scope:
            query = query.filter(Emission.scope == scope)
        if verified is not None:
            query = query.filter(Emission.verified == verified)

        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return PaginatedResponse(
            items=[EmissionResponse.model_validate(e) for e in items],
            total=total, limit=limit, offset=offset,
        )

    @r.get("/v1/emissions", response_model=PaginatedResponse)
    def list_emissions(
        db: Session = get_db,
        year: int | None = Query(None),
        scope: str | None = Query(None),
        sector: str | None = Query(None),
        sort: str | None = Query(None),
        order: str = Query("asc"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        query = db.query(Emission)
        if year:
            query = query.filter(Emission.year == year)
        if scope:
            query = query.filter(Emission.scope == scope)
        if sector:
            query = query.join(Company).filter(Company.sector == sector)

        if sort == "value_mt_co2e":
            col = Emission.value_mt_co2e
            query = query.order_by(sa_desc(col) if order == "desc" else col)

        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return PaginatedResponse(
            items=[EmissionResponse.model_validate(e) for e in items],
            total=total, limit=limit, offset=offset,
        )

    @r.get("/v1/emissions/compare", response_model=list[CompareRow])
    def compare_emissions(
        db: Session = get_db,
        companies: str = Query(..., description="Comma-separated company UUIDs"),
        scopes: str = Query("1", description="Comma-separated scopes"),
        years: str = Query(..., description="Comma-separated years"),
    ):
        company_ids = [uuid.UUID(c.strip()) for c in companies.split(",")]
        scope_list = [s.strip() for s in scopes.split(",")]
        year_list = [int(y.strip()) for y in years.split(",")]

        rows = (
            db.query(Emission, Company.name)
            .join(Company)
            .filter(
                Emission.company_id.in_(company_ids),
                Emission.scope.in_(scope_list),
                Emission.year.in_(year_list),
            )
            .all()
        )

        return [
            CompareRow(
                company_id=e.company_id,
                company_name=name,
                year=e.year,
                scope=e.scope,
                value_mt_co2e=float(e.value_mt_co2e),
            )
            for e, name in rows
        ]

    return r


def register_routes(router: APIRouter, get_db):
    """Legacy interface: register routes onto an existing router instance."""
    @router.get("/v1/companies/{company_id}/emissions", response_model=PaginatedResponse)
    def company_emissions(
        company_id: uuid.UUID,
        db: Session = get_db,
        year: int | None = Query(None),
        scope: str | None = Query(None),
        verified: bool | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        query = db.query(Emission).filter(Emission.company_id == company_id)
        if year:
            query = query.filter(Emission.year == year)
        if scope:
            query = query.filter(Emission.scope == scope)
        if verified is not None:
            query = query.filter(Emission.verified == verified)

        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return PaginatedResponse(
            items=[EmissionResponse.model_validate(e) for e in items],
            total=total, limit=limit, offset=offset,
        )

    @router.get("/v1/emissions", response_model=PaginatedResponse)
    def list_emissions(
        db: Session = get_db,
        year: int | None = Query(None),
        scope: str | None = Query(None),
        sector: str | None = Query(None),
        sort: str | None = Query(None),
        order: str = Query("asc"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        query = db.query(Emission)
        if year:
            query = query.filter(Emission.year == year)
        if scope:
            query = query.filter(Emission.scope == scope)
        if sector:
            query = query.join(Company).filter(Company.sector == sector)

        if sort == "value_mt_co2e":
            col = Emission.value_mt_co2e
            query = query.order_by(sa_desc(col) if order == "desc" else col)

        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return PaginatedResponse(
            items=[EmissionResponse.model_validate(e) for e in items],
            total=total, limit=limit, offset=offset,
        )

    @router.get("/v1/emissions/compare", response_model=list[CompareRow])
    def compare_emissions(
        db: Session = get_db,
        companies: str = Query(..., description="Comma-separated company UUIDs"),
        scopes: str = Query("1", description="Comma-separated scopes"),
        years: str = Query(..., description="Comma-separated years"),
    ):
        company_ids = [uuid.UUID(c.strip()) for c in companies.split(",")]
        scope_list = [s.strip() for s in scopes.split(",")]
        year_list = [int(y.strip()) for y in years.split(",")]

        rows = (
            db.query(Emission, Company.name)
            .join(Company)
            .filter(
                Emission.company_id.in_(company_ids),
                Emission.scope.in_(scope_list),
                Emission.year.in_(year_list),
            )
            .all()
        )

        return [
            CompareRow(
                company_id=e.company_id,
                company_name=name,
                year=e.year,
                scope=e.scope,
                value_mt_co2e=float(e.value_mt_co2e),
            )
            for e, name in rows
        ]
