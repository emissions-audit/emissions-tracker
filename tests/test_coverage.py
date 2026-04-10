import uuid
from collections import defaultdict
from datetime import datetime

from src.pipeline.coverage import compute_coverage_matrices, compute_alerts

def _make_company_id():
    return uuid.uuid4()

XOM_ID = _make_company_id()
CVX_ID = _make_company_id()

FILING_TYPES = ["epa_ghgrp", "climate_trace", "eu_ets", "10k_xbrl", "cdp_response", "carb_sb253"]


class TestComputeCoverageMatrices:
    """Test the pure computation that turns query rows into JSONB dicts."""

    def test_source_year_matrix(self):
        source_year_rows = [("epa_ghgrp", 2022, 112), ("epa_ghgrp", 2023, 121)]
        result = compute_coverage_matrices(
            source_year_rows=source_year_rows, company_source_rows=[], company_year_rows=[],
            cv_flag_rows=[], total_emission_tuples=0, cv_count=0, filing_types=FILING_TYPES,
        )
        assert result["by_source_year"]["epa_ghgrp"] == {"2022": 112, "2023": 121}
        assert result["by_source_year"]["climate_trace"] == {}
        assert result["by_source_year"]["eu_ets"] == {}

    def test_company_source_matrix(self):
        company_source_rows = [("XOM", "epa_ghgrp", 8), ("CVX", "epa_ghgrp", 6)]
        result = compute_coverage_matrices(
            source_year_rows=[], company_source_rows=company_source_rows, company_year_rows=[],
            cv_flag_rows=[], total_emission_tuples=0, cv_count=0, filing_types=FILING_TYPES,
        )
        assert result["by_company_source"]["XOM"]["epa_ghgrp"] == 8
        assert result["by_company_source"]["XOM"]["climate_trace"] == 0
        assert result["by_company_source"]["CVX"]["epa_ghgrp"] == 6

    def test_company_year_matrix(self):
        company_year_rows = [("XOM", 2022, 4), ("XOM", 2023, 4), ("CVX", 2022, 3)]
        result = compute_coverage_matrices(
            source_year_rows=[], company_source_rows=[], company_year_rows=company_year_rows,
            cv_flag_rows=[], total_emission_tuples=0, cv_count=0, filing_types=FILING_TYPES,
        )
        assert result["by_company_year"]["XOM"] == {"2022": 4, "2023": 4}
        assert result["by_company_year"]["CVX"] == {"2022": 3}

    def test_cv_coverage_pct(self):
        result = compute_coverage_matrices(
            source_year_rows=[], company_source_rows=[], company_year_rows=[],
            cv_flag_rows=[("green", 5), ("red", 15)], total_emission_tuples=100, cv_count=20,
            filing_types=FILING_TYPES,
        )
        assert result["cv_by_flag"] == {"green": 5, "yellow": 0, "red": 15}
        assert float(result["cv_coverage_pct"]) == 20.0

    def test_cv_coverage_pct_zero_tuples(self):
        result = compute_coverage_matrices(
            source_year_rows=[], company_source_rows=[], company_year_rows=[],
            cv_flag_rows=[], total_emission_tuples=0, cv_count=0, filing_types=FILING_TYPES,
        )
        assert float(result["cv_coverage_pct"]) == 0.0


class TestComputeAlerts:
    """Test alert generation by comparing current vs previous snapshot data."""

    def test_regression_critical_source_drops(self):
        previous = {"by_source_year": {"epa_ghgrp": {"2022": 100, "2023": 100}}}
        current = {"by_source_year": {"epa_ghgrp": {}}}
        alerts = compute_alerts(current, previous)
        regression_alerts = [a for a in alerts if a["type"] == "regression" and a["severity"] == "critical"]
        assert len(regression_alerts) == 1
        assert "epa_ghgrp" in regression_alerts[0]["message"]

    def test_regression_warning_company_loses_source(self):
        previous = {"by_company_source": {"XOM": {"epa_ghgrp": 8, "climate_trace": 3}}}
        current = {"by_company_source": {"XOM": {"epa_ghgrp": 8, "climate_trace": 0}}}
        alerts = compute_alerts(current, previous)
        regression_warnings = [a for a in alerts if a["type"] == "regression" and a["severity"] == "warning"]
        assert len(regression_warnings) == 1
        assert "XOM" in regression_warnings[0]["message"]

    def test_staleness_never_produced(self):
        current = {"by_source_year": {"epa_ghgrp": {"2022": 100}, "eu_ets": {}}}
        alerts = compute_alerts(current, previous=None)
        staleness = [a for a in alerts if a["type"] == "staleness"]
        assert any("eu_ets" in a["message"] for a in staleness)

    def test_quality_low_cv_coverage(self):
        current = {"cv_coverage_pct": 4.2, "cv_by_flag": {"green": 1, "yellow": 0, "red": 23}}
        alerts = compute_alerts(current, previous=None)
        quality = [a for a in alerts if a["type"] == "quality" and a["severity"] == "warning"]
        assert len(quality) == 1

    def test_quality_majority_red(self):
        current = {"cv_coverage_pct": 25.0, "cv_by_flag": {"green": 1, "yellow": 0, "red": 23}}
        alerts = compute_alerts(current, previous=None)
        quality_info = [a for a in alerts if a["type"] == "quality" and a["severity"] == "info"]
        assert len(quality_info) == 1

    def test_staleness_critical_source_went_dark(self):
        previous = {"by_source_year": {"epa_ghgrp": {"2022": 100}, "eu_ets": {"2022": 50}}}
        current = {"by_source_year": {"epa_ghgrp": {"2022": 100}, "eu_ets": {}}, "cv_coverage_pct": 50.0, "cv_by_flag": {"green": 5, "yellow": 0, "red": 5}}
        alerts = compute_alerts(current, previous)
        staleness = [a for a in alerts if a["type"] == "staleness" and a["severity"] == "warning"]
        never_produced = [a for a in staleness if "never produced" in a["message"]]
        assert not any("eu_ets" in a["message"] for a in never_produced), "eu_ets previously had data, should not say 'never produced'"

    def test_no_regression_on_first_run(self):
        current = {"by_source_year": {"epa_ghgrp": {"2022": 100}}, "cv_coverage_pct": 50.0, "cv_by_flag": {"green": 10, "yellow": 0, "red": 0}}
        alerts = compute_alerts(current, previous=None)
        regression = [a for a in alerts if a["type"] == "regression"]
        assert len(regression) == 0


from src.pipeline.coverage import format_report, format_brief


class TestFormatReport:
    """Test the CLI report output formatting."""

    def _make_snapshot_dict(self):
        return {
            "computed_at": datetime(2026, 4, 10, 14, 30),
            "total_companies": 20,
            "total_emissions": 233,
            "total_filings": 15,
            "total_cross_validations": 24,
            "year_min": 2022,
            "year_max": 2023,
            "by_source_year": {
                "epa_ghgrp": {"2022": 112, "2023": 121},
                "climate_trace": {},
                "eu_ets": {},
                "10k_xbrl": {},
                "cdp_response": {},
                "carb_sb253": {},
            },
            "by_company_source": {
                "XOM": {"epa_ghgrp": 8, "climate_trace": 0, "eu_ets": 0, "10k_xbrl": 0, "cdp_response": 0, "carb_sb253": 0},
            },
            "by_company_year": {"XOM": {"2022": 4, "2023": 4}},
            "cv_by_flag": {"green": 1, "yellow": 0, "red": 23},
            "cv_coverage_pct": 4.2,
            "alerts": [
                {"type": "staleness", "severity": "warning", "message": "eu_ets has never produced data", "detail": {}},
            ],
        }

    def test_format_report_contains_summary(self):
        output = format_report(self._make_snapshot_dict())
        assert "Companies: 20" in output
        assert "Emissions: 233" in output
        assert "Sources active: 1/6" in output

    def test_format_report_contains_source_year_table(self):
        output = format_report(self._make_snapshot_dict())
        assert "epa_ghgrp" in output
        assert "112" in output
        assert "121" in output

    def test_format_report_contains_alerts(self):
        output = format_report(self._make_snapshot_dict())
        assert "eu_ets has never produced data" in output

    def test_format_brief_is_short(self):
        data = self._make_snapshot_dict()
        output = format_brief(data)
        assert "Emissions: 233" in output
        assert "Sources active: 1/6" in output
        assert "112" not in output
