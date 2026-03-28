import pytest

from src.pipeline.sources.cdp import CdpSource, parse_cdp_response


SAMPLE_CDP_DATA = [
    {
        "organization": "Shell plc",
        "ticker": "SHEL",
        "year": 2023,
        "scope_1_mt_co2e": 68_000_000,
        "scope_2_mt_co2e": 10_000_000,
        "scope_3_mt_co2e": 1_200_000_000,
        "verification_status": "Third-party verified",
    },
]


def test_parse_cdp_response():
    results = parse_cdp_response(SAMPLE_CDP_DATA, [2023])
    assert len(results) == 3  # scope 1, 2, 3

    scope1 = [r for r in results if r.scope == "Scope 1"][0]
    assert scope1.value == 68_000_000
    assert scope1.unit == "mt_co2e"
    assert scope1.verified is True
    assert scope1.filing_type == "cdp_response"

    scope3 = [r for r in results if r.scope == "Scope 3"][0]
    assert scope3.value == 1_200_000_000


def test_parse_cdp_response_filters_years():
    results = parse_cdp_response(SAMPLE_CDP_DATA, [2022])
    assert results == []


def test_parse_cdp_response_missing_scopes():
    data = [{"organization": "Test", "ticker": "TST", "year": 2023,
             "scope_1_mt_co2e": 1000, "verification_status": "Not verified"}]
    results = parse_cdp_response(data, [2023])
    assert len(results) == 1
    assert results[0].scope == "Scope 1"
    assert results[0].verified is False
