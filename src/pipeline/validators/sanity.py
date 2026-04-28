"""Post-ingest plausibility check.

Halts the ingest workflow if any company-year emission exceeds a sanity
threshold. Catches future unit-conversion regressions or upstream-data
corruption.
"""
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.shared.models import Emission

# 10 Gt CO2e = ~25% of global annual emissions. Plausibility ceiling for a
# single corporate-year. Realistic max (Saudi Aramco) is ~4 Gt, so 10 Gt
# leaves comfortable margin while catching order-of-magnitude bugs.
SANITY_CEILING_TONNES = 10_000_000_000


class SanityCheckFailed(Exception):
    """Raised when a post-ingest sanity check finds an implausible value."""


def check_sanity(session: Session) -> None:
    """Scan all emissions and raise if any value exceeds the ceiling.

    Designed to be cheap (single aggregate query) and called after every
    ingest run via cli.py.
    """
    max_value = session.execute(
        select(func.max(Emission.value_t_co2e))
    ).scalar()

    if max_value is not None and max_value > SANITY_CEILING_TONNES:
        # Find the offending row(s) for the error message
        offenders = session.execute(
            select(Emission.company_id, Emission.year, Emission.value_t_co2e)
            .where(Emission.value_t_co2e > SANITY_CEILING_TONNES)
            .limit(5)
        ).all()
        details = ", ".join(
            f"company={c}, year={y}, value={v:.0f}t" for c, y, v in offenders
        )
        raise SanityCheckFailed(
            f"Post-ingest sanity check failed: {len(offenders)}+ row(s) "
            f"exceed {SANITY_CEILING_TONNES:,} tonnes ceiling. "
            f"Likely cause: unit-conversion regression. Offenders: {details}"
        )
