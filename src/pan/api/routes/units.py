from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from pan.services.database import get_session
from pan.services.models import Tenant

logger = structlog.get_logger()
router = APIRouter()


class UnitResponse(BaseModel):
    unit: str
    rent_amount: float
    tenant_count: int


class UnitUpdateRequest(BaseModel):
    rent_amount: float
    late_fee_flat: float | None = None
    late_fee_daily: float | None = None
    grace_period_days: int | None = None


@router.get("")
async def list_units() -> list[UnitResponse]:
    async with get_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.is_active.is_(True)).order_by(Tenant.unit)
        )
        tenants = result.scalars().all()

    units: dict[str, UnitResponse] = {}
    for t in tenants:
        if t.unit in units:
            units[t.unit].tenant_count += 1
        else:
            units[t.unit] = UnitResponse(
                unit=t.unit,
                rent_amount=float(t.rent_amount),
                tenant_count=1,
            )

    return list(units.values())


@router.put("/{unit_name}")
async def update_unit(unit_name: str, body: UnitUpdateRequest) -> UnitResponse:
    async with get_session() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.unit == unit_name, Tenant.is_active.is_(True))
        )
        tenants = result.scalars().all()

        if not tenants:
            raise HTTPException(status_code=404, detail=f"No active tenants in unit '{unit_name}'")

        for t in tenants:
            t.rent_amount = Decimal(str(body.rent_amount))
            if body.late_fee_flat is not None:
                t.late_fee_flat = Decimal(str(body.late_fee_flat))
            if body.late_fee_daily is not None:
                t.late_fee_daily = Decimal(str(body.late_fee_daily))
            if body.grace_period_days is not None:
                t.grace_period_days = body.grace_period_days

        logger.info("unit_updated", unit=unit_name, tenant_count=len(tenants))

    return UnitResponse(
        unit=unit_name,
        rent_amount=body.rent_amount,
        tenant_count=len(tenants),
    )
