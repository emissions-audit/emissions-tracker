import pytest

from src.pipeline.normalize import normalize_value, normalize_scope


def test_normalize_t_co2e_passthrough():
    assert normalize_value(1_000_000.0, "t_co2e") == 1_000_000.0


def test_normalize_metric_tons_co2e_passthrough():
    assert normalize_value(1_000_000.0, "metric_tons_co2e") == 1_000_000.0


def test_normalize_unit_case_insensitive():
    assert normalize_value(1_000.0, "T_CO2E") == 1_000.0


def test_normalize_unknown_unit_raises():
    with pytest.raises(ValueError, match="Unknown unit"):
        normalize_value(1.0, "mt_co2e")


def test_normalize_scope_names():
    assert normalize_scope("Scope 1") == "1"
    assert normalize_scope("scope 2") == "2"
    assert normalize_scope("Scope 3") == "3"
    assert normalize_scope("Scope 1+2") == "1+2"
    assert normalize_scope("Total") == "total"
    assert normalize_scope("1") == "1"


def test_normalize_scope_unknown_raises():
    with pytest.raises(ValueError, match="Unknown scope"):
        normalize_scope("something weird")
