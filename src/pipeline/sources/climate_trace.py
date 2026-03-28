from collections import defaultdict

import httpx

from src.pipeline.sources.base import BaseSource, RawEmission

CLIMATE_TRACE_API = "https://api.climatetrace.org/v6/assets"

TICKER_TO_OWNER = {
    "XOM": "ExxonMobil",
    "CVX": "Chevron",
    "COP": "ConocoPhillips",
    "SHEL": "Shell",
    "BP": "BP",
    "TTE": "TotalEnergies",
    "ENI": "Eni",
    "EQNR": "Equinor",
    "OXY": "Occidental",
    "MPC": "Marathon Petroleum",
    "PSX": "Phillips 66",
    "VLO": "Valero",
    "DVN": "Devon Energy",
    "HES": "Hess",
    "MRO": "Marathon Oil",
}


def parse_asset_emissions(
    ticker: str, assets: list[dict], years: list[int]
) -> list[RawEmission]:
    yearly_totals: dict[int, float] = defaultdict(float)

    for asset in assets:
        start = asset.get("start_time", "")
        year = int(start[:4]) if len(start) >= 4 else None
        if year not in years:
            continue
        if asset.get("gas") != "co2e_100yr":
            continue
        yearly_totals[year] += asset.get("emissions_quantity", 0)

    results = []
    for year, total in sorted(yearly_totals.items()):
        results.append(
            RawEmission(
                company_ticker=ticker,
                year=year,
                scope="Scope 1",
                value=total,
                unit="t_co2e",
                methodology="satellite_derived",
                verified=None,
                source_url=CLIMATE_TRACE_API,
                filing_type="climate_trace",
                parser_used="api",
            )
        )
    return results


class ClimateTraceSource(BaseSource):
    name = "climate_trace"

    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        if not tickers:
            tickers = list(TICKER_TO_OWNER.keys())

        results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for ticker in tickers:
                owner = TICKER_TO_OWNER.get(ticker.upper())
                if not owner:
                    continue
                try:
                    resp = await client.get(
                        CLIMATE_TRACE_API,
                        params={"owners": owner, "sector": "oil-and-gas"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    results.extend(parse_asset_emissions(ticker, data, years))
                except httpx.HTTPError:
                    continue
        return results
