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
    # --- Oil & Gas: Integrated majors ---
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
    # --- Oil & Gas: E&P ---
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
    "Pioneer Natural Resources": "PXD",
    "Pioneer Natural Resources Company": "PXD",
    "Coterra Energy": "CTRA",
    "Coterra Energy Inc.": "CTRA",
    "Cabot Oil & Gas": "CTRA",
    # --- Oil & Gas: Refining ---
    "Marathon Petroleum": "MPC",
    "Marathon Petroleum Corporation": "MPC",
    "Phillips 66": "PSX",
    "Phillips 66 Company": "PSX",
    "Valero": "VLO",
    "Valero Energy": "VLO",
    "Valero Energy Corporation": "VLO",
    # --- Oilfield services ---
    "SLB": "SLB",
    "Schlumberger": "SLB",
    "SLB (Schlumberger)": "SLB",
    "Baker Hughes": "BKR",
    "Baker Hughes Company": "BKR",
    "Halliburton": "HAL",
    "Halliburton Company": "HAL",
    # --- Utilities / Power generation ---
    "Duke Energy": "DUK",
    "Duke Energy Corporation": "DUK",
    "Duke Energy Indiana": "DUK",
    "Duke Energy Carolinas": "DUK",
    "Duke Energy Florida": "DUK",
    "Duke Energy Progress": "DUK",
    "Southern Company": "SO",
    "Southern Company Services": "SO",
    "Georgia Power Company": "SO",
    "Alabama Power Company": "SO",
    "Mississippi Power Company": "SO",
    "NextEra Energy": "NEE",
    "Florida Power & Light": "NEE",
    "Florida Power & Light Company": "NEE",
    "American Electric Power": "AEP",
    "American Electric Power Company": "AEP",
    "AEP Generation Resources": "AEP",
    "Appalachian Power Company": "AEP",
    "Dominion Energy": "D",
    "Dominion Energy Virginia": "D",
    "Virginia Electric and Power": "D",
    "Xcel Energy": "XEL",
    "Xcel Energy Inc.": "XEL",
    "Northern States Power": "XEL",
    "Southwestern Public Service": "XEL",
    "WEC Energy Group": "WEC",
    "Wisconsin Electric Power": "WEC",
    "Wisconsin Electric Power Company": "WEC",
    "Edison International": "EIX",
    "Southern California Edison": "EIX",
    "Southern California Edison Company": "EIX",
    "Entergy": "ETR",
    "Entergy Corporation": "ETR",
    "Entergy Louisiana": "ETR",
    "Entergy Texas": "ETR",
    "Entergy Arkansas": "ETR",
    "AES Corporation": "AES",
    "AES Indiana": "AES",
    "AES Ohio": "AES",
    "Indianapolis Power & Light": "AES",
    "Evergy": "EVRG",
    "Evergy Inc.": "EVRG",
    "Evergy Kansas Central": "EVRG",
    "Evergy Metro": "EVRG",
    "NRG Energy": "NRG",
    "NRG Energy Inc.": "NRG",
    "Vistra": "VST",
    "Vistra Corp": "VST",
    "Luminant": "VST",
    "TXU Energy": "VST",
    # --- Materials: Cement & Aggregates ---
    "Vulcan Materials": "VMC",
    "Vulcan Materials Company": "VMC",
    "Martin Marietta Materials": "MLM",
    "Martin Marietta Materials Inc.": "MLM",
    # --- Materials: Steel ---
    "Nucor": "NUE",
    "Nucor Corporation": "NUE",
    "Steel Dynamics": "STLD",
    "Steel Dynamics Inc.": "STLD",
    "Cleveland-Cliffs": "CLF",
    "Cleveland-Cliffs Inc.": "CLF",
    "ArcelorMittal USA": "CLF",
    "United States Steel": "X",
    "United States Steel Corporation": "X",
    "U.S. Steel": "X",
    # --- Chemicals ---
    "Dow": "DOW",
    "Dow Inc.": "DOW",
    "Dow Chemical": "DOW",
    "Dow Chemical Company": "DOW",
    "LyondellBasell": "LYB",
    "LyondellBasell Industries": "LYB",
    "Celanese": "CE",
    "Celanese Corporation": "CE",
    "CF Industries": "CF",
    "CF Industries Holdings": "CF",
    "Mosaic": "MOS",
    "Mosaic Company": "MOS",
    "The Mosaic Company": "MOS",
    # --- Mining ---
    "Freeport-McMoRan": "FCX",
    "Freeport-McMoRan Inc.": "FCX",
    "Newmont": "NEM",
    "Newmont Corporation": "NEM",
    "Newmont Mining": "NEM",
    "Alcoa": "AA",
    "Alcoa Corporation": "AA",
    # --- Airlines ---
    "Delta Air Lines": "DAL",
    "Delta Air Lines Inc.": "DAL",
    "United Airlines": "UAL",
    "United Airlines Holdings": "UAL",
    "American Airlines": "AAL",
    "American Airlines Group": "AAL",
    # --- EU subsidiaries (for EU ETS installation matching) ---
    "Shell Deutschland": "SHEL",
    "Shell Deutschland Oil": "SHEL",
    "Shell Deutschland Oil GmbH": "SHEL",
    "BP Europa": "BP",
    "BP Europa SE": "BP",
    "BP Gelsenkirchen": "BP",
    "TotalEnergies Raffinage": "TTE",
    "TotalEnergies Raffinage France": "TTE",
    "Eni Deutschland": "ENI",
    "ExxonMobil Production Deutschland": "XOM",
    "ExxonMobil Central Europe Holding": "XOM",
    "Equinor Refining Denmark": "EQNR",
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
