import json
from pathlib import Path
from typing import Any

CORRECTIONS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "corrections" / "corrections.json"
)

_cache: list[dict[str, Any]] | None = None


def _load_from_disk() -> list[dict[str, Any]]:
    if not CORRECTIONS_PATH.exists():
        return []
    try:
        with open(CORRECTIONS_PATH) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def get_corrections() -> list[dict[str, Any]]:
    global _cache
    if _cache is None:
        _cache = _load_from_disk()
    return _cache


def clear_cache() -> None:
    global _cache
    _cache = None


def _match(c: dict[str, Any], ticker: str, year: int, scope: str) -> bool:
    return (
        c.get("company_ticker") == ticker
        and c.get("year") == year
        and c.get("scope") == scope
    )


def apply_value(
    field: str,
    current: Any,
    ticker: str | None,
    year: int,
    scope: str,
    corrections: list[dict[str, Any]] | None = None,
) -> Any:
    if not ticker:
        return current
    pool = corrections if corrections is not None else get_corrections()
    for c in pool:
        if _match(c, ticker, year, scope) and c.get("field") == field:
            return c["new_value"]
    return current


def build_provenance(
    ticker: str | None,
    year: int,
    scope: str,
    corrections: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not ticker:
        return None
    pool = corrections if corrections is not None else get_corrections()
    matching = [c for c in pool if _match(c, ticker, year, scope)]
    if not matching:
        return None
    contributors = sorted({c["contributor"] for c in matching})
    return {
        "contributors": contributors,
        "corrections": [
            {
                "field": c["field"],
                "old_value": c["old_value"],
                "new_value": c["new_value"],
                "source_url": c["source_url"],
                "contributor": c["contributor"],
                "accepted_date": c["accepted_date"],
            }
            for c in matching
        ],
    }
