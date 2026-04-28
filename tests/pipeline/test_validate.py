import uuid

from src.pipeline.validate import compute_cross_validations, compute_flag


def test_compute_flag_green():
    assert compute_flag(5.0) == "green"
    assert compute_flag(0.0) == "green"
    assert compute_flag(9.9) == "green"


def test_compute_flag_yellow():
    assert compute_flag(10.0) == "yellow"
    assert compute_flag(20.0) == "yellow"
    assert compute_flag(29.9) == "yellow"


def test_compute_flag_red():
    assert compute_flag(30.0) == "red"
    assert compute_flag(50.0) == "red"
    assert compute_flag(100.0) == "red"


def test_compute_cross_validations_multiple_sources():
    company_id = uuid.uuid4()
    filing_a = uuid.uuid4()
    filing_b = uuid.uuid4()

    emissions = [
        {"company_id": company_id, "year": 2023, "scope": "1",
         "value_t_co2e": 100_000_000, "source_id": filing_a},
        {"company_id": company_id, "year": 2023, "scope": "1",
         "value_t_co2e": 120_000_000, "source_id": filing_b},
    ]

    source_types = {
        filing_a: "regulatory",
        filing_b: "satellite",
    }

    results = compute_cross_validations(emissions, source_types)
    assert len(results) == 1

    cv = results[0]
    assert cv["company_id"] == company_id
    assert cv["year"] == 2023
    assert cv["scope"] == "1"
    assert cv["source_count"] == 2
    assert cv["min_value"] == 100_000_000
    assert cv["max_value"] == 120_000_000
    assert cv["spread_pct"] == 20.0
    assert cv["flag"] == "yellow"
    assert len(cv["entries"]) == 2


def test_compute_cross_validations_single_source_skipped():
    emissions = [
        {"company_id": uuid.uuid4(), "year": 2023, "scope": "1",
         "value_t_co2e": 100_000_000, "source_id": uuid.uuid4()},
    ]
    results = compute_cross_validations(emissions, {})
    assert results == []
