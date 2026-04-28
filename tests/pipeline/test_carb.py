import json

import pytest

from src.pipeline.sources.carb import CarbSource, parse_carb_response, CARB_COMPANY_TO_TICKER


SAMPLE_CARB_DATA = [
    {
        "entity_name": "Chevron Corporation",
        "reporting_year": 2026,
        "naics_code": "211120",
        "scope_1_t_co2e": 55_000_000,
        "scope_2_t_co2e": 8_500_000,
        "scope_3_t_co2e": None,
        "verification_status": "third_party_verified",
        "verification_body": "Bureau Veritas",
        "reporting_deadline": "2026-08-01",
        "filing_url": "https://ww2.arb.ca.gov/sb253/filings/chevron-2026",
    },
    {
        "entity_name": "ExxonMobil Corporation",
        "reporting_year": 2026,
        "naics_code": "211120",
        "scope_1_t_co2e": 112_000_000,
        "scope_2_t_co2e": 14_000_000,
        "scope_3_t_co2e": 540_000_000,
        "verification_status": "third_party_verified",
        "verification_body": "DNV",
        "reporting_deadline": "2026-08-01",
        "filing_url": "https://ww2.arb.ca.gov/sb253/filings/exxonmobil-2026",
    },
    {
        "entity_name": "Some Unknown Corp",
        "reporting_year": 2026,
        "naics_code": "999999",
        "scope_1_t_co2e": 1_000,
        "scope_2_t_co2e": 500,
        "scope_3_t_co2e": None,
        "verification_status": "unverified",
        "verification_body": None,
        "reporting_deadline": "2026-08-01",
        "filing_url": None,
    },
]


def test_parse_carb_response_basic():
    results = parse_carb_response(SAMPLE_CARB_DATA, [2026])

    # Chevron: scope 1 + scope 2 (scope 3 is None)
    cvx = [r for r in results if r.company_ticker == "CVX"]
    assert len(cvx) == 2
    cvx_s1 = [r for r in cvx if r.scope == "Scope 1"][0]
    assert cvx_s1.value == 55_000_000
    assert cvx_s1.unit == "t_co2e"
    assert cvx_s1.methodology == "ghg_protocol"
    assert cvx_s1.verified is True
    assert cvx_s1.filing_type == "carb_sb253"

    cvx_s2 = [r for r in cvx if r.scope == "Scope 2"][0]
    assert cvx_s2.value == 8_500_000

    # ExxonMobil: scope 1, 2, 3
    xom = [r for r in results if r.company_ticker == "XOM"]
    assert len(xom) == 3
    xom_s3 = [r for r in xom if r.scope == "Scope 3"][0]
    assert xom_s3.value == 540_000_000
    assert xom_s3.verified is True
    assert xom_s3.filing_type == "carb_sb253"

    # Unknown corp uses entity_name as ticker
    unknown = [r for r in results if r.company_ticker == "Some Unknown Corp"]
    assert len(unknown) == 2  # scope 1 + scope 2, scope 3 is None


def test_parse_carb_response_filters_years():
    results = parse_carb_response(SAMPLE_CARB_DATA, [2025])
    assert results == []


def test_parse_carb_response_skips_null_scopes():
    data = [
        {
            "entity_name": "Chevron Corporation",
            "reporting_year": 2026,
            "naics_code": "211120",
            "scope_1_t_co2e": None,
            "scope_2_t_co2e": None,
            "scope_3_t_co2e": None,
            "verification_status": "third_party_verified",
            "verification_body": "Bureau Veritas",
            "reporting_deadline": "2026-08-01",
            "filing_url": None,
        },
    ]
    results = parse_carb_response(data, [2026])
    assert results == []


def test_parse_carb_response_verification_status():
    # third_party_verified -> True
    results = parse_carb_response(SAMPLE_CARB_DATA, [2026])
    cvx = [r for r in results if r.company_ticker == "CVX"][0]
    assert cvx.verified is True

    # unverified -> False
    unknown = [r for r in results if r.company_ticker == "Some Unknown Corp"][0]
    assert unknown.verified is False


def test_carb_company_to_ticker_mapping():
    assert "Chevron Corporation" in CARB_COMPANY_TO_TICKER
    assert CARB_COMPANY_TO_TICKER["Chevron Corporation"] == "CVX"
    assert "ExxonMobil Corporation" in CARB_COMPANY_TO_TICKER
    assert CARB_COMPANY_TO_TICKER["ExxonMobil Corporation"] == "XOM"
    assert "ConocoPhillips" in CARB_COMPANY_TO_TICKER
    assert CARB_COMPANY_TO_TICKER["ConocoPhillips"] == "COP"


@pytest.mark.asyncio
async def test_carb_source_fetch_from_file(tmp_path):
    data_file = tmp_path / "carb_data.json"
    data_file.write_text(json.dumps(SAMPLE_CARB_DATA))

    source = CarbSource(data_path=str(data_file))
    results = await source.fetch_emissions(tickers=["CVX"], years=[2026])

    assert len(results) == 2  # CVX scope 1 + scope 2
    assert all(r.company_ticker == "CVX" for r in results)


@pytest.mark.asyncio
async def test_carb_source_fetch_empty_without_data_path():
    source = CarbSource()
    results = await source.fetch_emissions(tickers=[], years=[2026])
    assert results == []


@pytest.mark.asyncio
async def test_carb_source_fetch_api_graceful_failure(monkeypatch):
    """If CARB API is not live, fetch_emissions should return empty list."""
    import httpx
    from src.pipeline.sources.carb import CarbSource

    async def mock_get(self, url, **kwargs):
        raise httpx.HTTPStatusError(
            "Not Found",
            request=httpx.Request("GET", url),
            response=httpx.Response(404),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
    source = CarbSource()
    results = await source.fetch_emissions(tickers=[], years=[2026])
    assert results == []
