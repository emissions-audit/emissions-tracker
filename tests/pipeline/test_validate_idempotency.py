"""Idempotency test for validate command's CV upsert (ET-67).

Running validate twice on the same data must produce the same CrossValidation
and SourceEntry row counts. Values should reflect the latest computation.
"""
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.pipeline.validate import compute_cross_validations
from src.shared.models import Base, Company, CrossValidation, Emission, Filing, SourceEntry


@pytest.fixture
def sync_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    company = Company(
        id=uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
        name="Shell plc", ticker="SHEL",
        sector="energy", subsector="oil_gas_integrated", country="GB",
    )
    session.add(company)

    filing_1 = Filing(
        id=uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        company_id=company.id, year=2023, filing_type="eu_ets",
        source_url="https://example.com/eu-ets", parser_used="excel",
        fetched_at=datetime.utcnow(),
    )
    filing_2 = Filing(
        id=uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"),
        company_id=company.id, year=2023, filing_type="climate_trace",
        source_url="https://example.com/ct", parser_used="json",
        fetched_at=datetime.utcnow(),
    )
    session.add_all([filing_1, filing_2])

    session.add_all([
        Emission(
            id=uuid.uuid4(), company_id=company.id, year=2023, scope="scope_1",
            value_mt_co2e=68_000_000, methodology="eu_ets_verified",
            verified=True, source_id=filing_1.id,
        ),
        Emission(
            id=uuid.uuid4(), company_id=company.id, year=2023, scope="scope_1",
            value_mt_co2e=72_000_000, methodology="satellite",
            verified=False, source_id=filing_2.id,
        ),
    ])
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _run_validate_upsert(session):
    """Simulate the validate command's upsert logic."""
    emissions = session.query(Emission).all()
    emission_dicts = [
        {"company_id": e.company_id, "year": e.year, "scope": e.scope,
         "value_mt_co2e": float(e.value_mt_co2e), "source_id": e.source_id}
        for e in emissions
    ]
    filings = {f.id: f.filing_type for f in session.query(Filing).all()}
    results = compute_cross_validations(emission_dicts, filings)

    for cv_data in results:
        existing_cv = (
            session.query(CrossValidation)
            .filter(
                CrossValidation.company_id == cv_data["company_id"],
                CrossValidation.year == cv_data["year"],
                CrossValidation.scope == cv_data["scope"],
            )
            .first()
        )
        if existing_cv is None:
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
            session.add(cv)
            session.flush()
        else:
            cv = existing_cv
            cv.source_count = cv_data["source_count"]
            cv.min_value = cv_data["min_value"]
            cv.max_value = cv_data["max_value"]
            cv.spread_pct = cv_data["spread_pct"]
            cv.flag = cv_data["flag"]
            cv.updated_at = datetime.utcnow()
            session.query(SourceEntry).filter(
                SourceEntry.cross_validation_id == cv.id
            ).delete()
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
    return len(results)


def test_validate_is_idempotent(sync_session):
    first = _run_validate_upsert(sync_session)
    cv_after_first = sync_session.scalar(select(func.count()).select_from(CrossValidation))
    entries_after_first = sync_session.scalar(select(func.count()).select_from(SourceEntry))

    second = _run_validate_upsert(sync_session)
    cv_after_second = sync_session.scalar(select(func.count()).select_from(CrossValidation))
    entries_after_second = sync_session.scalar(select(func.count()).select_from(SourceEntry))

    assert first == 1  # one CV for scope_1
    assert second == 1
    assert cv_after_first == cv_after_second == 1
    assert entries_after_first == entries_after_second == 2


def test_validate_updates_values_on_rerun(sync_session):
    _run_validate_upsert(sync_session)

    # Change an emission value — CV should update, not duplicate
    emission = sync_session.query(Emission).filter(
        Emission.methodology == "satellite"
    ).first()
    emission.value_mt_co2e = 80_000_000
    sync_session.commit()

    _run_validate_upsert(sync_session)

    cvs = sync_session.query(CrossValidation).all()
    assert len(cvs) == 1
    assert float(cvs[0].max_value) == 80_000_000
    assert float(cvs[0].min_value) == 68_000_000
