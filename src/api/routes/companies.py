import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from src.shared.models import Company
from src.shared.schemas import CompanyResponse, PaginatedResponse
from src.api.deps import PaginationParams

# Module-level router used as a namespace/tag reference only.
# Routes are registered via register_routes() called from create_app().
router = APIRouter(prefix="/v1/companies", tags=["companies"])


def _list_companies(
    db: Session,
    pagination: PaginationParams,
    sector: str | None = None,
    country: str | None = None,
    subsector: str | None = None,
):
    query = db.query(Company)
    if sector:
        query = query.filter(Company.sector == sector)
    if country:
        query = query.filter(Company.country == country)
    if subsector:
        query = query.filter(Company.subsector == subsector)

    total = query.count()
    items = query.offset(pagination.offset).limit(pagination.limit).all()
    return PaginatedResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


def _get_company(db: Session, company_id: uuid.UUID):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with routes bound to the given get_db dependency."""
    r = APIRouter(prefix="/v1/companies", tags=["companies"])

    @r.get("", response_model=PaginatedResponse)
    def list_companies(
        db: Session = get_db,
        sector: str | None = Query(None),
        country: str | None = Query(None),
        subsector: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        pagination = PaginationParams(limit=limit, offset=offset)
        return _list_companies(db, pagination, sector, country, subsector)

    @r.get("/{company_id}", response_model=CompanyResponse)
    def get_company(company_id: uuid.UUID, db: Session = get_db):
        return _get_company(db, company_id)

    return r


def register_routes(router: APIRouter, get_db):
    """Legacy interface: register routes onto an existing router instance."""
    @router.get("", response_model=PaginatedResponse)
    def list_companies(
        db: Session = get_db,
        sector: str | None = Query(None),
        country: str | None = Query(None),
        subsector: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        pagination = PaginationParams(limit=limit, offset=offset)
        return _list_companies(db, pagination, sector, country, subsector)

    @router.get("/{company_id}", response_model=CompanyResponse)
    def get_company(company_id: uuid.UUID, db: Session = get_db):
        return _get_company(db, company_id)
