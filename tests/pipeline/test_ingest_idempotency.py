"""Idempotency test for _upsert_emissions (ET-66).

Running the same ingest twice must produce the same row counts — no new
filings, no new emissions. Values should still reflect the latest input.
"""
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.pipeline.cli import _upsert_emissions
from src.pipeline.sources.base import RawEmission
from src.shared.models import Base, Company, Emission, Filing


@pytest.fixture
def sync_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(Company(
        id=uuid.uuid4(), name="Shell plc", ticker="SHEL",
        sector="energy", subsector="oil_gas_integrated", country="GB",
    ))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _sample_records() -> list[RawEmission]:
    return [
        RawEmission(
            company_ticker="SHEL",
            year=2023,
            scope="Scope 1",
            value=68_000_000,
            unit="t_co2e",
            methodology="eu_ets_verified",
            verified=True,
            source_url="https://example.com/eu-ets",
            filing_type="eu_ets",
            parser_used="excel",
        ),
        RawEmission(
            company_ticker="SHEL",
            year=2023,
            scope="Scope 2",
            value=10_000_000,
            unit="t_co2e",
            methodology="eu_ets_verified",
            verified=True,
            source_url="https://example.com/eu-ets",
            filing_type="eu_ets",
            parser_used="excel",
        ),
    ]


def test_upsert_is_idempotent(sync_session):
    records = _sample_records()

    first = _upsert_emissions(sync_session, records)
    filings_after_first = sync_session.scalar(select(func.count()).select_from(Filing))
    emissions_after_first = sync_session.scalar(select(func.count()).select_from(Emission))

    second = _upsert_emissions(sync_session, records)
    filings_after_second = sync_session.scalar(select(func.count()).select_from(Filing))
    emissions_after_second = sync_session.scalar(select(func.count()).select_from(Emission))

    assert first == 2
    assert second == 2
    assert filings_after_first == filings_after_second == 1
    assert emissions_after_first == emissions_after_second == 2


def test_upsert_updates_values_on_rerun(sync_session):
    records = _sample_records()
    _upsert_emissions(sync_session, records)

    updated = [
        RawEmission(
            company_ticker=r.company_ticker,
            year=r.year,
            scope=r.scope,
            value=r.value + 1_000_000,
            unit=r.unit,
            methodology=r.methodology,
            verified=r.verified,
            source_url=r.source_url,
            filing_type=r.filing_type,
            parser_used=r.parser_used,
        )
        for r in records
    ]
    _upsert_emissions(sync_session, updated)

    emissions = sync_session.query(Emission).order_by(Emission.scope).all()
    assert len(emissions) == 2
    assert float(emissions[0].value_t_co2e) == 69_000_000
    assert float(emissions[1].value_t_co2e) == 11_000_000
