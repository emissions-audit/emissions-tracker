import uuid
import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Pledge, Emission, Company
from src.shared.schemas import PledgeResponse, PledgeTrackerRow


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["pledges"])

    @router.get("/v1/companies/{company_id}/pledges", response_model=list[PledgeResponse])
    async def company_pledges(company_id: uuid.UUID, db: AsyncSession = get_db):
        result = await db.execute(select(Pledge).where(Pledge.company_id == company_id))
        pledges = result.scalars().all()
        return [PledgeResponse.model_validate(p) for p in pledges]

    @router.get("/v1/pledges/tracker", response_model=list[PledgeTrackerRow])
    async def pledge_tracker(db: AsyncSession = get_db):
        stmt = select(Pledge, Company.name).join(Company, Pledge.company_id == Company.id)
        pledge_rows = (await db.execute(stmt)).all()
        results = []
        for pledge, company_name in pledge_rows:
            latest_stmt = (
                select(Emission)
                .where(Emission.company_id == pledge.company_id)
                .where(Emission.scope.in_(["1", "total"]))
                .order_by(Emission.year.desc())
                .limit(1)
            )
            latest = (await db.execute(latest_stmt)).scalars().first()
            latest_value = float(latest.value_t_co2e) if latest else None
            baseline = float(pledge.baseline_value_t_co2e) if pledge.baseline_value_t_co2e else None
            actual_reduction = None
            on_track = None
            if baseline and latest_value and baseline > 0:
                actual_reduction = round((1 - latest_value / baseline) * 100, 2)
                if pledge.target_reduction_pct:
                    now_year = datetime.date.today().year
                    if pledge.target_year and pledge.baseline_year:
                        total_years = pledge.target_year - pledge.baseline_year
                        elapsed = now_year - pledge.baseline_year
                        if total_years > 0:
                            expected = (elapsed / total_years) * float(pledge.target_reduction_pct)
                            on_track = actual_reduction >= expected
            results.append(
                PledgeTrackerRow(
                    company_id=pledge.company_id,
                    company_name=company_name,
                    pledge_type=pledge.pledge_type,
                    target_year=pledge.target_year,
                    target_reduction_pct=float(pledge.target_reduction_pct) if pledge.target_reduction_pct else None,
                    baseline_value=baseline,
                    latest_value=latest_value,
                    actual_reduction_pct=actual_reduction,
                    on_track=on_track,
                )
            )
        return results

    return router
