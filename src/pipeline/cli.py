import asyncio
import uuid
from datetime import datetime
from typing import Optional

import typer
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.shared.config import get_settings
from src.shared.models import Company, Filing, Emission
from src.pipeline.normalize import normalize_value, normalize_scope
from src.pipeline.sources.base import RawEmission
from src.pipeline.sources.edgar import EdgarSource
from src.pipeline.sources.climate_trace import ClimateTraceSource
from src.pipeline.sources.cdp import CdpSource
from src.pipeline.validate import compute_cross_validations
from src.pipeline.export import export_all

app = typer.Typer(name="emissions-pipeline", help="Corporate emissions data pipeline")

SOURCE_MAP = {
    "edgar": EdgarSource,
    "climate_trace": ClimateTraceSource,
    "cdp": CdpSource,
}

FILING_TYPE_TO_SOURCE_TYPE = {
    "10k_xbrl": "regulatory",
    "climate_trace": "satellite",
    "cdp_response": "voluntary",
    "sustainability_report": "self_reported",
    "csrd": "regulatory",
}


def _get_sync_session():
    url = get_settings().DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    return factory()


def _upsert_emissions(session, raw_emissions: list[RawEmission]):
    """Normalize and upsert emissions into the DB."""
    count = 0
    for raw in raw_emissions:
        company = session.query(Company).filter(Company.ticker == raw.company_ticker).first()
        if not company:
            continue

        filing = Filing(
            id=uuid.uuid4(),
            company_id=company.id,
            year=raw.year,
            filing_type=raw.filing_type,
            source_url=raw.source_url,
            parser_used=raw.parser_used,
            fetched_at=datetime.utcnow(),
        )
        session.add(filing)
        session.flush()

        try:
            normalized_value = normalize_value(raw.value, raw.unit)
            normalized_scope = normalize_scope(raw.scope)
        except ValueError:
            continue

        emission = Emission(
            id=uuid.uuid4(),
            company_id=company.id,
            year=raw.year,
            scope=normalized_scope,
            value_mt_co2e=normalized_value,
            methodology=raw.methodology,
            verified=raw.verified,
            source_id=filing.id,
        )
        session.merge(emission)
        count += 1

    session.commit()
    return count


@app.command()
def ingest(
    source: str = typer.Argument(help="Source: edgar, climate_trace, cdp"),
    tickers: Optional[str] = typer.Option(None, help="Comma-separated tickers"),
    years: str = typer.Option("2022,2023,2024", help="Comma-separated years"),
):
    """Fetch, parse, normalize, and load emissions data."""
    source_cls = SOURCE_MAP.get(source)
    if not source_cls:
        typer.echo(f"Unknown source: {source}. Available: {list(SOURCE_MAP.keys())}")
        raise typer.Exit(1)

    ticker_list = [t.strip() for t in tickers.split(",")] if tickers else []
    year_list = [int(y.strip()) for y in years.split(",")]

    typer.echo(f"Ingesting from {source}...")
    raw_emissions = asyncio.run(source_cls().fetch_emissions(ticker_list, year_list))
    typer.echo(f"Fetched {len(raw_emissions)} raw records")

    session = _get_sync_session()
    count = _upsert_emissions(session, raw_emissions)
    typer.echo(f"Upserted {count} emissions records")
    session.close()


@app.command()
def validate():
    """Run cross-validation across all emissions data."""
    from src.shared.models import CrossValidation, SourceEntry

    session = _get_sync_session()
    emissions = session.query(Emission).all()

    emission_dicts = [
        {"company_id": e.company_id, "year": e.year, "scope": e.scope,
         "value_mt_co2e": float(e.value_mt_co2e), "source_id": e.source_id}
        for e in emissions
    ]

    filings = {f.id: FILING_TYPE_TO_SOURCE_TYPE.get(f.filing_type, "unknown")
               for f in session.query(Filing).all()}

    results = compute_cross_validations(emission_dicts, filings)
    typer.echo(f"Computed {len(results)} cross-validations")

    for cv_data in results:
        cv = CrossValidation(
            id=uuid.uuid4(),
            company_id=cv_data["company_id"],
            year=cv_data["year"],
            scope=cv_data["scope"],
            source_count=cv_data["source_count"],
            min_value=cv_data["min_value"],
            max_value=cv_data["max_value"],
            spread_pct=cv_data["spread_pct"],
            flag=cv_data["flag"],
        )
        session.merge(cv)
        session.flush()

        for entry_data in cv_data["entries"]:
            entry = SourceEntry(
                id=uuid.uuid4(),
                cross_validation_id=cv.id,
                source_type=entry_data["source_type"],
                value_mt_co2e=entry_data["value_mt_co2e"],
                filing_id=entry_data.get("filing_id"),
            )
            session.add(entry)

    session.commit()
    session.close()

    flags = {"green": 0, "yellow": 0, "red": 0}
    for r in results:
        flags[r["flag"]] += 1
    typer.echo(f"Flags: {flags}")


@app.command()
def seed():
    """Seed the companies table with V1 energy companies."""
    from src.pipeline.sources.edgar import TICKER_TO_CIK
    from src.pipeline.sources.climate_trace import TICKER_TO_OWNER

    ENERGY_COMPANIES = {
        "XOM": ("ExxonMobil", "oil_gas_integrated", "US", "US30231G1022"),
        "CVX": ("Chevron", "oil_gas_integrated", "US", "US1667641005"),
        "SHEL": ("Shell plc", "oil_gas_integrated", "GB", "GB00BP6MXD84"),
        "BP": ("BP plc", "oil_gas_integrated", "GB", "GB0007980591"),
        "TTE": ("TotalEnergies", "oil_gas_integrated", "FR", "FR0000120271"),
        "COP": ("ConocoPhillips", "oil_gas_exploration", "US", "US20825C1045"),
        "ENI": ("Eni S.p.A.", "oil_gas_integrated", "IT", "IT0003132476"),
        "EQNR": ("Equinor ASA", "oil_gas_integrated", "NO", "NO0010096985"),
        "OXY": ("Occidental Petroleum", "oil_gas_exploration", "US", "US6745991058"),
        "MPC": ("Marathon Petroleum", "oil_gas_refining", "US", "US56585A1025"),
        "PSX": ("Phillips 66", "oil_gas_refining", "US", "US7185461040"),
        "VLO": ("Valero Energy", "oil_gas_refining", "US", "US91913Y1001"),
        "DVN": ("Devon Energy", "oil_gas_exploration", "US", "US25179M1036"),
        "HES": ("Hess Corporation", "oil_gas_exploration", "US", "US42809H1077"),
        "MRO": ("Marathon Oil", "oil_gas_exploration", "US", "US5658491064"),
        "EOG": ("EOG Resources", "oil_gas_exploration", "US", "US26875P1012"),
        "SLB": ("SLB (Schlumberger)", "oilfield_services", "US", "AN8068571086"),
        "BKR": ("Baker Hughes", "oilfield_services", "US", "US05722G1004"),
        "HAL": ("Halliburton", "oilfield_services", "US", "US4062161017"),
        "FANG": ("Diamondback Energy", "oil_gas_exploration", "US", "US25278X1090"),
    }

    session = _get_sync_session()
    count = 0
    for ticker, (name, subsector, country, isin) in ENERGY_COMPANIES.items():
        existing = session.query(Company).filter(Company.ticker == ticker).first()
        if existing:
            continue
        session.add(Company(
            id=uuid.uuid4(), name=name, ticker=ticker, sector="energy",
            subsector=subsector, country=country, isin=isin,
        ))
        count += 1

    session.commit()
    session.close()
    typer.echo(f"Seeded {count} companies")


@app.command()
def export(
    output: str = typer.Option("./data/export", help="Output directory for data dump"),
):
    """Export all data to JSON and CSV files for open data dump."""
    session = _get_sync_session()
    try:
        typer.echo(f"Exporting data to {output}...")
        files = export_all(session, output)
        typer.echo(f"Exported {len(files)} files:")
        for name, path in files.items():
            typer.echo(f"  {name}: {path}")
    finally:
        session.close()


if __name__ == "__main__":
    app()
