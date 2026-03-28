import uuid

import pytest
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.shared.models import Base, Company, Filing, Emission
from src.api.main import create_app


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
    yield session
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
    db_session.commit()
    return db_session


@pytest.fixture
def client(seeded_session):
    app = create_app(db_session_override=seeded_session)
    return TestClient(app)
