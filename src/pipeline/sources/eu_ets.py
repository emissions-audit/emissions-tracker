"""EU Emissions Trading System (EU ETS) data source.

Downloads verified emissions data from the European Commission's Transaction
Log (EUTL) Excel exports and maps installations to company tickers.

EU ETS reports emissions at installation level in **tonnes CO2e** (Scope 1
only, as the scheme covers direct emissions from regulated installations).
"""

import io
import sys

import httpx

from src.pipeline.company_mapping import resolve_ticker
from src.pipeline.sources.base import BaseSource, RawEmission

# The EUTL publishes compliance data as annual Excel workbooks with UUID-based
# download URLs (no computable slug pattern). Each year's workbook contains the
# VERIFIED_EMISSIONS_{year} column for that year only, so we download each one
# separately. Refresh this map when the EC publishes new years — the canonical
# list lives at
# https://climate.ec.europa.eu/eu-action/eu-emissions-trading-system-eu-ets/union-registry_en
EU_ETS_COMPLIANCE_URLS = {
    2020: "https://climate.ec.europa.eu/document/download/2d3e055d-ba0e-46db-b4c1-e3a9210d7ddb_en?filename=compliance_2020_code_en.xlsx",
    2021: "https://climate.ec.europa.eu/document/download/86a31a71-dff3-4729-86d0-943685c20dc1_en?filename=compliance_2021_code_en.xlsx",
    2022: "https://climate.ec.europa.eu/document/download/7e7268a1-fa21-4f73-b368-6e9571262e2f_en?filename=compliance_2022_code_en.xlsx",
    2023: "https://climate.ec.europa.eu/document/download/42495a32-cb4c-4772-9a2a-d08781c8ed61_en?filename=compliance_2023_code_en.xlsx",
    2024: "https://climate.ec.europa.eu/document/download/b80300cf-7608-405d-969e-8b016687640e_en?filename=compliance_2024_code_en.xlsx",
}

EU_ETS_LATEST_AVAILABLE_YEAR = max(EU_ETS_COMPLIANCE_URLS)


def _resolve_installation_ticker(installation_name: str) -> str:
    """Resolve an EU ETS installation name to a stock ticker.

    EU ETS installation names typically follow the pattern
    ``"Company Name - Facility Description"``.  We try the full name first,
    then progressively shorter prefixes (splitting on `` - ``), and finally
    each whitespace-delimited token.  If nothing matches, the raw
    installation name is returned as-is.
    """
    # 1. Try the full installation name
    ticker = resolve_ticker(installation_name)
    if ticker is not None:
        return ticker

    # 2. Try prefix segments (split on " - ")
    parts = installation_name.split(" - ")
    if len(parts) > 1:
        # Try progressively shorter prefixes: "A - B - C" -> "A - B", then "A"
        for i in range(len(parts) - 1, 0, -1):
            prefix = " - ".join(parts[:i])
            ticker = resolve_ticker(prefix)
            if ticker is not None:
                return ticker

    # 3. Try the first segment alone (the company-name portion)
    first_segment = parts[0].strip()
    if first_segment != installation_name:
        ticker = resolve_ticker(first_segment)
        if ticker is not None:
            return ticker

    # 4. Try progressively shorter word prefixes of the first segment.
    #    E.g. "Shell Deutschland Oil GmbH" -> "Shell Deutschland Oil",
    #    "Shell Deutschland", "Shell"
    words = first_segment.split()
    for end in range(len(words) - 1, 0, -1):
        candidate = " ".join(words[:end])
        ticker = resolve_ticker(candidate)
        if ticker is not None:
            return ticker

    # 5. Fall back to the raw installation name
    return installation_name


def parse_eu_ets_data(records: list[dict], years: list[int]) -> list[RawEmission]:
    """Parse pre-extracted EU ETS installation dicts into RawEmission records.

    Each *record* represents one installation row from the EUTL Excel file
    (already converted to a flat dict).  Emissions columns follow the naming
    convention ``VERIFIED_EMISSIONS_{year}`` and contain tonnes CO2e or
    ``None`` when not yet verified.

    Parameters
    ----------
    records:
        List of dicts with at least ``INSTALLATION_NAME`` and one or more
        ``VERIFIED_EMISSIONS_{year}`` keys.
    years:
        Which reporting years to extract.

    Returns
    -------
    list[RawEmission]
        One entry per (installation, year) pair where the value is non-None.
    """
    results: list[RawEmission] = []

    for row in records:
        installation_name = row.get("INSTALLATION_NAME", "")

        ticker = _resolve_installation_ticker(installation_name)

        for year in years:
            col = f"VERIFIED_EMISSIONS_{year}"
            value = row.get(col)
            if value is None:
                continue

            source_url = (
                f"https://climate.ec.europa.eu/eu-action/eu-emissions-trading-system/"
                f"union-registry_en#tab-compliance-data"
            )

            results.append(
                RawEmission(
                    company_ticker=ticker,
                    year=year,
                    scope="Scope 1",
                    value=value,
                    unit="t_co2e",
                    methodology="eu_ets_verified",
                    verified=True,
                    source_url=source_url,
                    filing_type="eu_ets",
                    parser_used="excel",
                )
            )

    return results


class EuEtsSource(BaseSource):
    """EU ETS verified emissions data source."""

    name = "eu_ets"

    async def fetch_emissions(
        self, tickers: list[str], years: list[int]
    ) -> list[RawEmission]:
        """Download per-year EU ETS Excel workbooks and parse installation emissions.

        Each year has its own workbook (UUID-based URLs — see
        :data:`EU_ETS_COMPLIANCE_URLS`).  For each requested year that has a
        known URL, fetch the workbook, parse the ``VERIFIED_EMISSIONS_{year}``
        column, and map installation names to tickers. Silently skip years we
        don't have URLs for (e.g. current or future year where the EC has not
        yet published).

        Returns a merged list across all downloaded years.
        """
        results: list[RawEmission] = []
        target_years = [y for y in years if y in EU_ETS_COMPLIANCE_URLS]

        for year in target_years:
            try:
                records = await self._download_and_parse(year)
            except httpx.HTTPError as e:
                print(
                    f"  eu_ets {year} download failed: {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                continue
            except Exception as e:
                print(
                    f"  eu_ets {year} parse failed: {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                continue
            results.extend(parse_eu_ets_data(records, [year]))

        if tickers:
            ticker_set = {t.upper() for t in tickers}
            results = [r for r in results if r.company_ticker.upper() in ticker_set]

        return results

    async def _download_and_parse(self, year: int) -> list[dict]:
        """Download a single year's Excel workbook and convert rows to dicts."""
        from openpyxl import load_workbook

        url = EU_ETS_COMPLIANCE_URLS[year]

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

        wb = load_workbook(filename=io.BytesIO(response.content), read_only=True)
        ws = wb.active

        # Header is at row 21 (1-indexed in openpyxl).
        header_row_index = 21
        rows = list(ws.iter_rows(min_row=header_row_index, values_only=True))

        if not rows:
            return []

        headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]

        records: list[dict] = []
        for row in rows[1:]:
            record = dict(zip(headers, row))
            records.append(record)

        wb.close()
        return records
