import uuid
from collections import defaultdict


def compute_flag(spread_pct: float) -> str:
    if spread_pct < 10.0:
        return "green"
    elif spread_pct < 30.0:
        return "yellow"
    else:
        return "red"


def compute_cross_validations(
    emissions: list[dict],
    source_types: dict[uuid.UUID, str],
) -> list[dict]:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for e in emissions:
        key = (e["company_id"], e["year"], e["scope"])
        grouped[key].append(e)

    results = []
    for (company_id, year, scope), group in grouped.items():
        if len(group) < 2:
            continue

        values = [e["value_t_co2e"] for e in group]
        min_val = min(values)
        max_val = max(values)
        spread_pct = round((max_val - min_val) / min_val * 100, 2) if min_val > 0 else 0.0

        entries = []
        for e in group:
            source_id = e.get("source_id")
            entries.append({
                "source_type": source_types.get(source_id, "unknown"),
                "value_t_co2e": e["value_t_co2e"],
                "filing_id": source_id,
            })

        results.append({
            "company_id": company_id,
            "year": year,
            "scope": scope,
            "source_count": len(group),
            "min_value": min_val,
            "max_value": max_val,
            "spread_pct": spread_pct,
            "flag": compute_flag(spread_pct),
            "entries": entries,
        })

    return results
