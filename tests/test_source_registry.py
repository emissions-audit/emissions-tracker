"""Verify all 6 data sources are registered and coverage system knows about them."""


def test_all_sources_registered_in_source_map():
    from src.pipeline.cli import SOURCE_MAP
    expected = {"edgar", "climate_trace", "cdp", "carb", "epa_ghgrp", "eu_ets"}
    assert set(SOURCE_MAP.keys()) == expected


def test_all_filing_types_in_coverage():
    from src.pipeline.coverage import ALL_FILING_TYPES
    expected = {"epa_ghgrp", "climate_trace", "eu_ets", "10k_xbrl", "cdp_response", "carb_sb253"}
    assert set(ALL_FILING_TYPES) == expected
