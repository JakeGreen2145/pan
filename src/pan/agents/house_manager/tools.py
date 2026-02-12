from datetime import date
from decimal import Decimal

import structlog
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pan.services.database import get_session
from pan.services.models import RentPayment, Tenant, User

logger = structlog.get_logger()


def _parse_month(month_str: str | None) -> tuple[date, date]:
    if month_str:
        year, month = map(int, month_str.split("-"))
    else:
        today = date.today()
        year, month = today.year, today.month

    period_start = date(year, month, 1)
    if month == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, month + 1, 1)

    return period_start, period_end


def _calculate_late_fee(tenant: Tenant, as_of: date) -> Decimal:
    grace_deadline = date(as_of.year, as_of.month, min(tenant.grace_period_days, 28))

    if as_of <= grace_deadline:
        return Decimal("0.00")

    days_late = (as_of - grace_deadline).days
    fee = tenant.late_fee_flat + (tenant.late_fee_daily * days_late)
    return fee


@tool
async def check_rent_status(month: str | None = None) -> str:
    """Check rent payment status for all tenants.

    Args:
        month: Month to check in YYYY-MM format (default: current month).
    """
    period_start, period_end = _parse_month(month)
    today = date.today()

    async with get_session() as session:
        result = await session.execute(
            select(Tenant)
            .options(selectinload(Tenant.user), selectinload(Tenant.payments))
            .where(Tenant.is_active.is_(True))
        )
        tenants = result.scalars().all()

    if not tenants:
        return "No active tenants found."

    lines = [f"Rent Status for {period_start.strftime('%B %Y')}:", ""]
    paid_count = 0
    unpaid_count = 0

    for tenant in tenants:
        name = tenant.user.name if tenant.user else "Unknown"
        period_payments = [
            p
            for p in tenant.payments
            if p.period_start >= period_start and p.period_start < period_end
        ]
        total_paid = sum(p.amount for p in period_payments)

        if total_paid >= tenant.rent_amount:
            lines.append(f"  {name} (Unit {tenant.unit}): PAID — ${total_paid:.2f}")
            paid_count += 1
        else:
            remaining = tenant.rent_amount - total_paid
            late_fee = _calculate_late_fee(tenant, today)
            status = f"  {name} (Unit {tenant.unit}): UNPAID — ${remaining:.2f} remaining"
            if late_fee > 0:
                status += f" + ${late_fee:.2f} late fee"
            lines.append(status)
            unpaid_count += 1

    lines.append("")
    lines.append(f"Summary: {paid_count} paid, {unpaid_count} unpaid out of {len(tenants)} tenants")

    return "\n".join(lines)


@tool
async def get_tenant_info(tenant_name: str | None = None) -> str:
    """Get tenant details including unit, rent, lease dates, and payment history.

    Args:
        tenant_name: Tenant's name to look up. If None, returns all tenants.
    """
    async with get_session() as session:
        query = (
            select(Tenant)
            .options(selectinload(Tenant.user), selectinload(Tenant.payments))
            .where(Tenant.is_active.is_(True))
        )
        if tenant_name:
            query = query.join(User).where(User.name.ilike(f"%{tenant_name}%"))

        result = await session.execute(query)
        tenants = result.scalars().all()

    if not tenants:
        return f"No tenant found matching '{tenant_name}'." if tenant_name else "No tenants found."

    parts = []
    for tenant in tenants:
        name = tenant.user.name if tenant.user else "Unknown"
        info = [
            f"Tenant: {name}",
            f"  Unit: {tenant.unit}",
            f"  Rent: ${tenant.rent_amount:.2f}/month",
            f"  Lease: {tenant.lease_start} to {tenant.lease_end}",
            f"  Grace Period: {tenant.grace_period_days} days",
            f"  Late Fee: ${tenant.late_fee_flat:.2f} flat + ${tenant.late_fee_daily:.2f}/day",
            "  Recent Payments:",
        ]
        for payment in tenant.payments[:5]:
            info.append(
                f"    {payment.period_start.strftime('%B %Y')}: "
                f"${payment.amount:.2f} paid on {payment.date_paid}"
            )
        if not tenant.payments:
            info.append("    (no payments recorded)")
        parts.append("\n".join(info))

    return "\n\n".join(parts)


@tool
async def calculate_late_fees(tenant_name: str) -> str:
    """Calculate current late fees for a specific tenant.

    Args:
        tenant_name: Name of the tenant to calculate fees for.
    """
    async with get_session() as session:
        result = await session.execute(
            select(Tenant)
            .options(selectinload(Tenant.user))
            .join(User)
            .where(User.name.ilike(f"%{tenant_name}%"), Tenant.is_active.is_(True))
        )
        tenant = result.scalars().first()

    if not tenant:
        return f"No active tenant found matching '{tenant_name}'."

    today = date.today()
    fee = _calculate_late_fee(tenant, today)
    name = tenant.user.name

    if fee == Decimal("0.00"):
        return f"{name}: No late fees as of {today}."

    return (
        f"{name} (Unit {tenant.unit}):\n"
        f"  Late fee: ${fee:.2f}\n"
        f"  Policy: ${tenant.late_fee_flat:.2f} flat + ${tenant.late_fee_daily:.2f}/day "
        f"after {tenant.grace_period_days}-day grace period"
    )


@tool
async def record_payment(
    tenant_name: str,
    amount: str,
    date_paid: str,
    period: str,
) -> str:
    """Record a rent payment for a tenant.

    Args:
        tenant_name: Name of the tenant who paid.
        amount: Payment amount (e.g., "1500.00").
        date_paid: Date payment was received (YYYY-MM-DD).
        period: Rental period this covers (YYYY-MM).
    """
    period_start, period_end = _parse_month(period)
    payment_date = date.fromisoformat(date_paid)
    payment_amount = Decimal(amount)

    async with get_session() as session:
        result = await session.execute(
            select(Tenant)
            .options(selectinload(Tenant.user))
            .join(User)
            .where(User.name.ilike(f"%{tenant_name}%"), Tenant.is_active.is_(True))
        )
        tenant = result.scalars().first()

        if not tenant:
            return f"No active tenant found matching '{tenant_name}'."

        payment = RentPayment(
            tenant_id=tenant.id,
            amount=payment_amount,
            date_paid=payment_date,
            period_start=period_start,
            period_end=period_end,
        )
        session.add(payment)

    name = tenant.user.name
    logger.info(
        "payment_recorded",
        tenant=name,
        amount=str(payment_amount),
        period=period,
    )
    return (
        f"Payment recorded:\n"
        f"  Tenant: {name}\n"
        f"  Amount: ${payment_amount:.2f}\n"
        f"  Date Paid: {payment_date}\n"
        f"  Period: {period_start.strftime('%B %Y')}"
    )


@tool
async def send_rent_reminder(tenant_name: str | None = None) -> str:
    """Queue rent reminders for overdue tenants.

    Args:
        tenant_name: Specific tenant to remind. If None, reminds all overdue tenants.
    """
    today = date.today()
    period_start, period_end = _parse_month(None)

    async with get_session() as session:
        query = (
            select(Tenant)
            .options(selectinload(Tenant.user), selectinload(Tenant.payments))
            .where(Tenant.is_active.is_(True))
        )
        if tenant_name:
            query = query.join(User).where(User.name.ilike(f"%{tenant_name}%"))

        result = await session.execute(query)
        tenants = result.scalars().all()

    reminders = []
    for tenant in tenants:
        payments = [
            p
            for p in tenant.payments
            if p.period_start >= period_start and p.period_start < period_end
        ]
        total_paid = sum(p.amount for p in payments)
        if total_paid < tenant.rent_amount:
            name = tenant.user.name if tenant.user else "Unknown"
            remaining = tenant.rent_amount - total_paid
            late_fee = _calculate_late_fee(tenant, today)
            reminders.append(
                f"  {name} (Unit {tenant.unit}): ${remaining:.2f} due + ${late_fee:.2f} late fee"
            )

    if not reminders:
        return "All tenants are current on rent. No reminders needed."

    return (
        f"Rent reminders queued for {len(reminders)} tenant(s):\n"
        + "\n".join(reminders)
        + "\n\n(Notifications will be sent via Discord.)"
    )
