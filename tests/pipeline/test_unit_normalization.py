"""TDD tests for the post-ingest sanity validator (Phase 3, ET-83).

These tests write directly through the underlying sync session
(`db_session._session`) because `check_sanity` performs synchronous
SQLAlchemy reads. The conftest fixture exposes `db_session` as a
`_SyncAsyncSession` adapter; the underlying sync `Session` is on
``_session``.
"""
import uuid

import pytest

from src.shared.models import Company, Emission, Filing
from src.pipeline.validators.sanity import check_sanity, SanityCheckFailed


def _seed_company_and_filing(sync_session):
    """Insert a single Company + Filing and return their ids."""
    company_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    sync_session.add(
        Company(
            id=company_id,
            name="Test Co",
            ticker="TEST",
            sector="energy",
            subsector="oil_gas_integrated",
            country="US",
        )
    )
    sync_session.add(
        Filing(
            id=filing_id,
            company_id=company_id,
            year=2023,
            filing_type="cdp_response",
            parser_used="api",
        )
    )
    sync_session.commit()
    return company_id, filing_id


def test_sanity_passes_real_magnitude(db_session):
    sync_session = db_session._session
    company_id, filing_id = _seed_company_and_filing(sync_session)

    sync_session.add(
        Emission(
            id=uuid.uuid4(),
            company_id=company_id,
            year=2023,
            scope="1",
            value_t_co2e=112_000_000,  # 112 Mt — XOM 2023 actual scale
            source_id=filing_id,
        )
    )
    sync_session.commit()

    # Should NOT raise
    check_sanity(sync_session)


def test_sanity_fails_on_planted_absurd_value(db_session):
    sync_session = db_session._session
    company_id, filing_id = _seed_company_and_filing(sync_session)

    sync_session.add(
        Emission(
            id=uuid.uuid4(),
            company_id=company_id,
            year=2023,
            scope="1",
            value_t_co2e=100_000_000_000,  # 100 Gt — impossible for one company-year
            source_id=filing_id,
        )
    )
    sync_session.commit()

    with pytest.raises(SanityCheckFailed):
        check_sanity(sync_session)
