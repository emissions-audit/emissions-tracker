import pytest
import httpx

from src.pipeline.sources.climate_trace import ClimateTraceSource, parse_asset_emissions


SAMPLE_RESPONSE = [
    {
        "asset_name": "Baytown Refinery",
        "gas": "co2e_100yr",
        "emissions_quantity": 15_200_000,
        "emissions_factor_units": "tonnes_of_co2e",
        "start_time": "2023-01-01",
        "end_time": "2023-12-31",
        "source_name": "Climate TRACE",
    },
    {
        "asset_name": "Beaumont Refinery",
        "gas": "co2e_100yr",
        "emissions_quantity": 8_500_000,
        "emissions_factor_units": "tonnes_of_co2e",
        "start_time": "2023-01-01",
        "end_time": "2023-12-31",
        "source_name": "Climate TRACE",
    },
]


def test_parse_asset_emissions():
    results = parse_asset_emissions("XOM", SAMPLE_RESPONSE, [2023])
    assert len(results) == 1  # rolled up to one per year
    assert results[0].year == 2023
    assert results[0].value == 23_700_000  # sum of two assets
    assert results[0].unit == "t_co2e"
    assert results[0].scope == "Scope 1"
    assert results[0].filing_type == "climate_trace"


def test_parse_asset_emissions_filters_years():
    results = parse_asset_emissions("XOM", SAMPLE_RESPONSE, [2022])
    assert results == []


@pytest.mark.asyncio
async def test_climate_trace_source_constructs_url(monkeypatch):
    captured = []

    async def mock_get(self, url, **kwargs):
        captured.append(url)
        request = httpx.Request("GET", url)
        return httpx.Response(200, json=[], request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    source = ClimateTraceSource()
    await source.fetch_emissions(["XOM"], [2023])
    assert len(captured) == 1
    assert "climatetrace" in captured[0].lower() or "climate-trace" in captured[0].lower()
