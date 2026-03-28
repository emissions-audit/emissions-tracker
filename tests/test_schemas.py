import uuid
from datetime import datetime

from src.shared.schemas import (
    CompanyResponse,
    EmissionResponse,
    FilingResponse,
    PledgeResponse,
    CrossValidationResponse,
    DiscrepancyResponse,
    PaginatedResponse,
    StatsResponse,
)


def test_company_response():
    data = CompanyResponse(
        id=uuid.uuid4(), name="Shell plc", ticker="SHEL", sector="energy",
        subsector="oil_gas_integrated", country="GB", isin="GB00BP6MXD84",
        website="https://www.shell.com",
    )
    assert data.name == "Shell plc"


def test_emission_response():
    data = EmissionResponse(
        id=uuid.uuid4(), company_id=uuid.uuid4(), year=2023, scope="1",
        value_mt_co2e=120_000_000.0, methodology="ghg_protocol", verified=True,
        source_id=uuid.uuid4(),
    )
    assert data.scope == "1"


def test_paginated_response():
    data = PaginatedResponse(
        items=[{"name": "test"}], total=100, limit=50, offset=0,
    )
    assert data.total == 100
    assert len(data.items) == 1


def test_stats_response():
    data = StatsResponse(
        company_count=25, filing_count=150, emission_count=400,
        year_range={"min": 2021, "max": 2024}, last_updated=datetime.utcnow(),
    )
    assert data.company_count == 25
