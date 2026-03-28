from src.pipeline.normalize import normalize_value, normalize_scope


def test_normalize_mt_co2e_passthrough():
    assert normalize_value(1_000_000.0, "mt_co2e") == 1_000_000.0


def test_normalize_kt_to_mt():
    assert normalize_value(1_000.0, "kt_co2e") == 1_000_000.0


def test_normalize_t_to_mt():
    assert normalize_value(1_000_000_000.0, "t_co2e") == 1_000_000.0


def test_normalize_scope_names():
    assert normalize_scope("Scope 1") == "1"
    assert normalize_scope("scope 2") == "2"
    assert normalize_scope("Scope 3") == "3"
    assert normalize_scope("Scope 1+2") == "1+2"
    assert normalize_scope("Total") == "total"
    assert normalize_scope("1") == "1"


def test_normalize_scope_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown scope"):
        normalize_scope("something weird")
