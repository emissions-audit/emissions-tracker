"""Climate TRACE asset-rollup data source.

API returns asset-level emissions in tonnes CO2e (t_co2e).
The aggregator sums owned assets per ticker via client-side filter on
Owners[].CompanyName (the v6 API's owners query-param does not reliably
filter — see _asset_owned_by below).

Known limitation: ASSET_LIMIT=500 may truncate global asset lists for
oil-and-gas majors with many holdings; owner filter may also miss
subsidiaries. Cross-source magnitude alignment with CDP is the success
criterion for ET-83; tightening accuracy is ET-84's scope.
"""

import httpx

from src.pipeline.sources.base import BaseSource, RawEmission

CLIMATE_TRACE_API = "https://api.climatetrace.org/v6/assets"

# Maps tickers to their exact Climate TRACE CompanyName values.
# These must match the Owners[].CompanyName field in the v6 API response.
# Companies not in Climate TRACE's oil-and-gas-production dataset are omitted.
TICKER_TO_OWNER = {
    # Oil & Gas: Integrated majors
    "XOM": "Exxon Mobil Corp",
    "CVX": "Chevron Corp",
    "SHEL": "Shell PLC",
    "BP": "BP PLC",
    "TTE": "TotalEnergies SE",
    "COP": "ConocoPhillips Corp",
    "ENI": "Eni SpA",
    "EQNR": "Equinor ASA",
    # Oil & Gas: E&P
    "OXY": "Occidental Petroleum Corp",
    "DVN": "Devon Energy Corp",
    "HES": "Hess Corp",
    "MRO": "Marathon Oil Corp",
    "EOG": "EOG Resources Inc",
    "FANG": "Diamondback Energy Inc",
    "PXD": "Pioneer Natural Resources Co",
    "CTRA": "Coterra Energy Inc",
    # Oil & Gas: Refining
    "MPC": "Marathon Petroleum Corp",
    "PSX": "Phillips 66",
    "VLO": "Valero Energy Corp",
    # Oilfield services
    "SLB": "Schlumberger Ltd",
    "BKR": "Baker Hughes Co",
    "HAL": "Halliburton Co",
    # Utilities / Power generation
    "DUK": "Duke Energy Corp",
    "SO": "Southern Co",
    "NEE": "NextEra Energy Inc",
    "AEP": "American Electric Power Co Inc",
    "D": "Dominion Energy Inc",
    "XEL": "Xcel Energy Inc",
    "WEC": "WEC Energy Group Inc",
    "EIX": "Edison International",
    "ETR": "Entergy Corp",
    "AES": "AES Corp",
    "EVRG": "Evergy Inc",
    "NRG": "NRG Energy Inc",
    "VST": "Vistra Corp",
    # Materials: Steel
    "NUE": "Nucor Corp",
    "CLF": "Cleveland-Cliffs Inc",
    "X": "United States Steel Corp",
    # Chemicals
    "DOW": "Dow Inc",
    "LYB": "LyondellBasell Industries NV",
    "CF": "CF Industries Holdings Inc",
    # Mining
    "FCX": "Freeport-McMoRan Inc",
    "AA": "Alcoa Corp",
    # Airlines
    "DAL": "Delta Air Lines Inc",
    "UAL": "United Airlines Holdings Inc",
    "AAL": "American Airlines Group Inc",
}


def _asset_owned_by(asset: dict, owner: str) -> bool:
    """Check if any of an asset's Owners match the target CompanyName."""
    for o in (asset.get("Owners") or []):
        if o.get("CompanyName") == owner:
            return True
    return False


def parse_asset_emissions(
    ticker: str, assets: list[dict], year: int, owner: str | None = None
) -> RawEmission | None:
    """Sum co2e_100yr EmissionsSummary across owned assets for a single year.

    If *owner* is given, only assets whose Owners[].CompanyName matches are
    included.  The v6 API's ``owners`` query-param does not reliably filter,
    so client-side filtering is required.
    """
    total = 0.0
    for asset in assets:
        if owner and not _asset_owned_by(asset, owner):
            continue
        for entry in (asset.get("EmissionsSummary") or []):
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


ASSET_LIMIT = 500


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
                for year in years:
                    try:
                        resp = await client.get(
                            CLIMATE_TRACE_API,
                            params={"owners": owner, "year": year, "limit": ASSET_LIMIT},
                        )
                        resp.raise_for_status()
                        assets = resp.json().get("assets", [])
                        emission = parse_asset_emissions(ticker, assets, year, owner=owner)
                        if emission:
                            results.append(emission)
                    except httpx.HTTPError:
                        continue
        return results
