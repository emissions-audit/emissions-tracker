import pytest
import httpx

from src.pipeline.sources.climate_trace import (
    ClimateTraceSource,
    TICKER_TO_OWNER,
    parse_asset_emissions,
    _asset_owned_by,
)

# Companies confirmed in Climate TRACE's oil-and-gas-production dataset.
EXPECTED_TICKERS = [
    "XOM", "CVX", "COP", "SHEL", "BP",
    "TTE", "ENI", "EQNR", "OXY", "MPC", "MRO",
]

# v6 API response shape — assets with nested EmissionsSummary and Owners.
SAMPLE_ASSETS = [
    {
        "AssetName": "Baytown Refinery",
        "Owners": [{"CompanyName": "Exxon Mobil Corp"}],
        "EmissionsSummary": [
            {"Gas": "co2e_100yr", "EmissionsQuantity": 15_200_000},
            {"Gas": "co2", "EmissionsQuantity": 14_000_000},
        ],
    },
    {
        "AssetName": "Beaumont Refinery",
        "Owners": [{"CompanyName": "Exxon Mobil Corp"}],
        "EmissionsSummary": [
            {"Gas": "co2e_100yr", "EmissionsQuantity": 8_500_000},
        ],
    },
    {
        "AssetName": "Basin Aggregate",
        "Owners": [],
        "EmissionsSummary": [
            {"Gas": "co2e_100yr", "EmissionsQuantity": 999_999},
        ],
    },
    {
        "AssetName": "Chevron Refinery",
        "Owners": [{"CompanyName": "Chevron Corp"}],
        "EmissionsSummary": [
            {"Gas": "co2e_100yr", "EmissionsQuantity": 5_000_000},
        ],
    },
]


def test_asset_owned_by_match():
    asset = {"Owners": [{"CompanyName": "Exxon Mobil Corp"}]}
    assert _asset_owned_by(asset, "Exxon Mobil Corp") is True


def test_asset_owned_by_no_match():
    asset = {"Owners": [{"CompanyName": "Chevron Corp"}]}
    assert _asset_owned_by(asset, "Exxon Mobil Corp") is False


def test_asset_owned_by_empty_owners():
    asset = {"Owners": []}
    assert _asset_owned_by(asset, "Exxon Mobil Corp") is False


def test_asset_owned_by_null_owners():
    """API sometimes returns Owners: null instead of an empty list."""
    asset = {"Owners": None}
    assert _asset_owned_by(asset, "Exxon Mobil Corp") is False


def test_parse_asset_emissions_with_owner_filter():
    """Only Exxon-owned assets should be summed when owner is specified."""
    result = parse_asset_emissions("XOM", SAMPLE_ASSETS, 2023, owner="Exxon Mobil Corp")
    assert result is not None
    assert result.value == 23_700_000  # 15.2M + 8.5M (Exxon only)
    assert result.unit == "t_co2e"
    assert result.scope == "Scope 1"
    assert result.filing_type == "climate_trace"


def test_parse_asset_emissions_without_owner_sums_all():
    """Without owner filter, all assets are summed (backward compat)."""
    result = parse_asset_emissions("XOM", SAMPLE_ASSETS, 2023)
    assert result is not None
    # 15.2M + 8.5M + 999K + 5M = 29,699,999
    assert result.value == 29_699_999


def test_parse_asset_emissions_zero_returns_none():
    result = parse_asset_emissions("XOM", [], 2023, owner="Exxon Mobil Corp")
    assert result is None


def test_ticker_map_has_expected_companies():
    """All confirmed Climate TRACE tickers must be present."""
    missing = [t for t in EXPECTED_TICKERS if t not in TICKER_TO_OWNER]
    assert missing == [], f"Missing tickers: {missing}"
    assert len(TICKER_TO_OWNER) == 11


@pytest.mark.asyncio
async def test_climate_trace_source_constructs_url(monkeypatch):
    captured = []

    async def mock_get(self, url, **kwargs):
        captured.append((url, kwargs.get("params", {})))
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"assets": []}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    source = ClimateTraceSource()
    await source.fetch_emissions(["XOM"], [2023])
    assert len(captured) == 1
    url, params = captured[0]
    assert "climatetrace" in url.lower() or "climate-trace" in url.lower()
    assert params["owners"] == "Exxon Mobil Corp"


@pytest.mark.asyncio
async def test_climate_trace_skips_unknown_tickers(monkeypatch):
    """Tickers not in TICKER_TO_OWNER should be silently skipped."""
    captured = []

    async def mock_get(self, url, **kwargs):
        captured.append(kwargs.get("params", {}))
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"assets": []}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    source = ClimateTraceSource()
    await source.fetch_emissions(["FAKE_TICKER"], [2023])
    assert len(captured) == 0


@pytest.mark.asyncio
async def test_climate_trace_client_side_filtering(monkeypatch):
    """fetch_emissions should only count assets owned by the target company."""

    async def mock_get(self, url, **kwargs):
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"assets": SAMPLE_ASSETS}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    source = ClimateTraceSource()
    results = await source.fetch_emissions(["XOM"], [2023])
    assert len(results) == 1
    # Should only include Exxon assets (15.2M + 8.5M), not Chevron or unowned
    assert results[0].value == 23_700_000
