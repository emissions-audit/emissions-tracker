import pytest
import httpx

from src.pipeline.sources.edgar import EdgarSource, parse_xbrl_filing


SAMPLE_XBRL_JSON = {
    "facts": {
        "us-gaap": {},
        "epa": {
            "GHGEmissionsScope1": {
                "units": {
                    "MtCO2e": [
                        {"val": 52.0, "fy": 2023, "fp": "FY", "form": "10-K"},
                        {"val": 50.0, "fy": 2022, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
            "GHGEmissionsScope2": {
                "units": {
                    "MtCO2e": [
                        {"val": 10.0, "fy": 2023, "fp": "FY", "form": "10-K"},
                    ]
                }
            },
        },
    }
}


def test_parse_xbrl_filing():
    results = parse_xbrl_filing("XOM", SAMPLE_XBRL_JSON, [2022, 2023])
    assert len(results) == 3

    scope1_2023 = [r for r in results if r.year == 2023 and r.scope == "Scope 1"][0]
    assert scope1_2023.value == 52.0
    assert scope1_2023.unit == "mt_co2e"
    assert scope1_2023.company_ticker == "XOM"

    scope1_2022 = [r for r in results if r.year == 2022 and r.scope == "Scope 1"][0]
    assert scope1_2022.value == 50.0


def test_parse_xbrl_filing_empty():
    empty_json = {"facts": {"us-gaap": {}}}
    results = parse_xbrl_filing("XOM", empty_json, [2023])
    assert results == []


@pytest.mark.asyncio
async def test_edgar_source_fetch_uses_correct_url(monkeypatch):
    """Verify EdgarSource constructs the correct EDGAR API URL."""
    captured_urls = []

    async def mock_get(self, url, **kwargs):
        captured_urls.append(url)
        response = httpx.Response(200, json={"facts": {"us-gaap": {}}})
        return response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    source = EdgarSource()
    results = await source.fetch_emissions(["XOM"], [2023])
    assert len(captured_urls) == 1
    assert "CIK" in captured_urls[0] or "companyfacts" in captured_urls[0]
    assert results == []
