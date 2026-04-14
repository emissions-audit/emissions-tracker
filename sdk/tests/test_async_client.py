import httpx
import respx

from emissions_tracker import AsyncEmissionsTracker
from emissions_tracker.models import Company, Stats


BASE = "https://test-api.example.com"

COMPANY_JSON = {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Shell plc",
    "ticker": "SHEL",
    "sector": "energy",
    "subsector": "oil_gas_integrated",
    "country": "GB",
    "isin": None,
    "website": None,
}

STATS_JSON = {
    "company_count": 52,
    "filing_count": 200,
    "emission_count": 1500,
    "year_range": {"min": 2020, "max": 2024},
    "last_updated": "2026-04-14T08:00:00",
}


@respx.mock
async def test_async_list_companies():
    paginated = {"items": [COMPANY_JSON], "total": 1, "limit": 50, "offset": 0}
    respx.get(f"{BASE}/v1/companies").mock(
        return_value=httpx.Response(200, json=paginated)
    )
    async with AsyncEmissionsTracker(base_url=BASE) as client:
        result = await client.list_companies()
    assert result.total == 1
    assert isinstance(result.items[0], Company)


@respx.mock
async def test_async_get_stats():
    respx.get(f"{BASE}/v1/stats").mock(
        return_value=httpx.Response(200, json=STATS_JSON)
    )
    async with AsyncEmissionsTracker(base_url=BASE, api_key="test") as client:
        stats = await client.get_stats()
    assert isinstance(stats, Stats)
    assert stats.company_count == 52


@respx.mock
async def test_async_api_key_header():
    respx.get(f"{BASE}/v1/stats").mock(
        return_value=httpx.Response(200, json=STATS_JSON)
    )
    async with AsyncEmissionsTracker(base_url=BASE, api_key="async-key") as client:
        await client.get_stats()
    assert respx.calls[0].request.headers["X-API-Key"] == "async-key"
