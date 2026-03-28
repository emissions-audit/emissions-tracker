import re

UNIT_MULTIPLIERS = {
    "mt_co2e": 1.0,
    "kt_co2e": 1_000.0,
    "t_co2e": 0.001,
    "metric_tons_co2e": 0.001,
}

SCOPE_MAP = {
    "scope 1": "1",
    "scope 2": "2",
    "scope 3": "3",
    "scope 1+2": "1+2",
    "scope 1 + 2": "1+2",
    "total": "total",
    "1": "1",
    "2": "2",
    "3": "3",
    "1+2": "1+2",
}


def normalize_value(value: float, unit: str) -> float:
    unit_lower = unit.lower().strip()
    if unit_lower not in UNIT_MULTIPLIERS:
        raise ValueError(f"Unknown unit: {unit}")
    return value * UNIT_MULTIPLIERS[unit_lower]


def normalize_scope(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", raw.strip().lower())
    if cleaned in SCOPE_MAP:
        return SCOPE_MAP[cleaned]
    raise ValueError(f"Unknown scope: {raw}")
