import csv
import io
import uuid

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.shared.models import Company, Emission, Filing


def build_router(get_db) -> APIRouter:
    """Return a fresh APIRouter with export routes bound to get_db."""
    r = APIRouter(tags=["export"])

    def _require_pro(request: Request):
        tier = getattr(request.state, "tier", "anonymous")
        if tier not in ("pro", "enterprise"):
            raise HTTPException(status_code=403, detail="Pro tier required for bulk export")

    @r.get("/v1/export/full")
    def export_full(
        request: Request,
        db: Session = get_db,
        format: str = Query("json", pattern="^(json|csv)$"),
    ):
        _require_pro(request)

        companies = db.query(Company).all()
        emissions = db.query(Emission).all()

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "company_name", "ticker", "year", "scope",
                "value_mt_co2e", "methodology", "verified",
            ])

            company_map = {c.id: c for c in companies}
            for e in emissions:
                c = company_map.get(e.company_id)
                writer.writerow([
                    c.name if c else "", c.ticker if c else "",
                    e.year, e.scope, float(e.value_mt_co2e),
                    e.methodology, e.verified,
                ])

            output.seek(0)
            return StreamingResponse(
                output,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=emissions-export.csv"},
            )

        return {
            "companies": [
                {"id": str(c.id), "name": c.name, "ticker": c.ticker,
                 "sector": c.sector, "country": c.country}
                for c in companies
            ],
            "emissions": [
                {"company_id": str(e.company_id), "year": e.year, "scope": e.scope,
                 "value_mt_co2e": float(e.value_mt_co2e), "methodology": e.methodology,
                 "verified": e.verified}
                for e in emissions
            ],
        }

    @r.get("/v1/export/companies/{company_id}")
    def export_company(
        company_id: uuid.UUID,
        request: Request,
        db: Session = get_db,
        format: str = Query("json", pattern="^(json|csv)$"),
    ):
        _require_pro(request)

        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        emissions = db.query(Emission).filter(Emission.company_id == company_id).all()
        filings = db.query(Filing).filter(Filing.company_id == company_id).all()

        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["year", "scope", "value_mt_co2e", "methodology", "verified"])
            for e in emissions:
                writer.writerow([e.year, e.scope, float(e.value_mt_co2e), e.methodology, e.verified])
            output.seek(0)
            return StreamingResponse(
                output, media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={company.ticker}-emissions.csv"},
            )

        return {
            "company": {"id": str(company.id), "name": company.name, "ticker": company.ticker},
            "emissions": [
                {"year": e.year, "scope": e.scope, "value_mt_co2e": float(e.value_mt_co2e),
                 "methodology": e.methodology, "verified": e.verified}
                for e in emissions
            ],
            "filings": [
                {"year": f.year, "filing_type": f.filing_type, "source_url": f.source_url,
                 "parser_used": f.parser_used}
                for f in filings
            ],
        }

    return r
