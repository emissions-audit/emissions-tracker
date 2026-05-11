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
from src.pipeline.normalize import normalize_value, UNIT_MULTIPLIERS


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


# ---------------------------------------------------------------------------
# Phase 4 Task 4.2 Step 1: unit-tag conversion tests
# ---------------------------------------------------------------------------


def test_canonical_tag_returns_value_unchanged():
    assert normalize_value(1_000_000, "t_co2e") == 1_000_000
    assert normalize_value(1_000_000, "metric_tons_co2e") == 1_000_000


def test_dropped_tag_raises():
    for tag in ("mt_co2e", "kt_co2e", "kg_co2e", "g_co2e"):
        with pytest.raises(ValueError):
            normalize_value(1_000, tag)


def test_unit_multipliers_only_canonical():
    # YAGNI: keep the table minimal; expand only when a future source needs it.
    assert set(UNIT_MULTIPLIERS.keys()) == {"t_co2e", "metric_tons_co2e"}


# ---------------------------------------------------------------------------
# Phase 4 Task 4.2 Step 2: cross-source magnitude consistency tests
#
# These exercise the full adapter -> normalize -> _upsert_emissions chain.
# Re-enabled in Phase 5 once `cli._upsert_emissions`, the seed JSONs, and the
# CDP/CARB SCOPE_FIELDS dicts all use the canonical `value_t_co2e` /
# `scope_N_t_co2e` names.
# ---------------------------------------------------------------------------

import asyncio

from src.pipeline.cli import _upsert_emissions
from src.pipeline.sources.cdp import CdpSource


def test_cdp_xom_2023_seeds_at_tonne_magnitude(db_session):
    """XOM 2023 from CDP seed should land in DB at ~112M tonnes (real-world correct)."""
    sync_session = db_session._session
    sync_session.add(
        Company(
            id=uuid.uuid4(),
            name="ExxonMobil",
            ticker="XOM",
            sector="energy",
            subsector="oil_gas_integrated",
            country="US",
        )
    )
    sync_session.commit()

    source = CdpSource(data_path="data/cdp/sample-2023.json")
    raw = asyncio.run(source.fetch_emissions(["XOM"], [2023]))
    _upsert_emissions(sync_session, raw)

    xom = next(c for c in sync_session.query(Company).filter_by(ticker="XOM"))
    em = (
        sync_session.query(Emission)
        .filter_by(company_id=xom.id, year=2023, scope="1")
        .first()
    )
    assert em is not None
    # XOM 2023 Scope 1 is real-world ~110-115 Mt = 110_000_000 - 115_000_000 tonnes
    assert 100_000_000 <= em.value_t_co2e <= 150_000_000, (
        f"XOM CDP 2023 Scope 1 stored as {em.value_t_co2e:,.0f}t — expected 100M-150M"
    )


def test_carb_xom_2026_seeds_at_tonne_magnitude(db_session):
    """XOM 2026 from CARB SB253 seed should also land at ~112M tonnes."""
    from src.pipeline.sources.carb import CarbSource

    sync_session = db_session._session
    sync_session.add(
        Company(
            id=uuid.uuid4(),
            name="ExxonMobil",
            ticker="XOM",
            sector="energy",
            subsector="oil_gas_integrated",
            country="US",
        )
    )
    sync_session.commit()

    source = CarbSource(data_path="data/carb/sample-2026.json")
    raw = asyncio.run(source.fetch_emissions(["XOM"], [2026]))
    _upsert_emissions(sync_session, raw)

    xom = next(c for c in sync_session.query(Company).filter_by(ticker="XOM"))
    em = (
        sync_session.query(Emission)
        .filter_by(company_id=xom.id, year=2026, scope="1")
        .first()
    )
    assert em is not None
    assert 100_000_000 <= em.value_t_co2e <= 150_000_000, (
        f"XOM CARB 2026 Scope 1 stored as {em.value_t_co2e:,.0f}t — expected 100M-150M"
    )
