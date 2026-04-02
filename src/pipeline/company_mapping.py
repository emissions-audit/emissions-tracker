"""Shared utility to resolve facility/installation owner names to stock tickers.

Both EPA GHGRP and EU ETS report at facility level without parent company
tickers.  This module provides the mapping via a static lookup table with
normalized-matching fallback.
"""

import re

# ---------------------------------------------------------------------------
# Static lookup: facility owner name  →  ticker
# Keys are stored in their canonical forms; matching is attempted first
# verbatim, then via normalised form.
# ---------------------------------------------------------------------------

FACILITY_OWNER_TO_TICKER: dict[str, str] = {
    # Integrated majors
    "ExxonMobil": "XOM",
    "Exxon Mobil Corporation": "XOM",
    "Chevron": "CVX",
    "Chevron Corporation": "CVX",
    "Chevron U.S.A. Inc.": "CVX",
    "Shell": "SHEL",
    "Shell plc": "SHEL",
    "Shell Oil Company": "SHEL",
    "Royal Dutch Shell": "SHEL",
    "BP": "BP",
    "BP plc": "BP",
    "BP America": "BP",
    "BP Products North America": "BP",
    "TotalEnergies": "TTE",
    "TotalEnergies SE": "TTE",
    "ConocoPhillips": "COP",
    "ConocoPhillips Company": "COP",
    "Eni": "ENI",
    "Eni S.p.A.": "ENI",
    "Equinor": "EQNR",
    "Equinor ASA": "EQNR",
    "Statoil": "EQNR",
    # E&P
    "Occidental": "OXY",
    "Occidental Petroleum": "OXY",
    "Occidental Petroleum Corporation": "OXY",
    "Devon Energy": "DVN",
    "Devon Energy Corporation": "DVN",
    "Hess": "HES",
    "Hess Corporation": "HES",
    "Marathon Oil": "MRO",
    "Marathon Oil Corporation": "MRO",
    "EOG Resources": "EOG",
    "EOG Resources Inc.": "EOG",
    "Diamondback Energy": "FANG",
    "Diamondback Energy Inc.": "FANG",
    # Refining
    "Marathon Petroleum": "MPC",
    "Marathon Petroleum Corporation": "MPC",
    "Phillips 66": "PSX",
    "Phillips 66 Company": "PSX",
    "Valero": "VLO",
    "Valero Energy": "VLO",
    "Valero Energy Corporation": "VLO",
    # Oilfield services
    "SLB": "SLB",
    "Schlumberger": "SLB",
    "SLB (Schlumberger)": "SLB",
    "Baker Hughes": "BKR",
    "Baker Hughes Company": "BKR",
    "Halliburton": "HAL",
    "Halliburton Company": "HAL",
}

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_SUFFIX_PATTERN = re.compile(
    r"\b("
    r"corporation|company|inc\.?|plc|s\.p\.a\.?|se|asa|ltd|limited|llc|lp"
    r")\s*$",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    """Lowercase, strip whitespace, remove common corporate suffixes."""
    cleaned = name.lower().strip()
    # Iteratively strip suffixes (a name might end with e.g. "Inc." then still
    # have trailing whitespace or another suffix).
    for _ in range(3):
        cleaned_next = _SUFFIX_PATTERN.sub("", cleaned).strip().rstrip(",").strip()
        if cleaned_next == cleaned:
            break
        cleaned = cleaned_next
    return cleaned


# Pre-build a normalised lookup for the fallback path.
_NORMALISED_LOOKUP: dict[str, str] = {}
for _name, _ticker in FACILITY_OWNER_TO_TICKER.items():
    norm = _normalize(_name)
    # First mapping wins (keeps canonical short forms preferred).
    if norm not in _NORMALISED_LOOKUP:
        _NORMALISED_LOOKUP[norm] = _ticker


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_ticker(facility_name: str) -> str | None:
    """Resolve a facility owner name to a stock ticker.

    Tries exact match first, then normalised (case-insensitive, suffix-stripped)
    match.  Returns ``None`` for truly unknown facilities.
    """
    # 1. Exact match
    ticker = FACILITY_OWNER_TO_TICKER.get(facility_name)
    if ticker is not None:
        return ticker

    # 2. Normalised fallback
    return _NORMALISED_LOOKUP.get(_normalize(facility_name))


def get_all_tickers() -> list[str]:
    """Return a deduplicated list of all known tickers (stable order)."""
    seen: set[str] = set()
    result: list[str] = []
    for ticker in FACILITY_OWNER_TO_TICKER.values():
        if ticker not in seen:
            seen.add(ticker)
            result.append(ticker)
    return result
