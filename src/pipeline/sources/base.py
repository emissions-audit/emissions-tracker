from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RawEmission:
    company_ticker: str
    year: int
    scope: str
    value: float
    unit: str
    methodology: str | None = None
    verified: bool | None = None
    source_url: str | None = None
    filing_type: str = ""
    parser_used: str = ""


@dataclass
class RawPledge:
    company_ticker: str
    pledge_type: str
    target_year: int | None = None
    target_scope: str | None = None
    target_reduction_pct: float | None = None
    baseline_year: int | None = None
    baseline_value: float | None = None
    source_url: str | None = None


class BaseSource(ABC):
    name: str

    @abstractmethod
    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        ...

    async def fetch_pledges(self, tickers: list[str]) -> list[RawPledge]:
        return []
