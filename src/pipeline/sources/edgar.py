import httpx

from src.pipeline.sources.base import BaseSource, RawEmission

EDGAR_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
EDGAR_HEADERS = {"User-Agent": "EmissionsTracker research@emissionstracker.org"}

TICKER_TO_CIK = {
    "XOM": "0000034088",
    "CVX": "0000093410",
    "COP": "0001163165",
    "EOG": "0000821189",
    "SLB": "0000087347",
    "MPC": "0001510295",
    "PSX": "0001534701",
    "VLO": "0001035002",
    "OXY": "0000797468",
    "HES": "0000004447",
    "DVN": "0001090012",
    "BKR": "0001701605",
    "HAL": "0000045012",
    "FANG": "0001539838",
    "MRO": "0000101778",
}

GHG_CONCEPTS = {
    "GHGEmissionsScope1": "Scope 1",
    "GHGEmissionsScope2": "Scope 2",
    "GHGEmissionsScope3": "Scope 3",
    "GHGEmissionsDirectScope1": "Scope 1",
    "GHGEmissionsIndirectScope2": "Scope 2",
    "TotalGHGEmissions": "Total",
}


def parse_xbrl_filing(ticker: str, data: dict, years: list[int]) -> list[RawEmission]:
    results = []
    facts = data.get("facts", {})

    for namespace in facts.values():
        for concept_name, concept_data in namespace.items():
            scope_label = None
            for key, label in GHG_CONCEPTS.items():
                if key.lower() in concept_name.lower():
                    scope_label = label
                    break
            if scope_label is None:
                continue

            for unit_key, entries in concept_data.get("units", {}).items():
                for entry in entries:
                    fy = entry.get("fy")
                    if fy not in years:
                        continue
                    if entry.get("fp") != "FY":
                        continue

                    unit = (
                        "mt_co2e"
                        if "mt" in unit_key.lower() or "mega" in unit_key.lower()
                        else "t_co2e"
                    )

                    results.append(
                        RawEmission(
                            company_ticker=ticker,
                            year=fy,
                            scope=scope_label,
                            value=entry["val"],
                            unit=unit,
                            methodology="ghg_protocol",
                            verified=None,
                            source_url=EDGAR_COMPANY_FACTS_URL.format(
                                cik=TICKER_TO_CIK.get(ticker, "")
                            ),
                            filing_type="10k_xbrl",
                            parser_used="xbrl",
                        )
                    )
    return results


class EdgarSource(BaseSource):
    name = "edgar"

    async def fetch_emissions(self, tickers: list[str], years: list[int]) -> list[RawEmission]:
        if not tickers:
            tickers = list(TICKER_TO_CIK.keys())

        results = []
        async with httpx.AsyncClient(headers=EDGAR_HEADERS, timeout=30.0) as client:
            for ticker in tickers:
                cik = TICKER_TO_CIK.get(ticker.upper())
                if not cik:
                    continue
                url = EDGAR_COMPANY_FACTS_URL.format(cik=cik)
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
                    results.extend(parse_xbrl_filing(ticker, data, years))
                except httpx.HTTPError:
                    continue
        return results
