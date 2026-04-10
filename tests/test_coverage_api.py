import uuid
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.shared.models import Base, CoverageSnapshot
from src.api.main import create_app


@pytest.fixture
async def app_with_snapshot():
    """Create app with in-memory async SQLite DB and a coverage snapshot."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Insert a snapshot
    async with factory() as session:
        snapshot = CoverageSnapshot(
            id=uuid.uuid4(),
            computed_at=datetime(2026, 4, 10, 14, 30),
            trigger="manual",
            source_filter=None,
            total_companies=20,
            total_emissions=233,
            total_filings=15,
            total_cross_validations=24,
            year_min=2022,
            year_max=2023,
            by_source_year={"epa_ghgrp": {"2022": 112, "2023": 121}, "climate_trace": {}, "eu_ets": {}},
            by_company_source={"XOM": {"epa_ghgrp": 8, "climate_trace": 0}},
            by_company_year={"XOM": {"2022": 4, "2023": 4}},
            cv_by_flag={"green": 1, "yellow": 0, "red": 23},
            cv_coverage_pct=4.2,
            alerts=[{"type": "staleness", "severity": "warning", "message": "eu_ets has never produced data", "detail": {"source": "eu_ets"}}],
        )
        session.add(snapshot)
        await session.commit()

    # Build app — use a fresh session for each request
    async with factory() as test_session:
        app = create_app(db_session_override=test_session)
        yield app

    await engine.dispose()


@pytest.mark.asyncio
async def test_coverage_returns_latest_snapshot(app_with_snapshot):
    async with AsyncClient(transport=ASGITransport(app=app_with_snapshot), base_url="http://test") as client:
        resp = await client.get("/v1/coverage")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "by_source_year" in data
    assert "alerts" in data
    assert data["summary"]["total_companies"] == 20
    assert data["summary"]["sources_active"] == 1
    assert data["summary"]["sources_total"] == 3


@pytest.mark.asyncio
async def test_coverage_view_filter(app_with_snapshot):
    async with AsyncClient(transport=ASGITransport(app=app_with_snapshot), base_url="http://test") as client:
        resp = await client.get("/v1/coverage?view=source_year")
    assert resp.status_code == 200
    data = resp.json()
    assert data["by_source_year"] is not None
    assert data["by_company_source"] is None
    assert data["by_company_year"] is None


@pytest.mark.asyncio
async def test_coverage_health(app_with_snapshot):
    async with AsyncClient(transport=ASGITransport(app=app_with_snapshot), base_url="http://test") as client:
        resp = await client.get("/v1/coverage/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "warning"
    assert data["alerts_warning"] == 1


@pytest.mark.asyncio
async def test_coverage_history(app_with_snapshot):
    async with AsyncClient(transport=ASGITransport(app=app_with_snapshot), base_url="http://test") as client:
        resp = await client.get("/v1/coverage/history?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "snapshots" in data
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["total_emissions"] == 233
