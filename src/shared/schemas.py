import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    ticker: str | None = None
    sector: str
    subsector: str | None = None
    country: str | None = None
    isin: str | None = None
    website: str | None = None

    model_config = {"from_attributes": True}


class EmissionResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    year: int
    scope: str
    value_mt_co2e: float
    methodology: str | None = None
    verified: bool | None = None
    source_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class FilingResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    year: int
    filing_type: str
    source_url: str | None = None
    fetched_at: datetime
    parser_used: str
    raw_hash: str | None = None

    model_config = {"from_attributes": True}


class PledgeResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    pledge_type: str
    target_year: int | None = None
    target_scope: str | None = None
    target_reduction_pct: float | None = None
    baseline_year: int | None = None
    baseline_value_mt_co2e: float | None = None
    source_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class SourceEntryResponse(BaseModel):
    source_type: str
    value_mt_co2e: float
    filing_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class CrossValidationResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    year: int
    scope: str
    source_count: int
    min_value: float
    max_value: float
    spread_pct: float
    flag: str
    entries: list[SourceEntryResponse] = []

    model_config = {"from_attributes": True}


class DiscrepancyResponse(BaseModel):
    company_id: uuid.UUID
    company_name: str
    year: int
    scope: str
    spread_pct: float
    flag: str
    source_count: int
    min_value: float
    max_value: float

    model_config = {"from_attributes": True}


class CompareRow(BaseModel):
    company_id: uuid.UUID
    company_name: str
    year: int
    scope: str
    value_mt_co2e: float


class PledgeTrackerRow(BaseModel):
    company_id: uuid.UUID
    company_name: str
    pledge_type: str
    target_year: int | None
    target_reduction_pct: float | None
    baseline_value: float | None
    latest_value: float | None
    actual_reduction_pct: float | None
    on_track: bool | None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class StatsResponse(BaseModel):
    company_count: int
    filing_count: int
    emission_count: int
    year_range: dict[str, int]
    last_updated: datetime
