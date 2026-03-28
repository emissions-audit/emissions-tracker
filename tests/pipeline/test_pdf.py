import pytest

from src.pipeline.sources.pdf import parse_llm_response, build_extraction_prompt


def test_parse_llm_response():
    llm_output = """
    [
        {"scope": "Scope 1", "value": 68000000, "unit": "mt_co2e", "year": 2023, "methodology": "ghg_protocol", "verified": true},
        {"scope": "Scope 2", "value": 10000000, "unit": "mt_co2e", "year": 2023, "methodology": "ghg_protocol", "verified": true}
    ]
    """
    results = parse_llm_response("SHEL", llm_output, "https://example.com/report.pdf")
    assert len(results) == 2
    assert results[0].company_ticker == "SHEL"
    assert results[0].scope == "Scope 1"
    assert results[0].value == 68_000_000
    assert results[0].filing_type == "sustainability_report"
    assert results[0].parser_used == "llm"


def test_parse_llm_response_empty():
    results = parse_llm_response("SHEL", "[]", "https://example.com")
    assert results == []


def test_parse_llm_response_invalid_json():
    results = parse_llm_response("SHEL", "not valid json", "https://example.com")
    assert results == []


def test_build_extraction_prompt():
    prompt = build_extraction_prompt("This is a sample sustainability report text about emissions.")
    assert "scope" in prompt.lower()
    assert "json" in prompt.lower()
    assert "sustainability report" in prompt.lower()
