"""
E2E smoke tests — require Docker Compose stack running at localhost:8000.
Run via: bash scripts/e2e.sh
Skipped automatically when the API is not reachable.
"""
import httpx
import pytest

API_URL = "http://localhost:8000"


def api_is_running() -> bool:
    try:
        httpx.get(f"{API_URL}/v1/stats", timeout=2)
        return True
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not api_is_running(),
        reason="E2E: Docker Compose stack not running at localhost:8000",
    ),
]


class TestHealthAndStats:
    def test_stats_returns_200(self):
        r = httpx.get(f"{API_URL}/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert "company_count" in data
        assert "emission_count" in data

    def test_stats_has_seeded_companies(self):
        r = httpx.get(f"{API_URL}/v1/stats")
        data = r.json()
        assert data["company_count"] >= 20


class TestCompaniesEndpoint:
    def test_list_companies(self):
        r = httpx.get(f"{API_URL}/v1/companies")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 20
        assert len(data["items"]) > 0

    def test_filter_by_sector(self):
        r = httpx.get(f"{API_URL}/v1/companies", params={"sector": "energy"})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["sector"] == "energy"

    def test_get_single_company(self):
        r = httpx.get(f"{API_URL}/v1/companies", params={"limit": 1})
        company_id = r.json()["items"][0]["id"]
        r2 = httpx.get(f"{API_URL}/v1/companies/{company_id}")
        assert r2.status_code == 200
        assert r2.json()["id"] == company_id


class TestMetaEndpoints:
    def test_sectors(self):
        r = httpx.get(f"{API_URL}/v1/meta/sectors")
        assert r.status_code == 200
        sectors = r.json()
        assert len(sectors) > 0
        assert any(s["sector"] == "energy" for s in sectors)

    def test_methodology(self):
        r = httpx.get(f"{API_URL}/v1/meta/methodology")
        assert r.status_code == 200
        data = r.json()
        assert "sources" in data
        assert "cross_validation" in data


class TestAuthMiddleware:
    def test_anonymous_access_allowed(self):
        r = httpx.get(f"{API_URL}/v1/companies")
        assert r.status_code == 200
        assert "X-RateLimit-Limit" in r.headers

    def test_invalid_api_key_returns_401(self):
        r = httpx.get(
            f"{API_URL}/v1/companies",
            headers={"X-API-Key": "invalid-key-12345"},
        )
        assert r.status_code == 401


class TestSwaggerDocs:
    def test_openapi_json(self):
        r = httpx.get(f"{API_URL}/openapi.json")
        assert r.status_code == 200
        spec = r.json()
        assert spec["info"]["title"] == "Emissions Tracker API"

    def test_docs_page(self):
        r = httpx.get(f"{API_URL}/docs")
        assert r.status_code == 200
