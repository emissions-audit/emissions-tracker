from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Company:
    id: str
    name: str
    sector: str
    ticker: str | None = None
    subsector: str | None = None
    country: str | None = None
    isin: str | None = None
    website: str | None = None


@dataclass
class Emission:
    id: str
    company_id: str
    year: int
    scope: str
    value_mt_co2e: float
    methodology: str | None = None
    verified: bool | None = None
    source_id: str | None = None


@dataclass
class Filing:
    id: str
    company_id: str
    year: int
    filing_type: str
    parser_used: str
    source_url: str | None = None
    fetched_at: str | None = None
    raw_hash: str | None = None


@dataclass
class Pledge:
    id: str
    company_id: str
    pledge_type: str
    target_year: int | None = None
    target_scope: str | None = None
    target_reduction_pct: float | None = None
    baseline_year: int | None = None
    baseline_value_mt_co2e: float | None = None
    source_id: str | None = None


@dataclass
class SourceDetail:
    source_type: str
    value_mt_co2e: float
    filing_url: str | None = None


@dataclass
class Discrepancy:
    company_id: str
    company_name: str
    year: int
    scope: str
    spread_pct: float
    flag: str
    source_count: int
    min_value: float
    max_value: float
    ticker: str | None = None
    delta_mt_co2e: float = 0
    sources: list[SourceDetail] = field(default_factory=list)


@dataclass
class SourceEntry:
    source_type: str
    value_mt_co2e: float
    filing_id: str | None = None
    filing_url: str | None = None


@dataclass
class CrossValidation:
    id: str
    company_id: str
    year: int
    scope: str
    source_count: int
    min_value: float
    max_value: float
    spread_pct: float
    flag: str
    entries: list[SourceEntry] = field(default_factory=list)


@dataclass
class Stats:
    company_count: int
    filing_count: int
    emission_count: int
    year_range: dict[str, int]
    last_updated: str


@dataclass
class PaginatedResponse:
    items: list[Any]
    total: int
    limit: int
    offset: int
