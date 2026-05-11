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


class CorrectionEntry(BaseModel):
    field: str
    old_value: Any
    new_value: Any
    source_url: str
    contributor: str
    accepted_date: str


class ProvenanceResponse(BaseModel):
    contributors: list[str]
    corrections: list[CorrectionEntry]


class EmissionResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    year: int
    scope: str
    value_t_co2e: float
    methodology: str | None = None
    verified: bool | None = None
    source_id: uuid.UUID | None = None
    provenance: ProvenanceResponse | None = None

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
    baseline_value_t_co2e: float | None = None
    source_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class SourceEntryResponse(BaseModel):
    source_type: str
    value_t_co2e: float
    filing_id: uuid.UUID | None = None
    filing_url: str | None = None

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


class DiscrepancySourceDetail(BaseModel):
    source_type: str
    value_t_co2e: float
    filing_url: str | None = None


class DiscrepancyResponse(BaseModel):
    company_id: uuid.UUID
    company_name: str
    ticker: str | None = None
    year: int
    scope: str
    spread_pct: float
    delta_mt_co2e: float = 0
    flag: str
    source_count: int
    min_value: float
    max_value: float
    sources: list[DiscrepancySourceDetail] = []

    model_config = {"from_attributes": True}


class CompareRow(BaseModel):
    company_id: uuid.UUID
    company_name: str
    year: int
    scope: str
    value_t_co2e: float


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


class EndpointCount(BaseModel):
    endpoint: str
    calls: int


class AnalyticsSummaryResponse(BaseModel):
    period_days: int
    total_calls: int
    unique_api_keys: int
    avg_response_time_ms: float
    top_endpoints: list[EndpointCount]
    calls_by_tier: dict[str, int]


class CoverageAlertResponse(BaseModel):
    type: str
    severity: str
    message: str
    detail: dict[str, Any]


class CoverageSummary(BaseModel):
    total_companies: int
    total_emissions: int
    total_filings: int
    total_cross_validations: int
    year_range: dict[str, int | None]
    cv_coverage_pct: float
    sources_active: int
    sources_total: int


class CoverageResponse(BaseModel):
    computed_at: datetime
    trigger: str
    summary: CoverageSummary
    by_source_year: dict[str, dict[str, int]] | None = None
    by_company_source: dict[str, dict[str, int]] | None = None
    by_company_year: dict[str, dict[str, int]] | None = None
    cv_by_flag: dict[str, int]
    alerts: list[CoverageAlertResponse]


class CoverageHistoryEntry(BaseModel):
    computed_at: datetime
    total_emissions: int
    sources_active: int
    cv_coverage_pct: float
    cv_by_flag: dict[str, int]
    alert_count: int


class CoverageHistoryResponse(BaseModel):
    snapshots: list[CoverageHistoryEntry]


class CoverageHealthResponse(BaseModel):
    status: str
    computed_at: datetime | None
    alerts_critical: int
    alerts_warning: int
    alerts_info: int
    alerts: list[CoverageAlertResponse]


WEBHOOK_EVENTS = [
    "new_filing",
    "new_emission",
    "new_discrepancy",
    "coverage_update",
    "ingestion_complete",
]


class WebhookCreate(BaseModel):
    url: str
    events: list[str]

    model_config = {"json_schema_extra": {"examples": [{"url": "https://example.com/webhook", "events": ["new_discrepancy", "ingestion_complete"]}]}}


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookEventPayload(BaseModel):
    event: str
    timestamp: datetime
    data: dict[str, Any]
