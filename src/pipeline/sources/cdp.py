import httpx

from src.pipeline.sources.base import BaseSource, RawEmission, RawPledge

CDP_SCOPE_FIELDS = {
    "scope_1_mt_co2e": "Scope 1",
    "scope_2_mt_co2e": "Scope 2",
    "scope_3_mt_co2e": "Scope 3",
}


def parse_cdp_response(data: list[dict], years: list[int]) -> list[RawEmission]:
    results = []
    for row in data:
        if row.get("year") not in years:
            continue
        ticker = row.get("ticker", "")
        verified = "verified" in (row.get("verification_status", "") or "").lower()
        verified = verified and "not verified" not in (row.get("verification_status", "") or "").lower()

        for field, scope_label in CDP_SCOPE_FIELDS.items():
            value = row.get(field)
            if value is None:
                continue
            results.append(
                RawEmission(
                    company_ticker=ticker,
                    year=row["year"],
                    scope=scope_label,
                    value=value,
                    unit="mt_co2e",
                    methodology="ghg_protocol",
                    verified=verified,
                    source_url="https://www.cdp.net",
                    filing_type="cdp_response",
                    parser_used="api",
                )
            )
    return results


class CdpSource(BaseSource):
    name = "cdp"

    def __init__(self, data_path: str | None = None):
        self.data_path = data_path

    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        if not self.data_path:
            return []

        import json
        from pathlib import Path

        path = Path(self.data_path)
        if not path.exists():
            return []

        data = json.loads(path.read_text())
        results = parse_cdp_response(data, years)

        if tickers:
            ticker_set = {t.upper() for t in tickers}
            results = [r for r in results if r.company_ticker.upper() in ticker_set]

        return results
