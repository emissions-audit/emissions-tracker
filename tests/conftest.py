import uuid

import pytest
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.shared.models import Base, Company, Filing, Emission, CrossValidation, SourceEntry, Pledge
from src.api.main import create_app


class _SyncAsyncSession:
    """
    Thin adapter that exposes a synchronous SQLAlchemy Session through the
    AsyncSession method surface used by the routes.

    Routes are ``async def`` and ``await session.execute(...)``, which cannot
    accept a sync ``Session`` directly. An in-memory aiosqlite engine would
    hit event-loop mismatches with ``TestClient`` (which spins up its own
    anyio loop per request), so this adapter stays with the sync engine and
    wraps every async method to delegate synchronously.
    """

    def __init__(self, sync_session):
        self._session = sync_session

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def scalar(self, *args, **kwargs):
        return self._session.scalar(*args, **kwargs)

    async def scalars(self, *args, **kwargs):
        return self._session.scalars(*args, **kwargs)

    async def commit(self):
        return self._session.commit()

    async def rollback(self):
        return self._session.rollback()

    async def close(self):
        return self._session.close()

    async def refresh(self, instance, *args, **kwargs):
        return self._session.refresh(instance, *args, **kwargs)

    async def flush(self, *args, **kwargs):
        return self._session.flush(*args, **kwargs)

    async def get(self, *args, **kwargs):
        return self._session.get(*args, **kwargs)

    async def delete(self, instance):
        return self._session.delete(instance)

    async def merge(self, instance, *args, **kwargs):
        return self._session.merge(instance, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._session, name)


@pytest.fixture
def db_session():
    # StaticPool + check_same_thread=False allows the in-memory DB to be shared
    # across threads — necessary because FastAPI's TestClient runs handlers in
    # a worker thread different from the pytest fixture thread.
    engine = create_sync_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield _SyncAsyncSession(session)
    session.close()
    engine.dispose()


@pytest.fixture
def seeded_session(db_session):
    """DB with sample companies, filings, and emissions."""
    shell_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    exxon_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    filing1_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
    filing2_id = uuid.UUID("00000000-0000-0000-0000-000000000011")

    db_session.add_all([
        Company(id=shell_id, name="Shell plc", ticker="SHEL", sector="energy",
                subsector="oil_gas_integrated", country="GB"),
        Company(id=exxon_id, name="ExxonMobil", ticker="XOM", sector="energy",
                subsector="oil_gas_integrated", country="US"),
        Filing(id=filing1_id, company_id=shell_id, year=2023,
               filing_type="10k_xbrl", parser_used="xbrl", raw_hash="abc"),
        Filing(id=filing2_id, company_id=exxon_id, year=2023,
               filing_type="10k_xbrl", parser_used="xbrl", raw_hash="def"),
        Emission(id=uuid.uuid4(), company_id=shell_id, year=2023, scope="1",
                 value_mt_co2e=68_000_000, source_id=filing1_id),
        Emission(id=uuid.uuid4(), company_id=shell_id, year=2023, scope="2",
                 value_mt_co2e=10_000_000, source_id=filing1_id),
        Emission(id=uuid.uuid4(), company_id=shell_id, year=2022, scope="1",
                 value_mt_co2e=72_000_000, source_id=filing1_id),
        Emission(id=uuid.uuid4(), company_id=exxon_id, year=2023, scope="1",
                 value_mt_co2e=112_000_000, source_id=filing2_id),
    ])
    db_session._session.commit()

    # Cross-validation fixtures (Task 12)
    cv_id = uuid.UUID("00000000-0000-0000-0000-000000000020")
    db_session.add_all([
        CrossValidation(id=cv_id, company_id=shell_id, year=2023, scope="1",
                        source_count=2, min_value=65_000_000, max_value=72_000_000,
                        spread_pct=10.77, flag="yellow"),
        SourceEntry(id=uuid.uuid4(), cross_validation_id=cv_id,
                    source_type="regulatory", value_mt_co2e=65_000_000, filing_id=filing1_id),
        SourceEntry(id=uuid.uuid4(), cross_validation_id=cv_id,
                    source_type="satellite", value_mt_co2e=72_000_000),
    ])
    db_session._session.commit()

    # Pledge fixtures (Task 13)
    db_session.add_all([
        Pledge(id=uuid.uuid4(), company_id=shell_id, pledge_type="net_zero",
               target_year=2050, target_scope="1+2+3", target_reduction_pct=100.0,
               baseline_year=2016, baseline_value_mt_co2e=1_700_000_000,
               source_id=filing1_id),
    ])
    db_session._session.commit()

    return db_session


@pytest.fixture
def client(seeded_session):
    app = create_app(db_session_override=seeded_session)
    return TestClient(app)
