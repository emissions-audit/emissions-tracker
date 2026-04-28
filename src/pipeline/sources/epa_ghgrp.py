"""EPA Greenhouse Gas Reporting Program (GHGRP) data source.

Fetches facility-level mandatory emissions reports from the EPA
Envirofacts API. Each API row represents a single greenhouse gas at
a single facility for a given year. Rows are aggregated into a single
CO2-equivalent total per facility+year (in tonnes CO2e — t_co2e), then
mapped to stock tickers via the shared company_mapping module.

PARTIAL COVERAGE NOTE: EPA GHGRP covers only US facilities reporting
above the 25,000 metric tons CO2e threshold. For multinational companies
(e.g. SHEL, BP, TTE), this source reports only US-domestic Scope 1.
CV engine semantics for partial sources tracked in ET-85.
"""

from collections import defaultdict

import httpx

from src.pipeline.company_mapping import resolve_ticker
from src.pipeline.sources.base import BaseSource, RawEmission

EPA_GHGRP_API = "https://data.epa.gov/efservice/GHG_EMITTER_SECTOR"
PAGE_SIZE = 1000


def _resolve_facility_ticker(facility_name: str) -> str | None:
    """Try to resolve a facility name to a ticker.

    EPA GHGRP facility names often include location and type suffixes
    (e.g. "ExxonMobil Baytown Refinery").  We first try the full name,
    then progressively shorter word-prefixes until a match is found.
    """
    # 1. Try full name
    ticker = resolve_ticker(facility_name)
    if ticker is not None:
        return ticker

    # 2. Try progressively shorter prefixes (drop trailing words)
    words = facility_name.split()
    for length in range(len(words) - 1, 0, -1):
        prefix = " ".join(words[:length])
        ticker = resolve_ticker(prefix)
        if ticker is not None:
            return ticker

    return None


def parse_ghgrp_response(
    records: list[dict], years: list[int]
) -> list[RawEmission]:
    """Parse raw EPA GHGRP API rows into aggregated RawEmission records.

    Multiple gas rows for the same facility+year are summed into a single
    CO2-equivalent total.  Facility names are resolved to stock tickers via
    ``resolve_ticker``; unknown facilities fall back to using the facility
    name as the company_ticker.
    """
    # Aggregate: (facility_id, year) → {total, facility_name}
    aggregated: dict[tuple[str, int], dict] = defaultdict(
        lambda: {"total": 0.0, "facility_name": ""}
    )

    for row in records:
        year = row.get("year")
        if year not in years:
            continue

        fid = row.get("facility_id", "")
        key = (str(fid), year)
        aggregated[key]["total"] += row.get("co2e_emission", 0.0)
        aggregated[key]["facility_name"] = row.get("facility_name", "")

    results: list[RawEmission] = []
    for (_fid, year), info in sorted(aggregated.items()):
        facility_name = info["facility_name"]
        ticker = _resolve_facility_ticker(facility_name) or facility_name

        results.append(
            RawEmission(
                company_ticker=ticker,
                year=year,
                scope="Scope 1",
                value=info["total"],
                unit="t_co2e",
                methodology="epa_mandatory",
                verified=None,
                source_url=EPA_GHGRP_API,
                filing_type="epa_ghgrp",
                parser_used="api",
            )
        )

    return results


class EpaGhgrpSource(BaseSource):
    name = "epa_ghgrp"

    async def fetch_emissions(
        self, tickers: list[str], years: list[int]
    ) -> list[RawEmission]:
        all_records: list[dict] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            for year in years:
                start = 0
                while True:
                    end = start + PAGE_SIZE - 1
                    url = f"{EPA_GHGRP_API}/YEAR/{year}/rows/{start}:{end}/JSON"
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        page = resp.json()
                    except httpx.HTTPError:
                        break

                    if not page:
                        break

                    all_records.extend(page)

                    if len(page) < PAGE_SIZE:
                        break
                    start += PAGE_SIZE

        results = parse_ghgrp_response(all_records, years)

        if tickers:
            ticker_set = {t.upper() for t in tickers}
            results = [r for r in results if r.company_ticker.upper() in ticker_set]

        return results
