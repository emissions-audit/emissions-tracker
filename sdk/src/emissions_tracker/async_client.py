from __future__ import annotations

from typing import Any

import httpx

from emissions_tracker.client import DEFAULT_BASE_URL, EmissionsTrackerError
from emissions_tracker.models import (
    Company,
    Emission,
    Filing,
    Pledge,
    Discrepancy,
    CrossValidation,
    SourceDetail,
    SourceEntry,
    Stats,
    PaginatedResponse,
)


class AsyncEmissionsTracker:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise EmissionsTrackerError(resp.status_code, detail)
        return resp.json()

    async def _get(self, path: str, **params) -> Any:
        cleaned = {k: v for k, v in params.items() if v is not None}
        return await self._request("GET", path, params=cleaned)

    # --- Companies ---

    async def list_companies(
        self,
        *,
        sector: str | None = None,
        country: str | None = None,
        subsector: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = await self._get(
            "/v1/companies",
            sector=sector, country=country, subsector=subsector,
            limit=limit, offset=offset,
        )
        return PaginatedResponse(
            items=[Company(**c) for c in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    async def get_company(self, company_id: str) -> Company:
        return Company(**await self._get(f"/v1/companies/{company_id}"))

    # --- Emissions ---

    async def list_emissions(
        self,
        *,
        year: int | None = None,
        scope: str | None = None,
        sector: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = await self._get(
            "/v1/emissions",
            year=year, scope=scope, sector=sector, limit=limit, offset=offset,
        )
        return PaginatedResponse(
            items=[Emission(**e) for e in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    async def get_company_emissions(
        self,
        company_id: str,
        *,
        year: int | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = await self._get(
            f"/v1/companies/{company_id}/emissions",
            year=year, scope=scope, limit=limit, offset=offset,
        )
        return PaginatedResponse(
            items=[Emission(**e) for e in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    async def compare_emissions(
        self,
        companies: list[str],
        *,
        scopes: list[str] | None = None,
        years: list[int] | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"companies": ",".join(companies)}
        if scopes:
            params["scopes"] = ",".join(scopes)
        if years:
            params["years"] = ",".join(str(y) for y in years)
        return await self._get("/v1/emissions/compare", **params)

    # --- Filings ---

    async def get_company_filings(
        self,
        company_id: str,
        *,
        year: int | None = None,
        filing_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = await self._get(
            f"/v1/companies/{company_id}/filings",
            year=year, filing_type=filing_type, limit=limit, offset=offset,
        )
        return PaginatedResponse(
            items=[Filing(**f) for f in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    # --- Pledges ---

    async def get_company_pledges(self, company_id: str) -> list[Pledge]:
        data = await self._get(f"/v1/companies/{company_id}/pledges")
        return [Pledge(**p) for p in data]

    async def get_pledge_tracker(self) -> list[dict]:
        return await self._get("/v1/pledges/tracker")

    # --- Discrepancies ---

    async def list_discrepancies(
        self,
        *,
        flag: str | None = None,
        year: int | None = None,
        sector: str | None = None,
        ticker: str | None = None,
        min_delta: float | None = None,
        sort: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = await self._get(
            "/v1/discrepancies",
            flag=flag, year=year, sector=sector, ticker=ticker,
            min_delta=min_delta, sort=sort, limit=limit, offset=offset,
        )
        items = []
        for d in data["items"]:
            sources = [SourceDetail(**s) for s in d.pop("sources", [])]
            items.append(Discrepancy(**d, sources=sources))
        return PaginatedResponse(
            items=items,
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    async def top_discrepancies(self) -> list[Discrepancy]:
        data = await self._get("/v1/discrepancies/top")
        results = []
        for d in data:
            sources = [SourceDetail(**s) for s in d.pop("sources", [])]
            results.append(Discrepancy(**d, sources=sources))
        return results

    # --- Validation ---

    async def get_company_validation(
        self, company_id: str, *, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse:
        data = await self._get(
            f"/v1/companies/{company_id}/validation",
            limit=limit, offset=offset,
        )
        items = []
        for cv in data["items"]:
            entries = [SourceEntry(**e) for e in cv.pop("entries", [])]
            items.append(CrossValidation(**cv, entries=entries))
        return PaginatedResponse(
            items=items,
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    # --- Coverage ---

    async def get_coverage(self, *, view: str | None = None, alerts_only: bool = False) -> dict:
        return await self._get("/v1/coverage", view=view, alerts_only=alerts_only or None)

    async def get_coverage_health(self) -> dict:
        return await self._get("/v1/coverage/health")

    # --- Meta ---

    async def get_stats(self) -> Stats:
        return Stats(**await self._get("/v1/stats"))

    async def get_sectors(self) -> dict:
        return await self._get("/v1/meta/sectors")

    async def get_methodology(self) -> dict:
        return await self._get("/v1/meta/methodology")
