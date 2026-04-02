import httpx

from src.pipeline.sources.base import BaseSource, RawEmission

CARB_API_URL = "https://ww2.arb.ca.gov/api/sb253/filings"

CARB_SCOPE_FIELDS = {
    "scope_1_mt_co2e": "Scope 1",
    "scope_2_mt_co2e": "Scope 2",
    "scope_3_mt_co2e": "Scope 3",
}

CARB_COMPANY_TO_TICKER = {
    "ExxonMobil Corporation": "XOM",
    "Chevron Corporation": "CVX",
    "ConocoPhillips": "COP",
    "Occidental Petroleum Corporation": "OXY",
    "Marathon Petroleum Corporation": "MPC",
    "Phillips 66": "PSX",
    "Valero Energy Corporation": "VLO",
    "Devon Energy Corporation": "DVN",
    "Hess Corporation": "HES",
    "Marathon Oil Corporation": "MRO",
    "EOG Resources Inc": "EOG",
    "SLB (Schlumberger)": "SLB",
    "Baker Hughes Company": "BKR",
    "Halliburton Company": "HAL",
    "Diamondback Energy Inc": "FANG",
    "Shell USA Inc": "SHEL",
    "BP America Inc": "BP",
    "TotalEnergies EP USA Inc": "TTE",
    "Equinor USA Operations LLC": "EQNR",
    "Eni US Operating Co Inc": "ENI",
}


def parse_carb_response(data: list[dict], years: list[int]) -> list[RawEmission]:
    results = []
    for row in data:
        if row.get("reporting_year") not in years:
            continue

        entity_name = row.get("entity_name", "")
        ticker = CARB_COMPANY_TO_TICKER.get(entity_name, entity_name)

        status = (row.get("verification_status", "") or "").lower()
        verified = "verified" in status and "unverified" not in status

        source_url = row.get("filing_url")

        for field, scope_label in CARB_SCOPE_FIELDS.items():
            value = row.get(field)
            if value is None:
                continue
            results.append(
                RawEmission(
                    company_ticker=ticker,
                    year=row["reporting_year"],
                    scope=scope_label,
                    value=value,
                    unit="mt_co2e",
                    methodology="ghg_protocol",
                    verified=verified,
                    source_url=source_url,
                    filing_type="carb_sb253",
                    parser_used="api",
                )
            )
    return results


class CarbSource(BaseSource):
    name = "carb"

    def __init__(self, data_path: str | None = None):
        self.data_path = data_path

    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        if self.data_path:
            results = self._fetch_from_file(years)
        else:
            results = await self._fetch_from_api(years)

        if tickers:
            ticker_set = {t.upper() for t in tickers}
            results = [r for r in results if r.company_ticker.upper() in ticker_set]

        return results

    def _fetch_from_file(self, years: list[int]) -> list[RawEmission]:
        import json
        from pathlib import Path

        path = Path(self.data_path)
        if not path.exists():
            return []

        data = json.loads(path.read_text())
        return parse_carb_response(data, years)

    async def _fetch_from_api(self, years: list[int]) -> list[RawEmission]:
        # CARB SB 253 API is not live yet — return empty for now
        return []
