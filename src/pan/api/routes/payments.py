import uuid
from datetime import date

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from pan.services.database import get_session
from pan.services.models import BankTransaction, MatchStatus, RentPayment, Tenant
from pan.services.payment_matcher import (
    get_reconciliation_summary,
    match_unmatched_transactions,
)
from pan.services.plaid_service import sync_all_items

logger = structlog.get_logger()
router = APIRouter()


class TransactionResponse(BaseModel):
    id: str
    plaid_transaction_id: str
    amount: float
    date: str
    name: str
    original_description: str | None
    payment_channel: str | None
    is_zelle: bool
    parsed_sender_name: str | None
    matched_tenant_id: str | None
    match_status: str
    match_confidence: int
    rent_payment_id: str | None
    created_at: str


class ManualMatchRequest(BaseModel):
    tenant_id: str


class ReconciliationSummary(BaseModel):
    month: str
    total_expected: float
    total_received: float
    outstanding: float
    tenants: list[dict]


def _txn_to_response(txn: BankTransaction) -> TransactionResponse:
    return TransactionResponse(
        id=str(txn.id),
        plaid_transaction_id=txn.plaid_transaction_id,
        amount=float(txn.amount),
        date=txn.date.isoformat(),
        name=txn.name,
        original_description=txn.original_description,
        payment_channel=txn.payment_channel,
        is_zelle=txn.is_zelle,
        parsed_sender_name=txn.parsed_sender_name,
        matched_tenant_id=str(txn.matched_tenant_id) if txn.matched_tenant_id else None,
        match_status=txn.match_status.value,
        match_confidence=txn.match_confidence,
        rent_payment_id=str(txn.rent_payment_id) if txn.rent_payment_id else None,
        created_at=txn.created_at.isoformat(),
    )


@router.get("/transactions")
async def list_transactions(
    match_status: str | None = Query(None),
    is_zelle: bool | None = Query(None),
    month: str | None = Query(None, description="YYYY-MM format"),
) -> list[TransactionResponse]:
    async with get_session() as session:
        stmt = select(BankTransaction).order_by(BankTransaction.date.desc())

        if match_status is not None:
            stmt = stmt.where(BankTransaction.match_status == MatchStatus(match_status))
        if is_zelle is not None:
            stmt = stmt.where(BankTransaction.is_zelle == is_zelle)
        if month is not None:
            year, mon = month.split("-")
            start = date(int(year), int(mon), 1)
            if int(mon) == 12:
                end = date(int(year) + 1, 1, 1)
            else:
                end = date(int(year), int(mon) + 1, 1)
            stmt = stmt.where(BankTransaction.date >= start, BankTransaction.date < end)

        result = await session.execute(stmt)
        transactions = result.scalars().all()

    return [_txn_to_response(t) for t in transactions]


@router.get("/transactions/{txn_id}")
async def get_transaction(txn_id: str) -> TransactionResponse:
    txn_uuid = _parse_uuid(txn_id)
    async with get_session() as session:
        result = await session.execute(
            select(BankTransaction).where(BankTransaction.id == txn_uuid)
        )
        txn = result.scalars().first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return _txn_to_response(txn)


@router.post("/transactions/{txn_id}/match")
async def manual_match_transaction(txn_id: str, body: ManualMatchRequest) -> TransactionResponse:
    txn_uuid = _parse_uuid(txn_id)
    tenant_uuid = _parse_uuid(body.tenant_id)

    async with get_session() as session:
        result = await session.execute(
            select(BankTransaction).where(BankTransaction.id == txn_uuid)
        )
        txn = result.scalars().first()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        result = await session.execute(select(Tenant).where(Tenant.id == tenant_uuid))
        tenant = result.scalars().first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        payment = RentPayment(
            tenant_id=tenant.id,
            amount=txn.amount,
            date_paid=txn.date,
            period_start=txn.date.replace(day=1),
            period_end=txn.date,
            notes=f"Manual match from transaction {txn.plaid_transaction_id}",
        )
        session.add(payment)
        await session.flush()

        txn.matched_tenant_id = tenant.id
        txn.match_status = MatchStatus.MANUAL
        txn.match_confidence = 100
        txn.rent_payment_id = payment.id

        logger.info(
            "transaction_manually_matched",
            txn_id=txn_id,
            tenant_id=body.tenant_id,
        )

    return _txn_to_response(txn)


@router.post("/transactions/{txn_id}/ignore")
async def ignore_transaction(txn_id: str) -> TransactionResponse:
    txn_uuid = _parse_uuid(txn_id)
    async with get_session() as session:
        result = await session.execute(
            select(BankTransaction).where(BankTransaction.id == txn_uuid)
        )
        txn = result.scalars().first()
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        txn.match_status = MatchStatus.IGNORED
        logger.info("transaction_ignored", txn_id=txn_id)

    return _txn_to_response(txn)


@router.get("/summary")
async def payment_summary(
    month: str = Query(..., description="YYYY-MM format"),
) -> ReconciliationSummary:
    summary = await get_reconciliation_summary(month)
    return ReconciliationSummary(**summary)


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync() -> dict[str, str]:
    await sync_all_items()
    logger.info("manual_sync_triggered")
    return {"status": "sync_complete"}


@router.post("/auto-match")
async def trigger_auto_match() -> dict[str, int]:
    matched_count = await match_unmatched_transactions()
    logger.info("auto_match_triggered", matched=matched_count)
    return {"matched": matched_count}


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from err
