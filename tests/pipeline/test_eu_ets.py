import pytest

import httpx

from src.pipeline.sources.eu_ets import parse_eu_ets_data


SAMPLE_EU_ETS_DATA = [
    {
        "REGISTRY_CODE": "DE",
        "INSTALLATION_NAME": "Shell Deutschland Oil GmbH - Rheinland Refinery",
        "INSTALLATION_IDENTIFIER": "DE-000000000001234",
        "PERMIT_IDENTIFIER": "DE1234",
        "MAIN_ACTIVITY_TYPE_CODE": "20",
        "VERIFIED_EMISSIONS_2022": 4500000,
        "VERIFIED_EMISSIONS_2023": 4200000,
        "VERIFIED_EMISSIONS_2024": None,
    },
    {
        "REGISTRY_CODE": "IT",
        "INSTALLATION_NAME": "Eni S.p.A. - Sannazzaro Refinery",
        "INSTALLATION_IDENTIFIER": "IT-000000000005678",
        "PERMIT_IDENTIFIER": "IT5678",
        "MAIN_ACTIVITY_TYPE_CODE": "20",
        "VERIFIED_EMISSIONS_2022": 3200000,
        "VERIFIED_EMISSIONS_2023": 3100000,
        "VERIFIED_EMISSIONS_2024": 2900000,
    },
    {
        "REGISTRY_CODE": "FR",
        "INSTALLATION_NAME": "Unknown French Factory",
        "INSTALLATION_IDENTIFIER": "FR-000000000009999",
        "PERMIT_IDENTIFIER": "FR9999",
        "MAIN_ACTIVITY_TYPE_CODE": "20",
        "VERIFIED_EMISSIONS_2022": 50000,
        "VERIFIED_EMISSIONS_2023": 48000,
        "VERIFIED_EMISSIONS_2024": 45000,
    },
]


def test_parse_eu_ets_basic():
    """Parse sample installation data into RawEmission records for multiple years."""
    results = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2022, 2023])

    # Shell: 2022 + 2023 = 2 records
    shell = [r for r in results if r.company_ticker == "SHEL"]
    assert len(shell) == 2
    shell_2022 = [r for r in shell if r.year == 2022][0]
    assert shell_2022.value == 4500000
    shell_2023 = [r for r in shell if r.year == 2023][0]
    assert shell_2023.value == 4200000

    # Eni: 2022 + 2023 = 2 records
    eni = [r for r in results if r.company_ticker == "ENI"]
    assert len(eni) == 2
    eni_2022 = [r for r in eni if r.year == 2022][0]
    assert eni_2022.value == 3200000

    # Unknown: 2022 + 2023 = 2 records (uses installation name as ticker)
    unknown = [r for r in results if r.company_ticker == "Unknown French Factory"]
    assert len(unknown) == 2

    # Total: 3 installations * 2 years = 6 records
    assert len(results) == 6


def test_parse_eu_ets_ticker_resolution():
    """Installations owned by known companies get correct tickers."""
    results = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2022])

    shell = [r for r in results if r.company_ticker == "SHEL"]
    assert len(shell) == 1
    assert shell[0].company_ticker == "SHEL"

    eni = [r for r in results if r.company_ticker == "ENI"]
    assert len(eni) == 1
    assert eni[0].company_ticker == "ENI"


def test_parse_eu_ets_unknown_installation():
    """Unknown installations use installation_name as company_ticker."""
    results = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2022])

    unknown = [r for r in results if r.company_ticker == "Unknown French Factory"]
    assert len(unknown) == 1
    assert unknown[0].company_ticker == "Unknown French Factory"
    assert unknown[0].value == 50000


def test_parse_eu_ets_year_filter():
    """Only returns emissions for requested years."""
    results_2023 = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2023])
    assert all(r.year == 2023 for r in results_2023)
    assert len(results_2023) == 3  # All 3 installations have 2023 data

    results_2024 = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2024])
    # Shell 2024 is None -> skipped, Eni and Unknown have values
    assert len(results_2024) == 2
    assert all(r.year == 2024 for r in results_2024)

    # Year not present in data at all
    results_2020 = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2020])
    assert results_2020 == []


def test_parse_eu_ets_missing_values():
    """Handles None/empty values in VERIFIED_EMISSIONS columns gracefully."""
    data_with_nones = [
        {
            "REGISTRY_CODE": "DE",
            "INSTALLATION_NAME": "Shell Deutschland Oil GmbH - Rheinland Refinery",
            "INSTALLATION_IDENTIFIER": "DE-000000000001234",
            "PERMIT_IDENTIFIER": "DE1234",
            "MAIN_ACTIVITY_TYPE_CODE": "20",
            "VERIFIED_EMISSIONS_2022": None,
            "VERIFIED_EMISSIONS_2023": None,
            "VERIFIED_EMISSIONS_2024": None,
        },
    ]
    results = parse_eu_ets_data(data_with_nones, [2022, 2023, 2024])
    assert results == []


def test_parse_eu_ets_metadata():
    """Verify correct metadata on every RawEmission record."""
    results = parse_eu_ets_data(SAMPLE_EU_ETS_DATA, [2022])

    for r in results:
        assert r.filing_type == "eu_ets"
        assert r.methodology == "eu_ets_verified"
        assert r.scope == "Scope 1"
        assert r.unit == "t_co2e"
        assert r.verified is True
        assert r.parser_used == "excel"


def test_eu_ets_download_url_construction():
    """The download URL should include the requested year."""
    from src.pipeline.sources.eu_ets import EU_ETS_DOWNLOAD_URL
    url = EU_ETS_DOWNLOAD_URL.format(year=2023)
    assert "2023" in url
    assert "climate.ec.europa.eu" in url


@pytest.mark.asyncio
async def test_eu_ets_source_handles_download_error(monkeypatch):
    """If the Excel download fails, fetch_emissions should return empty list."""
    from src.pipeline.sources.eu_ets import EuEtsSource

    async def mock_get(self, url, **kwargs):
        raise httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", url),
            response=httpx.Response(404),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    source = EuEtsSource()
    results = await source.fetch_emissions(tickers=["SHEL"], years=[2023])
    assert results == []
