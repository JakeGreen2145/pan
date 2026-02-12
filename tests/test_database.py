from datetime import date
from decimal import Decimal

from sqlalchemy import select

from pan.services.models import (
    ApprovalRequest,
    ApprovalStatus,
    RentPayment,
    Tenant,
    User,
    UserRole,
)


async def test_create_user(async_session):
    user = User(name="Jake", discord_id=123456789, role=UserRole.OWNER)
    async_session.add(user)
    await async_session.flush()

    result = await async_session.execute(select(User).where(User.name == "Jake"))
    fetched = result.scalar_one()
    assert fetched.role == UserRole.OWNER
    assert fetched.discord_id == 123456789


async def test_tenant_with_payment(async_session):
    user = User(name="Tenant A", role=UserRole.TENANT)
    async_session.add(user)
    await async_session.flush()

    tenant = Tenant(
        user_id=user.id,
        unit="1A",
        rent_amount=Decimal("1500.00"),
        lease_start=date(2025, 1, 1),
        lease_end=date(2026, 1, 1),
    )
    async_session.add(tenant)
    await async_session.flush()

    payment = RentPayment(
        tenant_id=tenant.id,
        amount=Decimal("1500.00"),
        date_paid=date(2025, 6, 1),
        period_start=date(2025, 6, 1),
        period_end=date(2025, 7, 1),
    )
    async_session.add(payment)
    await async_session.flush()

    result = await async_session.execute(
        select(RentPayment).where(RentPayment.tenant_id == tenant.id)
    )
    fetched = result.scalar_one()
    assert fetched.amount == Decimal("1500.00")


async def test_approval_request(async_session):
    approval = ApprovalRequest(
        agent_domain="tech_chair",
        action_type="restart_container",
        description="Restart nginx-proxy",
        payload={"container_id": "abc123"},
        status=ApprovalStatus.PENDING,
    )
    async_session.add(approval)
    await async_session.flush()

    result = await async_session.execute(
        select(ApprovalRequest).where(ApprovalRequest.status == ApprovalStatus.PENDING)
    )
    fetched = result.scalar_one()
    assert fetched.agent_domain == "tech_chair"
    assert fetched.payload["container_id"] == "abc123"
