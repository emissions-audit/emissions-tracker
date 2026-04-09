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
    "EOG": "EOG Resources",
    "SLB": "Schlumberger",  # Climate TRACE uses "Schlumberger" not "SLB"
    "BKR": "Baker Hughes",
    "HAL": "Halliburton",
    "FANG": "Diamondback Energy",
}


def parse_asset_emissions(
    ticker: str, assets: list[dict], year: int
) -> RawEmission | None:
    """Sum co2e_100yr EmissionsSummary across all assets for a single year."""
    total = 0.0
    for asset in assets:
        for entry in asset.get("EmissionsSummary", []):
            if entry.get("Gas") == "co2e_100yr":
                total += entry.get("EmissionsQuantity", 0)

    if total <= 0:
        return None

    return RawEmission(
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


PAGE_LIMIT = 500


class ClimateTraceSource(BaseSource):
    name = "climate_trace"

    async def _fetch_all_assets(
        self, client: httpx.AsyncClient, owner: str, year: int
    ) -> list[dict]:
        """Paginate through all assets for an owner+year."""
        assets: list[dict] = []
        offset = 0
        while True:
            resp = await client.get(
                CLIMATE_TRACE_API,
                params={"owners": owner, "year": year, "limit": PAGE_LIMIT, "offset": offset},
            )
            resp.raise_for_status()
            page = resp.json().get("assets", [])
            assets.extend(page)
            if len(page) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
        return assets

    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        if not tickers:
            tickers = list(TICKER_TO_OWNER.keys())

        results = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for ticker in tickers:
                owner = TICKER_TO_OWNER.get(ticker.upper())
                if not owner:
                    continue
                for year in years:
                    try:
                        assets = await self._fetch_all_assets(client, owner, year)
                        emission = parse_asset_emissions(ticker, assets, year)
                        if emission:
                            results.append(emission)
                    except httpx.HTTPError:
                        continue
        return results
