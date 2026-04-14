import pytest
import httpx
import respx

from emissions_tracker import EmissionsTracker
from emissions_tracker.client import EmissionsTrackerError
from emissions_tracker.models import Company, Emission, Stats


BASE = "https://test-api.example.com"

COMPANY_JSON = {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Shell plc",
    "ticker": "SHEL",
    "sector": "energy",
    "subsector": "oil_gas_integrated",
    "country": "GB",
    "isin": "GB00BP6MXD84",
    "website": None,
}

PAGINATED_COMPANIES = {
    "items": [COMPANY_JSON],
    "total": 1,
    "limit": 50,
    "offset": 0,
}

EMISSION_JSON = {
    "id": "00000000-0000-0000-0000-000000000010",
    "company_id": "00000000-0000-0000-0000-000000000001",
    "year": 2023,
    "scope": "1",
    "value_mt_co2e": 68000000.0,
    "methodology": None,
    "verified": None,
    "source_id": None,
}

STATS_JSON = {
    "company_count": 52,
    "filing_count": 200,
    "emission_count": 1500,
    "year_range": {"min": 2020, "max": 2024},
    "last_updated": "2026-04-14T08:00:00",
}


@respx.mock
def test_list_companies():
    respx.get(f"{BASE}/v1/companies").mock(
        return_value=httpx.Response(200, json=PAGINATED_COMPANIES)
    )
    with EmissionsTracker(base_url=BASE) as client:
        result = client.list_companies()
    assert result.total == 1
    assert isinstance(result.items[0], Company)
    assert result.items[0].name == "Shell plc"


@respx.mock
def test_list_companies_with_filters():
    respx.get(f"{BASE}/v1/companies").mock(
        return_value=httpx.Response(200, json=PAGINATED_COMPANIES)
    )
    with EmissionsTracker(base_url=BASE) as client:
        result = client.list_companies(sector="energy", country="GB")
    assert result.total == 1
    req = respx.calls[0].request
    query = str(req.url)
    assert "sector=energy" in query
    assert "country=GB" in query


@respx.mock
def test_get_company():
    cid = "00000000-0000-0000-0000-000000000001"
    respx.get(f"{BASE}/v1/companies/{cid}").mock(
        return_value=httpx.Response(200, json=COMPANY_JSON)
    )
    with EmissionsTracker(base_url=BASE) as client:
        company = client.get_company(cid)
    assert isinstance(company, Company)
    assert company.ticker == "SHEL"


@respx.mock
def test_list_emissions():
    paginated = {"items": [EMISSION_JSON], "total": 1, "limit": 50, "offset": 0}
    respx.get(f"{BASE}/v1/emissions").mock(
        return_value=httpx.Response(200, json=paginated)
    )
    with EmissionsTracker(base_url=BASE) as client:
        result = client.list_emissions(year=2023, scope="1")
    assert isinstance(result.items[0], Emission)
    assert result.items[0].value_mt_co2e == 68000000.0


@respx.mock
def test_get_stats():
    respx.get(f"{BASE}/v1/stats").mock(
        return_value=httpx.Response(200, json=STATS_JSON)
    )
    with EmissionsTracker(base_url=BASE) as client:
        stats = client.get_stats()
    assert isinstance(stats, Stats)
    assert stats.company_count == 52


@respx.mock
def test_list_discrepancies():
    disc_json = {
        "items": [{
            "company_id": "00000000-0000-0000-0000-000000000001",
            "company_name": "Shell plc",
            "ticker": "SHEL",
            "year": 2023,
            "scope": "1",
            "spread_pct": 10.77,
            "delta_mt_co2e": 7000000,
            "flag": "yellow",
            "source_count": 2,
            "min_value": 65000000,
            "max_value": 72000000,
            "sources": [
                {"source_type": "regulatory", "value_mt_co2e": 65000000, "filing_url": None},
                {"source_type": "satellite", "value_mt_co2e": 72000000, "filing_url": None},
            ],
        }],
        "total": 1,
        "limit": 50,
        "offset": 0,
    }
    respx.get(f"{BASE}/v1/discrepancies").mock(
        return_value=httpx.Response(200, json=disc_json)
    )
    with EmissionsTracker(base_url=BASE) as client:
        result = client.list_discrepancies(flag="yellow")
    assert result.items[0].spread_pct == 10.77
    assert len(result.items[0].sources) == 2


@respx.mock
def test_api_key_header():
    respx.get(f"{BASE}/v1/stats").mock(
        return_value=httpx.Response(200, json=STATS_JSON)
    )
    with EmissionsTracker(base_url=BASE, api_key="my-key") as client:
        client.get_stats()
    assert respx.calls[0].request.headers["X-API-Key"] == "my-key"


@respx.mock
def test_error_handling():
    respx.get(f"{BASE}/v1/companies/bad-id").mock(
        return_value=httpx.Response(404, json={"detail": "Company not found"})
    )
    with EmissionsTracker(base_url=BASE) as client:
        with pytest.raises(EmissionsTrackerError) as exc_info:
            client.get_company("bad-id")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail


@respx.mock
def test_none_params_excluded():
    respx.get(f"{BASE}/v1/companies").mock(
        return_value=httpx.Response(200, json=PAGINATED_COMPANIES)
    )
    with EmissionsTracker(base_url=BASE) as client:
        client.list_companies(sector=None, country=None)
    query = str(respx.calls[0].request.url)
    assert "sector" not in query
    assert "country" not in query
