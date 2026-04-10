"""Coverage snapshot computation and alerting.

Core logic is split into pure functions (compute_coverage_matrices,
compute_alerts) that accept pre-fetched query results, so they are
testable without a database.  The DB-aware function (create_snapshot)
wires queries -> pure logic -> DB write.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.shared.models import (
    Company, Emission, Filing, CrossValidation, CoverageSnapshot,
)

ALL_FILING_TYPES = [
    "epa_ghgrp", "climate_trace", "eu_ets", "10k_xbrl", "cdp_response", "carb_sb253",
]


# ---------------------------------------------------------------------------
# Pure computation (no DB dependency)
# ---------------------------------------------------------------------------

def compute_coverage_matrices(
    *,
    source_year_rows: list[tuple],
    company_source_rows: list[tuple],
    company_year_rows: list[tuple],
    cv_flag_rows: list[tuple],
    total_emission_tuples: int,
    cv_count: int,
    filing_types: list[str] | None = None,
) -> dict:
    """Turn raw GROUP BY rows into the JSONB-shaped coverage matrices."""
    filing_types = filing_types or ALL_FILING_TYPES

    # Source x Year
    by_source_year: dict[str, dict[str, int]] = {ft: {} for ft in filing_types}
    for filing_type, year, count in source_year_rows:
        if filing_type not in by_source_year:
            by_source_year[filing_type] = {}
        by_source_year[filing_type][str(year)] = count

    # Company x Source (include explicit zeros)
    tickers_seen: set[str] = set()
    company_source_map: dict[str, dict[str, int]] = defaultdict(lambda: {ft: 0 for ft in filing_types})
    for ticker, filing_type, count in company_source_rows:
        tickers_seen.add(ticker)
        company_source_map[ticker][filing_type] = count
    by_company_source = {t: dict(company_source_map[t]) for t in sorted(tickers_seen)}

    # Company x Year
    by_company_year: dict[str, dict[str, int]] = defaultdict(dict)
    for ticker, year, count in company_year_rows:
        by_company_year[ticker][str(year)] = count
    by_company_year = dict(by_company_year)

    # Cross-validation flags
    cv_by_flag = {"green": 0, "yellow": 0, "red": 0}
    for flag, count in cv_flag_rows:
        cv_by_flag[flag] = count

    # CV coverage percentage
    cv_coverage_pct = round((cv_count / total_emission_tuples) * 100, 2) if total_emission_tuples > 0 else 0.0

    return {
        "by_source_year": by_source_year,
        "by_company_source": by_company_source,
        "by_company_year": by_company_year,
        "cv_by_flag": cv_by_flag,
        "cv_coverage_pct": cv_coverage_pct,
    }


def compute_alerts(
    current: dict,
    previous: dict | None,
) -> list[dict]:
    """Generate alerts by comparing current coverage data to previous snapshot."""
    alerts: list[dict] = []

    # --- Regression alerts (require previous snapshot) ---
    if previous is not None:
        prev_src = previous.get("by_source_year", {})
        curr_src = current.get("by_source_year", {})
        for source, prev_years in prev_src.items():
            prev_total = sum(prev_years.values())
            curr_years = curr_src.get(source, {})
            curr_total = sum(curr_years.values())
            if prev_total > 0 and curr_total < prev_total * 0.9:
                alerts.append({
                    "type": "regression",
                    "severity": "critical",
                    "message": f"{source} record count dropped from {prev_total} to {curr_total}",
                    "detail": {"source": source, "previous": prev_total, "current": curr_total},
                })

        prev_cs = previous.get("by_company_source", {})
        curr_cs = current.get("by_company_source", {})
        for ticker, prev_sources in prev_cs.items():
            curr_sources = curr_cs.get(ticker, {})
            for source, prev_count in prev_sources.items():
                curr_count = curr_sources.get(source, 0)
                if prev_count > 0 and curr_count == 0:
                    alerts.append({
                        "type": "regression",
                        "severity": "warning",
                        "message": f"{ticker} lost all {source} records (was {prev_count})",
                        "detail": {"ticker": ticker, "source": source, "previous": prev_count},
                    })

    # --- Staleness alerts (always fire) ---
    curr_src = current.get("by_source_year", {})
    prev_src = (previous or {}).get("by_source_year", {})
    for source, years in curr_src.items():
        total = sum(years.values())
        prev_total = sum(prev_src.get(source, {}).values()) if previous else 0
        if total == 0 and prev_total == 0:
            alerts.append({
                "type": "staleness",
                "severity": "warning",
                "message": f"{source} has never produced data",
                "detail": {"source": source, "last_filing": None},
            })

    # --- Quality alerts (always fire) ---
    cv_pct = current.get("cv_coverage_pct", 0)
    if cv_pct < 20.0:
        alerts.append({
            "type": "quality",
            "severity": "warning",
            "message": f"Cross-validation coverage at {cv_pct}% (threshold: 20%)",
            "detail": {"cv_coverage_pct": cv_pct, "threshold": 20},
        })

    cv_flags = current.get("cv_by_flag", {})
    total_cv = sum(cv_flags.values())
    red_count = cv_flags.get("red", 0)
    if total_cv > 0 and red_count > total_cv * 0.5:
        alerts.append({
            "type": "quality",
            "severity": "info",
            "message": f"{red_count}/{total_cv} cross-validations are red-flagged (>{50}%)",
            "detail": {"red_count": red_count, "total": total_cv},
        })

    return alerts


# ---------------------------------------------------------------------------
# DB-aware functions (sync, used by pipeline CLI)
# ---------------------------------------------------------------------------

def _query_coverage_data(session: Session) -> dict:
    """Run the 3 GROUP BY queries + scalar counts and return raw data."""
    source_year_rows = session.execute(
        select(Filing.filing_type, Emission.year, func.count(Emission.id))
        .join(Filing, Emission.source_id == Filing.id)
        .group_by(Filing.filing_type, Emission.year)
    ).all()

    company_source_rows = session.execute(
        select(Company.ticker, Filing.filing_type, func.count(Emission.id))
        .join(Company, Emission.company_id == Company.id)
        .join(Filing, Emission.source_id == Filing.id)
        .group_by(Company.ticker, Filing.filing_type)
    ).all()

    company_year_rows = session.execute(
        select(Company.ticker, Emission.year, func.count(Emission.id))
        .join(Company, Emission.company_id == Company.id)
        .group_by(Company.ticker, Emission.year)
    ).all()

    cv_flag_rows = session.execute(
        select(CrossValidation.flag, func.count(CrossValidation.id))
        .group_by(CrossValidation.flag)
    ).all()

    total_companies = session.execute(select(func.count(Company.id))).scalar() or 0
    total_emissions = session.execute(select(func.count(Emission.id))).scalar() or 0
    total_filings = session.execute(select(func.count(Filing.id))).scalar() or 0
    total_cv = session.execute(select(func.count(CrossValidation.id))).scalar() or 0
    year_min = session.execute(select(func.min(Emission.year))).scalar()
    year_max = session.execute(select(func.max(Emission.year))).scalar()

    total_emission_tuples = session.execute(
        select(func.count())
        .select_from(
            select(Emission.company_id, Emission.year, Emission.scope)
            .distinct()
            .subquery()
        )
    ).scalar() or 0

    return {
        "source_year_rows": source_year_rows,
        "company_source_rows": company_source_rows,
        "company_year_rows": company_year_rows,
        "cv_flag_rows": cv_flag_rows,
        "total_companies": total_companies,
        "total_emissions": total_emissions,
        "total_filings": total_filings,
        "total_cv": total_cv,
        "year_min": year_min,
        "year_max": year_max,
        "total_emission_tuples": total_emission_tuples,
    }


def _get_previous_snapshot(session: Session) -> dict | None:
    """Load the most recent coverage snapshot, or None if none exist."""
    row = session.query(CoverageSnapshot).order_by(
        CoverageSnapshot.computed_at.desc()
    ).first()
    if row is None:
        return None
    return {
        "by_source_year": row.by_source_year,
        "by_company_source": row.by_company_source,
        "by_company_year": row.by_company_year,
        "cv_by_flag": row.cv_by_flag,
        "cv_coverage_pct": float(row.cv_coverage_pct),
    }


def create_snapshot(
    session: Session,
    trigger: str,
    source_filter: str | None = None,
    save: bool = True,
) -> CoverageSnapshot:
    """Compute coverage, generate alerts, optionally persist snapshot."""
    raw = _query_coverage_data(session)
    matrices = compute_coverage_matrices(
        source_year_rows=raw["source_year_rows"],
        company_source_rows=raw["company_source_rows"],
        company_year_rows=raw["company_year_rows"],
        cv_flag_rows=raw["cv_flag_rows"],
        total_emission_tuples=raw["total_emission_tuples"],
        cv_count=raw["total_cv"],
    )

    previous = _get_previous_snapshot(session)
    alerts = compute_alerts(matrices, previous)

    snapshot = CoverageSnapshot(
        id=uuid.uuid4(),
        computed_at=datetime.utcnow(),
        trigger=trigger,
        source_filter=source_filter,
        total_companies=raw["total_companies"],
        total_emissions=raw["total_emissions"],
        total_filings=raw["total_filings"],
        total_cross_validations=raw["total_cv"],
        year_min=raw["year_min"],
        year_max=raw["year_max"],
        by_source_year=matrices["by_source_year"],
        by_company_source=matrices["by_company_source"],
        by_company_year=matrices["by_company_year"],
        cv_by_flag=matrices["cv_by_flag"],
        cv_coverage_pct=matrices["cv_coverage_pct"],
        alerts=alerts,
    )

    if save:
        session.add(snapshot)
        session.commit()

    return snapshot


# ---------------------------------------------------------------------------
# CLI formatting
# ---------------------------------------------------------------------------

def _sources_active(by_source_year: dict) -> int:
    """Count sources that have at least one year with records."""
    return sum(1 for years in by_source_year.values() if years)


def format_report(data: dict, full: bool = False) -> str:
    """Full CLI coverage report."""
    by_sy = data["by_source_year"]
    by_cs = data["by_company_source"]
    cv_flags = data["cv_by_flag"]
    alerts = data.get("alerts", [])
    active = _sources_active(by_sy)
    total_sources = len(by_sy)

    computed = data["computed_at"]
    if isinstance(computed, datetime):
        ts = computed.strftime("%Y-%m-%d %H:%M UTC")
    else:
        ts = str(computed)

    lines = [
        f"\U0001f4ca Coverage Report \u2014 {ts}",
        "\u2501" * 40,
        "",
        "\U0001f4c8 Summary",
        f"   Companies: {data['total_companies']} | Emissions: {data['total_emissions']} | Filings: {data['total_filings']}",
        f"   Years: {data['year_min']}\u2013{data['year_max']} | Sources active: {active}/{total_sources}",
        f"   Cross-validation coverage: {data['cv_coverage_pct']}%",
        "",
    ]

    # Source x Year table
    all_years = sorted({y for years in by_sy.values() for y in years})
    lines.append("\U0001f4e1 Source \u00d7 Year")
    if all_years:
        header = "   {:20s}".format("Source") + "".join(f"{y:>7}" for y in all_years)
        lines.append(header)
        for source in sorted(by_sy.keys()):
            years = by_sy[source]
            row = "   {:20s}".format(source) + "".join(
                f"{years.get(y, 0):>7}" if years.get(y, 0) > 0 else "      \u2014"
                for y in all_years
            )
            lines.append(row)
    else:
        lines.append("   (no data)")
    lines.append("")

    # Company x Source table
    tickers = sorted(by_cs.keys(), key=lambda t: sum(by_cs[t].values()), reverse=True)
    if not full:
        tickers = tickers[:10]
    sources_with_data = [s for s in sorted(by_sy.keys()) if _sources_active({s: by_sy[s]})]
    if not sources_with_data:
        sources_with_data = sorted(by_sy.keys())[:3]

    lines.append(f"\U0001f3e2 Company \u00d7 Source (top {len(tickers)} by record count)")
    header = "   {:8s}".format("Ticker") + "".join(f"{s:>15}" for s in sources_with_data)
    lines.append(header)
    for ticker in tickers:
        src_data = by_cs[ticker]
        row = "   {:8s}".format(ticker) + "".join(
            f"{src_data.get(s, 0):>15}" if src_data.get(s, 0) > 0 else "              \u2014"
            for s in sources_with_data
        )
        lines.append(row)
    total_tickers = len(by_cs)
    if not full and total_tickers > 10:
        lines.append(f"   ({total_tickers} total \u2014 use --full to show all)")
    lines.append("")

    # Cross-validation
    lines.append("\U0001f500 Cross-Validation")
    lines.append(f"   Green: {cv_flags.get('green', 0)} | Yellow: {cv_flags.get('yellow', 0)} | Red: {cv_flags.get('red', 0)}")
    lines.append(f"   Coverage: {data['cv_coverage_pct']}% of company/year/scope tuples have \u22652 sources")
    lines.append("")

    # Alerts
    if alerts:
        lines.append("\U0001f6a8 Alerts")
        for a in alerts:
            icon = {"critical": "\U0001f534", "warning": "\u26a0\ufe0f", "info": "\u2139\ufe0f"}.get(a["severity"], "\u2022")
            lines.append(f"   {icon}  {a['message']}")
    else:
        lines.append("\u2705 No alerts")

    return "\n".join(lines)


def format_brief(data: dict) -> str:
    """Abbreviated post-ingest summary (summary + alert counts only)."""
    by_sy = data["by_source_year"]
    active = _sources_active(by_sy)
    total_sources = len(by_sy)
    alerts = data.get("alerts", [])

    alert_counts = {"critical": 0, "warning": 0, "info": 0}
    for a in alerts:
        alert_counts[a.get("severity", "info")] += 1

    lines = [
        "\U0001f4ca Coverage updated:",
        f"   Emissions: {data['total_emissions']} | Sources active: {active}/{total_sources} | CV coverage: {data['cv_coverage_pct']}%",
    ]

    total_alerts = sum(alert_counts.values())
    if total_alerts > 0:
        parts = []
        if alert_counts["critical"]:
            parts.append(f"{alert_counts['critical']} critical")
        if alert_counts["warning"]:
            parts.append(f"{alert_counts['warning']} warnings")
        if alert_counts["info"]:
            parts.append(f"{alert_counts['info']} info")
        lines.append(f"   \U0001f6a8 {', '.join(parts)} \u2014 run `pipeline coverage` for details")
    else:
        lines.append("   \u2705 No alerts")

    return "\n".join(lines)
