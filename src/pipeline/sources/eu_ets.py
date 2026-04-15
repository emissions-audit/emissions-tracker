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

# The EUTL publishes annual compliance data as Excel workbooks.
# The URL pattern uses the reporting year; adjust as the EC changes hosting.
EU_ETS_DOWNLOAD_URL = (
    "https://climate.ec.europa.eu/document/download/"
    "compliance-data-for-installations-and-aircraft-operators_{year}"
)

# Verified EU ETS data publishes ~year+1. Clamp target year so we never request
# a future year that doesn't exist yet (returns 404).
EU_ETS_LATEST_AVAILABLE_YEAR = 2023


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
        """Download the EU ETS Excel file and parse installation emissions.

        1. Fetch the .xlsx workbook from the EUTL website.
        2. Parse with openpyxl (header at row 21, i.e. 0-indexed row 20).
        3. Extract ``VERIFIED_EMISSIONS_{year}`` columns for requested years.
        4. Map installations to tickers via :func:`resolve_ticker`.
        5. Filter to requested tickers (if non-empty).

        Returns an empty list if the download fails (404, timeout, etc.).
        """
        try:
            records = await self._download_and_parse(years)
        except httpx.HTTPError as e:
            print(f"  eu_ets download failed: {type(e).__name__}: {e}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"  eu_ets parse failed: {type(e).__name__}: {e}", file=sys.stderr)
            return []
        results = parse_eu_ets_data(records, years)

        if tickers:
            ticker_set = {t.upper() for t in tickers}
            results = [r for r in results if r.company_ticker.upper() in ticker_set]

        return results

    async def _download_and_parse(self, years: list[int]) -> list[dict]:
        """Download the Excel workbook and convert rows to dicts."""
        from openpyxl import load_workbook

        # Clamp the target year so we never request a future year that
        # hasn't been published yet (EU ETS publishes verified data ~year+1).
        target_year = (
            min(max(years), EU_ETS_LATEST_AVAILABLE_YEAR)
            if years
            else EU_ETS_LATEST_AVAILABLE_YEAR
        )
        url = EU_ETS_DOWNLOAD_URL.format(year=target_year)

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
