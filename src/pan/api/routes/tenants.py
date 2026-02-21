import uuid
from datetime import date
from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pan.services.database import get_session
from pan.services.models import Tenant, User, UserRole

logger = structlog.get_logger()
router = APIRouter()


class TenantCreateRequest(BaseModel):
    name: str
    unit: str
    rent_amount: float
    lease_start: str
    lease_end: str
    late_fee_flat: float = 0
    late_fee_daily: float = 0
    grace_period_days: int = 5
    discord_id: int | None = None


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    unit: str | None = None
    rent_amount: float | None = None
    lease_start: str | None = None
    lease_end: str | None = None
    late_fee_flat: float | None = None
    late_fee_daily: float | None = None
    grace_period_days: int | None = None
    discord_id: int | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    id: str
    name: str
    unit: str
    rent_amount: float
    lease_start: str
    lease_end: str
    late_fee_flat: float
    late_fee_daily: float
    grace_period_days: int
    is_active: bool
    discord_id: int | None


def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.user.name,
        unit=tenant.unit,
        rent_amount=float(tenant.rent_amount),
        lease_start=tenant.lease_start.isoformat(),
        lease_end=tenant.lease_end.isoformat(),
        late_fee_flat=float(tenant.late_fee_flat),
        late_fee_daily=float(tenant.late_fee_daily),
        grace_period_days=tenant.grace_period_days,
        is_active=tenant.is_active,
        discord_id=tenant.user.discord_id,
    )


@router.get("")
async def list_tenants() -> list[TenantResponse]:
    async with get_session() as session:
        result = await session.execute(
            select(Tenant).options(joinedload(Tenant.user)).order_by(Tenant.unit)
        )
        tenants = result.scalars().unique().all()

    return [_tenant_to_response(t) for t in tenants]


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str) -> TenantResponse:
    tenant_uuid = _parse_uuid(tenant_id)
    async with get_session() as session:
        result = await session.execute(
            select(Tenant).options(joinedload(Tenant.user)).where(Tenant.id == tenant_uuid)
        )
        tenant = result.scalars().first()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return _tenant_to_response(tenant)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tenant(body: TenantCreateRequest) -> TenantResponse:
    async with get_session() as session:
        user = User(
            name=body.name,
            discord_id=body.discord_id,
            role=UserRole.TENANT,
        )
        session.add(user)
        await session.flush()

        tenant = Tenant(
            user_id=user.id,
            unit=body.unit,
            rent_amount=Decimal(str(body.rent_amount)),
            lease_start=date.fromisoformat(body.lease_start),
            lease_end=date.fromisoformat(body.lease_end),
            late_fee_flat=Decimal(str(body.late_fee_flat)),
            late_fee_daily=Decimal(str(body.late_fee_daily)),
            grace_period_days=body.grace_period_days,
        )
        session.add(tenant)
        await session.flush()

        result = await session.execute(
            select(Tenant).options(joinedload(Tenant.user)).where(Tenant.id == tenant.id)
        )
        tenant = result.scalars().first()

        logger.info("tenant_created", tenant_id=str(tenant.id), name=body.name, unit=body.unit)

    return _tenant_to_response(tenant)  # type: ignore[arg-type]


@router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, body: TenantUpdateRequest) -> TenantResponse:
    tenant_uuid = _parse_uuid(tenant_id)
    async with get_session() as session:
        result = await session.execute(
            select(Tenant).options(joinedload(Tenant.user)).where(Tenant.id == tenant_uuid)
        )
        tenant = result.scalars().first()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        if body.name is not None:
            tenant.user.name = body.name
        if body.discord_id is not None:
            tenant.user.discord_id = body.discord_id
        if body.unit is not None:
            tenant.unit = body.unit
        if body.rent_amount is not None:
            tenant.rent_amount = Decimal(str(body.rent_amount))
        if body.lease_start is not None:
            tenant.lease_start = date.fromisoformat(body.lease_start)
        if body.lease_end is not None:
            tenant.lease_end = date.fromisoformat(body.lease_end)
        if body.late_fee_flat is not None:
            tenant.late_fee_flat = Decimal(str(body.late_fee_flat))
        if body.late_fee_daily is not None:
            tenant.late_fee_daily = Decimal(str(body.late_fee_daily))
        if body.grace_period_days is not None:
            tenant.grace_period_days = body.grace_period_days
        if body.is_active is not None:
            tenant.is_active = body.is_active

        logger.info("tenant_updated", tenant_id=tenant_id)

    return _tenant_to_response(tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: str) -> None:
    tenant_uuid = _parse_uuid(tenant_id)
    async with get_session() as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_uuid))
        tenant = result.scalars().first()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        tenant.is_active = False
        logger.info("tenant_deactivated", tenant_id=tenant_id)


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from err
