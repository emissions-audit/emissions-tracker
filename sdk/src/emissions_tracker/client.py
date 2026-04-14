from __future__ import annotations

from typing import Any

import httpx

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

DEFAULT_BASE_URL = "https://emissions-tracker-production.up.railway.app"


class EmissionsTrackerError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class EmissionsTracker:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = 30.0,
    ):
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise EmissionsTrackerError(resp.status_code, detail)
        return resp.json()

    def _get(self, path: str, **params) -> Any:
        cleaned = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", path, params=cleaned)

    # --- Companies ---

    def list_companies(
        self,
        *,
        sector: str | None = None,
        country: str | None = None,
        subsector: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = self._get(
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

    def get_company(self, company_id: str) -> Company:
        return Company(**self._get(f"/v1/companies/{company_id}"))

    # --- Emissions ---

    def list_emissions(
        self,
        *,
        year: int | None = None,
        scope: str | None = None,
        sector: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = self._get(
            "/v1/emissions",
            year=year, scope=scope, sector=sector, limit=limit, offset=offset,
        )
        return PaginatedResponse(
            items=[Emission(**e) for e in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    def get_company_emissions(
        self,
        company_id: str,
        *,
        year: int | None = None,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = self._get(
            f"/v1/companies/{company_id}/emissions",
            year=year, scope=scope, limit=limit, offset=offset,
        )
        return PaginatedResponse(
            items=[Emission(**e) for e in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )

    def compare_emissions(
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
        return self._get("/v1/emissions/compare", **params)

    # --- Filings ---

    def get_company_filings(
        self,
        company_id: str,
        *,
        year: int | None = None,
        filing_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PaginatedResponse:
        data = self._get(
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

    def get_company_pledges(self, company_id: str) -> list[Pledge]:
        data = self._get(f"/v1/companies/{company_id}/pledges")
        return [Pledge(**p) for p in data]

    def get_pledge_tracker(self) -> list[dict]:
        return self._get("/v1/pledges/tracker")

    # --- Discrepancies ---

    def list_discrepancies(
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
        data = self._get(
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

    def top_discrepancies(self) -> list[Discrepancy]:
        data = self._get("/v1/discrepancies/top")
        results = []
        for d in data:
            sources = [SourceDetail(**s) for s in d.pop("sources", [])]
            results.append(Discrepancy(**d, sources=sources))
        return results

    # --- Validation ---

    def get_company_validation(
        self, company_id: str, *, limit: int = 50, offset: int = 0
    ) -> PaginatedResponse:
        data = self._get(
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

    def get_coverage(self, *, view: str | None = None, alerts_only: bool = False) -> dict:
        return self._get("/v1/coverage", view=view, alerts_only=alerts_only or None)

    def get_coverage_health(self) -> dict:
        return self._get("/v1/coverage/health")

    # --- Meta ---

    def get_stats(self) -> Stats:
        return Stats(**self._get("/v1/stats"))

    def get_sectors(self) -> dict:
        return self._get("/v1/meta/sectors")

    def get_methodology(self) -> dict:
        return self._get("/v1/meta/methodology")
