"""Data export functions for generating open data dumps."""

import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from src.shared.models import Company, Emission, CrossValidation, SourceEntry


def export_companies_json(session: Session) -> list[dict]:
    """Export all companies as a list of dicts."""
    companies = session.query(Company).order_by(Company.name).all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "ticker": c.ticker,
            "sector": c.sector,
            "subsector": c.subsector,
            "country": c.country,
            "isin": c.isin,
        }
        for c in companies
    ]


def export_companies_csv(session: Session, output_path: str) -> None:
    """Export all companies to a CSV file."""
    companies = export_companies_json(session)
    if not companies:
        return
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=companies[0].keys())
        writer.writeheader()
        writer.writerows(companies)


def export_emissions_json(session: Session) -> list[dict]:
    """Export all emissions with company info as a list of dicts."""
    rows = (
        session.query(Emission, Company.name, Company.ticker)
        .join(Company, Emission.company_id == Company.id)
        .order_by(Company.name, Emission.year, Emission.scope)
        .all()
    )
    return [
        {
            "company_name": name,
            "company_ticker": ticker,
            "year": e.year,
            "scope": e.scope,
            "value_mt_co2e": float(e.value_mt_co2e),
            "methodology": e.methodology,
            "verified": e.verified,
        }
        for e, name, ticker in rows
    ]


def export_emissions_csv(session: Session, output_path: str) -> None:
    """Export all emissions to a CSV file."""
    emissions = export_emissions_json(session)
    if not emissions:
        return
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=emissions[0].keys())
        writer.writeheader()
        writer.writerows(emissions)


def export_cross_validations_json(session: Session) -> list[dict]:
    """Export all cross-validations with source entries as a list of dicts."""
    cvs = (
        session.query(CrossValidation)
        .order_by(CrossValidation.year, CrossValidation.scope)
        .all()
    )
    results = []
    for cv in cvs:
        company = session.query(Company).filter(Company.id == cv.company_id).first()
        entries = session.query(SourceEntry).filter(
            SourceEntry.cross_validation_id == cv.id
        ).all()
        results.append({
            "company_name": company.name if company else "Unknown",
            "company_ticker": company.ticker if company else None,
            "year": cv.year,
            "scope": cv.scope,
            "source_count": cv.source_count,
            "min_value": float(cv.min_value),
            "max_value": float(cv.max_value),
            "spread_pct": float(cv.spread_pct),
            "flag": cv.flag,
            "sources": [
                {"source_type": se.source_type, "value_mt_co2e": float(se.value_mt_co2e)}
                for se in entries
            ],
        })
    return results


def export_cross_validations_csv(session: Session, output_path: str) -> None:
    """Export cross-validations to a CSV file (flat, no nested sources)."""
    cvs = export_cross_validations_json(session)
    if not cvs:
        return
    flat = [{k: v for k, v in cv.items() if k != "sources"} for cv in cvs]
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=flat[0].keys())
        writer.writeheader()
        writer.writerows(flat)


def export_all(session: Session, output_dir: str) -> dict[str, str]:
    """Export all data to JSON and CSV files. Returns dict of {label: path}."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {}

    companies = export_companies_json(session)
    path = out / "companies.json"
    path.write_text(json.dumps(companies, indent=2))
    files["companies_json"] = str(path)

    emissions = export_emissions_json(session)
    path = out / "emissions.json"
    path.write_text(json.dumps(emissions, indent=2))
    files["emissions_json"] = str(path)

    cvs = export_cross_validations_json(session)
    path = out / "cross_validations.json"
    path.write_text(json.dumps(cvs, indent=2))
    files["cross_validations_json"] = str(path)

    export_companies_csv(session, str(out / "companies.csv"))
    files["companies_csv"] = str(out / "companies.csv")

    export_emissions_csv(session, str(out / "emissions.csv"))
    files["emissions_csv"] = str(out / "emissions.csv")

    export_cross_validations_csv(session, str(out / "cross_validations.csv"))
    files["cross_validations_csv"] = str(out / "cross_validations.csv")

    return files
