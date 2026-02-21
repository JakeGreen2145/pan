import uuid
from datetime import date
from decimal import Decimal

import structlog
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pan.services.database import get_session
from pan.services.models import (
    BankTransaction,
    MatchStatus,
    RentPayment,
    Tenant,
)

logger = structlog.get_logger()

MATCH_THRESHOLD = 90
PARTIAL_THRESHOLD = 70


async def match_transaction(
    txn: BankTransaction,
) -> tuple[MatchStatus, uuid.UUID | None, int]:
    if not txn.parsed_sender_name:
        return MatchStatus.UNMATCHED, None, 0

    async with get_session() as session:
        result = await session.execute(
            select(Tenant).options(selectinload(Tenant.user)).where(Tenant.is_active.is_(True))
        )
        tenants = result.scalars().all()

    if not tenants:
        return MatchStatus.UNMATCHED, None, 0

    best_status = MatchStatus.UNMATCHED
    best_tenant_id: uuid.UUID | None = None
    best_score = 0

    for tenant in tenants:
        if not tenant.user:
            continue
        score = fuzz.token_sort_ratio(txn.parsed_sender_name, tenant.user.name)
        if score > best_score:
            best_score = int(score)
            best_tenant_id = tenant.id
            if best_score >= MATCH_THRESHOLD:
                best_status = MatchStatus.MATCHED
            elif best_score >= PARTIAL_THRESHOLD:
                best_status = MatchStatus.PARTIAL
            else:
                best_status = MatchStatus.UNMATCHED

    logger.info(
        "transaction_matched",
        txn_id=str(txn.id),
        sender=txn.parsed_sender_name,
        status=best_status,
        confidence=best_score,
    )
    return best_status, best_tenant_id, best_score


async def match_unmatched_transactions() -> dict[str, int]:
    counts = {"matched": 0, "partial": 0, "unmatched": 0}

    async with get_session() as session:
        result = await session.execute(
            select(BankTransaction).where(
                BankTransaction.is_zelle.is_(True),
                BankTransaction.match_status == MatchStatus.UNMATCHED,
            )
        )
        transactions = result.scalars().all()

    for txn in transactions:
        status, tenant_id, confidence = await match_transaction(txn)

        async with get_session() as session:
            result = await session.execute(
                select(BankTransaction).where(BankTransaction.id == txn.id)
            )
            db_txn = result.scalars().first()
            if db_txn:
                db_txn.match_status = status
                db_txn.matched_tenant_id = tenant_id
                db_txn.match_confidence = confidence

        match status:
            case MatchStatus.MATCHED:
                counts["matched"] += 1
            case MatchStatus.PARTIAL:
                counts["partial"] += 1
            case _:
                counts["unmatched"] += 1

    logger.info("batch_matching_complete", **counts)
    return counts


async def reconcile_payment(txn_id: uuid.UUID, tenant_id: uuid.UUID) -> RentPayment:
    async with get_session() as session:
        txn_result = await session.execute(
            select(BankTransaction).where(BankTransaction.id == txn_id)
        )
        txn = txn_result.scalars().first()
        if not txn:
            raise ValueError(f"Transaction {txn_id} not found")

        tenant_result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalars().first()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        period_start = date(txn.date.year, txn.date.month, 1)
        if txn.date.month == 12:
            period_end = date(txn.date.year + 1, 1, 1)
        else:
            period_end = date(txn.date.year, txn.date.month + 1, 1)

        payment = RentPayment(
            tenant_id=tenant_id,
            amount=txn.amount,
            date_paid=txn.date,
            period_start=period_start,
            period_end=period_end,
            notes=f"Auto-reconciled from Zelle: {txn.name}",
        )
        session.add(payment)
        await session.flush()

        is_manual = txn.match_status in (MatchStatus.UNMATCHED, MatchStatus.PARTIAL)
        txn.matched_tenant_id = tenant_id
        txn.match_status = MatchStatus.MANUAL if is_manual else MatchStatus.MATCHED
        txn.rent_payment_id = payment.id

    logger.info(
        "payment_reconciled",
        txn_id=str(txn_id),
        tenant_id=str(tenant_id),
        amount=str(txn.amount),
        period=period_start.isoformat(),
    )
    return payment


async def get_reconciliation_summary(month: str | None = None) -> dict:
    today = date.today()
    if month:
        year, mon = map(int, month.split("-"))
    else:
        year, mon = today.year, today.month

    period_start = date(year, mon, 1)
    if mon == 12:
        period_end = date(year + 1, 1, 1)
    else:
        period_end = date(year, mon + 1, 1)

    async with get_session() as session:
        tenant_result = await session.execute(
            select(Tenant)
            .options(selectinload(Tenant.user), selectinload(Tenant.payments))
            .where(Tenant.is_active.is_(True))
        )
        tenants = tenant_result.scalars().all()

        unmatched_result = await session.execute(
            select(BankTransaction).where(
                BankTransaction.is_zelle.is_(True),
                BankTransaction.match_status == MatchStatus.UNMATCHED,
                BankTransaction.date >= period_start,
                BankTransaction.date < period_end,
            )
        )
        unmatched_txns = unmatched_result.scalars().all()

    total_expected = Decimal("0")
    total_received = Decimal("0")
    tenant_breakdown = []

    for tenant in tenants:
        total_expected += tenant.rent_amount

        period_payments = [
            p
            for p in tenant.payments
            if p.period_start >= period_start and p.period_start < period_end
        ]
        paid = sum((p.amount for p in period_payments), Decimal("0"))
        total_received += paid

        tenant_name = tenant.user.name if tenant.user else "Unknown"
        tenant_breakdown.append(
            {
                "tenant_id": str(tenant.id),
                "name": tenant_name,
                "unit": tenant.unit,
                "rent_amount": str(tenant.rent_amount),
                "paid": str(paid),
                "remaining": str(tenant.rent_amount - paid),
                "status": "paid" if paid >= tenant.rent_amount else "unpaid",
            }
        )

    unmatched_list = [
        {
            "txn_id": str(txn.id),
            "amount": str(txn.amount),
            "date": txn.date.isoformat(),
            "name": txn.name,
            "parsed_sender": txn.parsed_sender_name,
        }
        for txn in unmatched_txns
    ]

    return {
        "month": f"{year:04d}-{mon:02d}",
        "total_expected": str(total_expected),
        "total_received": str(total_received),
        "outstanding": str(total_expected - total_received),
        "tenants": tenant_breakdown,
        "unmatched_transactions": unmatched_list,
    }
