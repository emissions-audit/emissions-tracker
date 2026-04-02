from src.pipeline.company_mapping import resolve_ticker, get_all_tickers


ALL_SEED_TICKERS = [
    "XOM", "CVX", "SHEL", "BP", "TTE", "COP", "ENI", "EQNR",
    "OXY", "DVN", "HES", "MRO", "EOG", "FANG",
    "MPC", "PSX", "VLO",
    "SLB", "BKR", "HAL",
]


def test_exact_match():
    assert resolve_ticker("ExxonMobil") == "XOM"
    assert resolve_ticker("Chevron") == "CVX"


def test_variant_match():
    assert resolve_ticker("Exxon Mobil Corporation") == "XOM"
    assert resolve_ticker("Chevron U.S.A. Inc.") == "CVX"


def test_case_insensitive():
    assert resolve_ticker("exxonmobil") == "XOM"
    assert resolve_ticker("SHELL") == "SHEL"


def test_normalized_suffix_stripping():
    assert resolve_ticker("Halliburton Company") == "HAL"
    assert resolve_ticker("Eni S.p.A.") == "ENI"


def test_unknown_facility():
    assert resolve_ticker("Random Unknown Corp") is None


def test_all_seed_companies_covered():
    """Every one of the 20 seed tickers must be resolvable from at least one name."""
    resolved = set(get_all_tickers())
    for ticker in ALL_SEED_TICKERS:
        assert ticker in resolved, f"Seed ticker {ticker} not covered"


def test_get_all_tickers():
    tickers = get_all_tickers()
    assert isinstance(tickers, list)
    assert len(tickers) == 20
    assert set(tickers) == set(ALL_SEED_TICKERS)
