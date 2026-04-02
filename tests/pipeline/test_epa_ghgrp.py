import pytest

from src.pipeline.sources.epa_ghgrp import EpaGhgrpSource, parse_ghgrp_response


SAMPLE_GHGRP_DATA = [
    # Facility 1: ExxonMobil Baytown — two gas rows for 2023
    {
        "facility_id": "1001234",
        "facility_name": "ExxonMobil Baytown Refinery",
        "address1": "4500 Garth Rd",
        "city": "Baytown",
        "state": "TX",
        "zip": "77521",
        "year": 2023,
        "sector_name": "Petroleum Refineries",
        "gas_code": "CO2",
        "gas_name": "Carbon Dioxide",
        "co2e_emission": 8_500_000.0,
    },
    {
        "facility_id": "1001234",
        "facility_name": "ExxonMobil Baytown Refinery",
        "address1": "4500 Garth Rd",
        "city": "Baytown",
        "state": "TX",
        "zip": "77521",
        "year": 2023,
        "sector_name": "Petroleum Refineries",
        "gas_code": "CH4",
        "gas_name": "Methane",
        "co2e_emission": 120_000.0,
    },
    # Facility 2: Chevron Richmond — single gas row for 2023
    {
        "facility_id": "1005678",
        "facility_name": "Chevron Richmond Refinery",
        "address1": "841 Chevron Way",
        "city": "Richmond",
        "state": "CA",
        "zip": "94802",
        "year": 2023,
        "sector_name": "Petroleum Refineries",
        "gas_code": "CO2",
        "gas_name": "Carbon Dioxide",
        "co2e_emission": 4_200_000.0,
    },
    # Facility 1 again but for 2022
    {
        "facility_id": "1001234",
        "facility_name": "ExxonMobil Baytown Refinery",
        "address1": "4500 Garth Rd",
        "city": "Baytown",
        "state": "TX",
        "zip": "77521",
        "year": 2022,
        "sector_name": "Petroleum Refineries",
        "gas_code": "CO2",
        "gas_name": "Carbon Dioxide",
        "co2e_emission": 8_000_000.0,
    },
    # Facility 3: Unknown company
    {
        "facility_id": "9999999",
        "facility_name": "Acme Chemical Plant",
        "address1": "100 Industrial Blvd",
        "city": "Houston",
        "state": "TX",
        "zip": "77001",
        "year": 2023,
        "sector_name": "Chemicals",
        "gas_code": "CO2",
        "gas_name": "Carbon Dioxide",
        "co2e_emission": 500_000.0,
    },
]


def test_parse_ghgrp_response_basic():
    """Multiple gas rows per facility+year are aggregated into a single CO2e total."""
    results = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2022, 2023])

    # ExxonMobil Baytown 2023: CO2 (8.5M) + CH4 (120K) = 8,620,000
    xom_2023 = [
        r for r in results
        if r.company_ticker == "XOM" and r.year == 2023
    ]
    assert len(xom_2023) == 1
    assert xom_2023[0].value == pytest.approx(8_620_000.0)

    # ExxonMobil Baytown 2022: only CO2 row = 8,000,000
    xom_2022 = [
        r for r in results
        if r.company_ticker == "XOM" and r.year == 2022
    ]
    assert len(xom_2022) == 1
    assert xom_2022[0].value == pytest.approx(8_000_000.0)

    # Chevron Richmond 2023: single row = 4,200,000
    cvx_2023 = [
        r for r in results
        if r.company_ticker == "CVX" and r.year == 2023
    ]
    assert len(cvx_2023) == 1
    assert cvx_2023[0].value == pytest.approx(4_200_000.0)


def test_parse_ghgrp_ticker_resolution():
    """Facilities owned by known companies resolve to the correct ticker."""
    results = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2023])

    # "ExxonMobil Baytown Refinery" should resolve via company_mapping → "XOM"
    xom = [r for r in results if r.company_ticker == "XOM"]
    assert len(xom) >= 1

    # "Chevron Richmond Refinery" should resolve → "CVX"
    cvx = [r for r in results if r.company_ticker == "CVX"]
    assert len(cvx) >= 1


def test_parse_ghgrp_unknown_facility():
    """Unknown facilities use facility_name as company_ticker."""
    results = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2023])

    acme = [r for r in results if r.company_ticker == "Acme Chemical Plant"]
    assert len(acme) == 1
    assert acme[0].value == pytest.approx(500_000.0)


def test_parse_ghgrp_year_filter():
    """Only returns emissions for requested years."""
    results_2023 = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2023])
    assert all(r.year == 2023 for r in results_2023)

    results_2022 = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2022])
    assert all(r.year == 2022 for r in results_2022)
    # Only the ExxonMobil 2022 row
    assert len(results_2022) == 1

    # No data for 2021
    results_2021 = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2021])
    assert results_2021 == []


def test_parse_ghgrp_metadata():
    """Verify filing_type, methodology, scope, and unit on every record."""
    results = parse_ghgrp_response(SAMPLE_GHGRP_DATA, [2023])
    assert len(results) > 0

    for r in results:
        assert r.filing_type == "epa_ghgrp"
        assert r.methodology == "epa_mandatory"
        assert r.scope == "Scope 1"
        assert r.unit == "t_co2e"
        assert r.parser_used == "api"
