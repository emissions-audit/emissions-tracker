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
from src.pipeline.sources.carb import CarbSource
from src.pipeline.sources.epa_ghgrp import EpaGhgrpSource
from src.pipeline.sources.eu_ets import EuEtsSource
from src.pipeline.validate import compute_cross_validations
from src.pipeline.export import export_all
from src.pipeline.coverage import create_snapshot, format_report, format_brief

app = typer.Typer(name="emissions-pipeline", help="Corporate emissions data pipeline")

SOURCE_MAP = {
    "edgar": EdgarSource,
    "climate_trace": ClimateTraceSource,
    "cdp": CdpSource,
    "carb": CarbSource,
    "epa_ghgrp": EpaGhgrpSource,
    "eu_ets": EuEtsSource,
}

FILING_TYPE_TO_SOURCE_TYPE = {
    "10k_xbrl": "regulatory",
    "climate_trace": "satellite",
    "cdp_response": "voluntary",
    "sustainability_report": "self_reported",
    "csrd": "regulatory",
    "carb_sb253": "regulatory",
    "epa_ghgrp": "regulatory",
    "eu_ets": "regulatory",
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

    # Post-ingest coverage snapshot
    snapshot = create_snapshot(session, trigger="post_ingest", source_filter=source)
    brief_data = {
        "total_emissions": snapshot.total_emissions,
        "by_source_year": snapshot.by_source_year,
        "cv_coverage_pct": float(snapshot.cv_coverage_pct),
        "alerts": snapshot.alerts,
    }
    typer.echo(format_brief(brief_data))

    # Fire webhook events
    from src.shared.webhooks import fire_event_sync

    fire_event_sync("ingestion_complete", {
        "source": source,
        "records_upserted": count,
        "total_emissions": snapshot.total_emissions,
    }, session)
    if count > 0:
        fire_event_sync("new_emission", {
            "source": source,
            "count": count,
        }, session)
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

    # Post-validate coverage snapshot
    session_cov = _get_sync_session()
    snapshot = create_snapshot(session_cov, trigger="post_validate")
    brief_data = {
        "total_emissions": snapshot.total_emissions,
        "by_source_year": snapshot.by_source_year,
        "cv_coverage_pct": float(snapshot.cv_coverage_pct),
        "alerts": snapshot.alerts,
    }
    typer.echo(format_brief(brief_data))

    # Fire webhook for new discrepancies and coverage updates
    from src.shared.webhooks import fire_event_sync

    red_count = flags.get("red", 0)
    yellow_count = flags.get("yellow", 0)
    if red_count > 0 or yellow_count > 0:
        fire_event_sync("new_discrepancy", {
            "red": red_count,
            "yellow": yellow_count,
            "green": flags.get("green", 0),
            "total": len(results),
        }, session_cov)
    fire_event_sync("coverage_update", {
        "total_emissions": snapshot.total_emissions,
        "cv_coverage_pct": float(snapshot.cv_coverage_pct),
        "cv_by_flag": snapshot.cv_by_flag,
    }, session_cov)
    session_cov.close()


@app.command()
def seed():
    """Seed the companies table with V1 energy companies."""
    from src.pipeline.sources.edgar import TICKER_TO_CIK
    from src.pipeline.sources.climate_trace import TICKER_TO_OWNER

    ENERGY_COMPANIES = {
        # --- Oil & Gas: Integrated majors ---
        "XOM": ("ExxonMobil", "oil_gas_integrated", "US", "US30231G1022"),
        "CVX": ("Chevron", "oil_gas_integrated", "US", "US1667641005"),
        "SHEL": ("Shell plc", "oil_gas_integrated", "GB", "GB00BP6MXD84"),
        "BP": ("BP plc", "oil_gas_integrated", "GB", "GB0007980591"),
        "TTE": ("TotalEnergies", "oil_gas_integrated", "FR", "FR0000120271"),
        "COP": ("ConocoPhillips", "oil_gas_exploration", "US", "US20825C1045"),
        "ENI": ("Eni S.p.A.", "oil_gas_integrated", "IT", "IT0003132476"),
        "EQNR": ("Equinor ASA", "oil_gas_integrated", "NO", "NO0010096985"),
        # --- Oil & Gas: E&P ---
        "OXY": ("Occidental Petroleum", "oil_gas_exploration", "US", "US6745991058"),
        "DVN": ("Devon Energy", "oil_gas_exploration", "US", "US25179M1036"),
        "HES": ("Hess Corporation", "oil_gas_exploration", "US", "US42809H1077"),
        "MRO": ("Marathon Oil", "oil_gas_exploration", "US", "US5658491064"),
        "EOG": ("EOG Resources", "oil_gas_exploration", "US", "US26875P1012"),
        "FANG": ("Diamondback Energy", "oil_gas_exploration", "US", "US25278X1090"),
        "PXD": ("Pioneer Natural Resources", "oil_gas_exploration", "US", "US7237871071"),
        "CTRA": ("Coterra Energy", "oil_gas_exploration", "US", "US1270971039"),
        # --- Oil & Gas: Refining ---
        "MPC": ("Marathon Petroleum", "oil_gas_refining", "US", "US56585A1025"),
        "PSX": ("Phillips 66", "oil_gas_refining", "US", "US7185461040"),
        "VLO": ("Valero Energy", "oil_gas_refining", "US", "US91913Y1001"),
        # --- Oilfield services ---
        "SLB": ("SLB (Schlumberger)", "oilfield_services", "US", "AN8068571086"),
        "BKR": ("Baker Hughes", "oilfield_services", "US", "US05722G1004"),
        "HAL": ("Halliburton", "oilfield_services", "US", "US4062161017"),
        # --- Utilities / Power generation ---
        "DUK": ("Duke Energy", "electric_utilities", "US", "US26441C2044"),
        "SO": ("Southern Company", "electric_utilities", "US", "US8425871071"),
        "NEE": ("NextEra Energy", "electric_utilities", "US", "US65339F1012"),
        "AEP": ("American Electric Power", "electric_utilities", "US", "US0255371017"),
        "D": ("Dominion Energy", "electric_utilities", "US", "US25746U1097"),
        "XEL": ("Xcel Energy", "electric_utilities", "US", "US98389B1008"),
        "WEC": ("WEC Energy Group", "electric_utilities", "US", "US92939U1060"),
        "EIX": ("Edison International", "electric_utilities", "US", "US2810201077"),
        "ETR": ("Entergy", "electric_utilities", "US", "US29364G1031"),
        "AES": ("AES Corporation", "electric_utilities", "US", "US00130H1059"),
        "EVRG": ("Evergy", "electric_utilities", "US", "US30034W1062"),
        "NRG": ("NRG Energy", "power_generation", "US", "US6293775085"),
        "VST": ("Vistra Corp", "power_generation", "US", "US92840M1027"),
        # --- Materials: Cement & Steel ---
        "VMC": ("Vulcan Materials", "construction_materials", "US", "US9291601097"),
        "MLM": ("Martin Marietta Materials", "construction_materials", "US", "US5732841060"),
        "NUE": ("Nucor Corporation", "steel", "US", "US6703461052"),
        "STLD": ("Steel Dynamics", "steel", "US", "US8581191009"),
        "CLF": ("Cleveland-Cliffs", "steel", "US", "US1858991011"),
        "X": ("United States Steel", "steel", "US", "US9129091081"),
        # --- Chemicals ---
        "DOW": ("Dow Inc.", "chemicals", "US", "US2605571031"),
        "LYB": ("LyondellBasell", "chemicals", "US", "NL0009434992"),
        "CE": ("Celanese Corporation", "chemicals", "US", "US1508701034"),
        "CF": ("CF Industries", "chemicals_fertilizer", "US", "US1252691001"),
        "MOS": ("Mosaic Company", "chemicals_fertilizer", "US", "US61945C1036"),
        # --- Mining ---
        "FCX": ("Freeport-McMoRan", "mining_copper", "US", "US35671D8570"),
        "NEM": ("Newmont Corporation", "mining_gold", "US", "US6516391066"),
        "AA": ("Alcoa Corporation", "mining_aluminum", "US", "US0138721065"),
        # --- Airlines (large scope 1 emitters) ---
        "DAL": ("Delta Air Lines", "airlines", "US", "US2473617023"),
        "UAL": ("United Airlines Holdings", "airlines", "US", "US9100471096"),
        "AAL": ("American Airlines Group", "airlines", "US", "US02376R1023"),
    }

    SUBSECTOR_TO_SECTOR = {
        "oil_gas_integrated": "energy",
        "oil_gas_exploration": "energy",
        "oil_gas_refining": "energy",
        "oilfield_services": "energy",
        "electric_utilities": "utilities",
        "power_generation": "utilities",
        "construction_materials": "materials",
        "steel": "materials",
        "chemicals": "materials",
        "chemicals_fertilizer": "materials",
        "mining_copper": "mining",
        "mining_gold": "mining",
        "mining_aluminum": "mining",
        "airlines": "transportation",
    }

    session = _get_sync_session()
    count = 0
    for ticker, (name, subsector, country, isin) in ENERGY_COMPANIES.items():
        existing = session.query(Company).filter(Company.ticker == ticker).first()
        if existing:
            continue
        sector = SUBSECTOR_TO_SECTOR.get(subsector, "energy")
        session.add(Company(
            id=uuid.uuid4(), name=name, ticker=ticker, sector=sector,
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


@app.command()
def coverage(
    full: bool = typer.Option(False, "--full", help="Show all companies"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
    no_save: bool = typer.Option(False, "--no-save", help="Don't persist snapshot"),
):
    """Compute and display data coverage report."""
    session = _get_sync_session()
    try:
        snapshot = create_snapshot(session, trigger="manual", save=not no_save)
        if json_output:
            import json
            data = {
                "computed_at": snapshot.computed_at.isoformat(),
                "trigger": snapshot.trigger,
                "summary": {
                    "total_companies": snapshot.total_companies,
                    "total_emissions": snapshot.total_emissions,
                    "total_filings": snapshot.total_filings,
                    "total_cross_validations": snapshot.total_cross_validations,
                    "year_range": {"min": snapshot.year_min, "max": snapshot.year_max},
                    "cv_coverage_pct": float(snapshot.cv_coverage_pct),
                    "sources_active": sum(1 for v in snapshot.by_source_year.values() if v),
                    "sources_total": len(snapshot.by_source_year),
                },
                "by_source_year": snapshot.by_source_year,
                "by_company_source": snapshot.by_company_source,
                "by_company_year": snapshot.by_company_year,
                "cv_by_flag": snapshot.cv_by_flag,
                "alerts": snapshot.alerts,
            }
            typer.echo(json.dumps(data, indent=2))
        else:
            data = {
                "computed_at": snapshot.computed_at,
                "total_companies": snapshot.total_companies,
                "total_emissions": snapshot.total_emissions,
                "total_filings": snapshot.total_filings,
                "total_cross_validations": snapshot.total_cross_validations,
                "year_min": snapshot.year_min,
                "year_max": snapshot.year_max,
                "by_source_year": snapshot.by_source_year,
                "by_company_source": snapshot.by_company_source,
                "by_company_year": snapshot.by_company_year,
                "cv_by_flag": snapshot.cv_by_flag,
                "cv_coverage_pct": float(snapshot.cv_coverage_pct),
                "alerts": snapshot.alerts,
            }
            typer.echo(format_report(data, full=full))
    finally:
        session.close()


if __name__ == "__main__":
    app()
