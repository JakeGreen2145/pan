import asyncio
import re
import uuid
from datetime import datetime
from decimal import Decimal

import plaid
import structlog
from plaid.api import plaid_api
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from sqlalchemy import select

from pan.config.settings import get_settings
from pan.services.database import get_session
from pan.services.models import BankTransaction, PlaidItem

logger = structlog.get_logger()

ZELLE_SENDER_PATTERNS = [
    re.compile(
        r"(?:ZELLE|Zelle)\s+(?:TRANSFER|PAYMENT|PMT)\s+(?:FROM|FRM)\s+(.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:FROM|FRM)\s+(.+?)(?:\s+ID[:.]|\s*$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"Zelle\s+(.+)",
        re.IGNORECASE,
    ),
]

_PLAID_ENV_MAP: dict[str, plaid.Environment] = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Production,
    "production": plaid.Environment.Production,
}


def _parse_zelle_sender(description: str) -> str | None:
    for pattern in ZELLE_SENDER_PATTERNS:
        match = pattern.search(description)
        if match:
            return match.group(1).strip()
    return None


def _get_plaid_client() -> plaid_api.PlaidApi:
    settings = get_settings().plaid
    env = _PLAID_ENV_MAP.get(settings.environment.lower(), plaid.Environment.Production)

    configuration = plaid.Configuration(
        host=env,
        api_key={
            "clientId": settings.client_id,
            "secret": settings.secret.get_secret_value(),
        },
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)


async def create_link_token(user_id: str) -> str:
    client = _get_plaid_client()
    settings = get_settings().plaid

    request = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Pan",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
        webhook=settings.webhook_url or None,
    )

    response = await asyncio.to_thread(client.link_token_create, request)
    link_token: str = response["link_token"]

    logger.info("link_token_created", user_id=user_id)
    return link_token


async def exchange_public_token(public_token: str, institution_name: str) -> PlaidItem:
    client = _get_plaid_client()

    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = await asyncio.to_thread(client.item_public_token_exchange, request)

    access_token: str = response["access_token"]
    item_id: str = response["item_id"]

    async with get_session() as session:
        plaid_item = PlaidItem(
            institution_name=institution_name,
            access_token=access_token,
            item_id=item_id,
        )
        session.add(plaid_item)

    logger.info(
        "public_token_exchanged",
        institution=institution_name,
        item_id=item_id,
    )
    return plaid_item


async def sync_transactions(plaid_item_id: uuid.UUID) -> list[BankTransaction]:
    client = _get_plaid_client()
    new_transactions: list[BankTransaction] = []

    async with get_session() as session:
        result = await session.execute(select(PlaidItem).where(PlaidItem.id == plaid_item_id))
        plaid_item = result.scalars().first()

        if not plaid_item:
            logger.warning("plaid_item_not_found", plaid_item_id=str(plaid_item_id))
            return []

        cursor = plaid_item.cursor
        has_more = True

        while has_more:
            request = TransactionsSyncRequest(
                access_token=plaid_item.access_token,
                cursor=cursor or "",
            )
            response = await asyncio.to_thread(client.transactions_sync, request)

            for txn in response["added"]:
                plaid_txn_id: str = txn["transaction_id"]

                existing = await session.execute(
                    select(BankTransaction).where(
                        BankTransaction.plaid_transaction_id == plaid_txn_id
                    )
                )
                if existing.scalars().first():
                    continue

                name: str = txn.get("name", "")
                original_description: str | None = txn.get("original_description")
                check_text = f"{name} {original_description or ''}".lower()
                is_zelle = "zelle" in check_text

                parsed_sender: str | None = None
                if is_zelle and original_description:
                    parsed_sender = _parse_zelle_sender(original_description)
                if is_zelle and not parsed_sender:
                    parsed_sender = _parse_zelle_sender(name)

                raw_amount = float(txn.get("amount", 0))
                amount = Decimal(str(abs(raw_amount)))

                bank_txn = BankTransaction(
                    plaid_item_id=plaid_item.id,
                    plaid_transaction_id=plaid_txn_id,
                    amount=amount,
                    date=txn["date"],
                    name=name,
                    original_description=original_description,
                    payment_channel=txn.get("payment_channel"),
                    is_zelle=is_zelle,
                    parsed_sender_name=parsed_sender,
                )
                session.add(bank_txn)
                new_transactions.append(bank_txn)

            for txn in response["modified"]:
                plaid_txn_id = txn["transaction_id"]
                existing_result = await session.execute(
                    select(BankTransaction).where(
                        BankTransaction.plaid_transaction_id == plaid_txn_id
                    )
                )
                existing_txn = existing_result.scalars().first()
                if existing_txn:
                    existing_txn.amount = Decimal(str(abs(float(txn.get("amount", 0)))))
                    existing_txn.date = txn["date"]
                    existing_txn.name = txn.get("name", "")
                    existing_txn.original_description = txn.get("original_description")
                    existing_txn.payment_channel = txn.get("payment_channel")

                    check_text = (
                        f"{existing_txn.name} {existing_txn.original_description or ''}".lower()
                    )
                    existing_txn.is_zelle = "zelle" in check_text

                    if existing_txn.is_zelle:
                        existing_txn.parsed_sender_name = _parse_zelle_sender(
                            existing_txn.original_description or existing_txn.name
                        )

            for txn in response["removed"]:
                plaid_txn_id = txn["transaction_id"]
                existing_result = await session.execute(
                    select(BankTransaction).where(
                        BankTransaction.plaid_transaction_id == plaid_txn_id
                    )
                )
                existing_txn = existing_result.scalars().first()
                if existing_txn:
                    await session.delete(existing_txn)

            cursor = response["next_cursor"]
            has_more = response["has_more"]

        plaid_item.cursor = cursor
        plaid_item.last_synced_at = datetime.now()

    logger.info(
        "transactions_synced",
        plaid_item_id=str(plaid_item_id),
        new_count=len(new_transactions),
    )
    return new_transactions


async def sync_all_items() -> int:
    async with get_session() as session:
        result = await session.execute(select(PlaidItem))
        items = result.scalars().all()

    if not items:
        logger.info("sync_all_items_skipped", reason="no_plaid_items")
        return 0

    total_new = 0
    for item in items:
        try:
            new_txns = await sync_transactions(item.id)
            total_new += len(new_txns)
        except Exception:
            logger.exception("sync_item_failed", plaid_item_id=str(item.id))

    logger.info("sync_all_items_complete", total_new=total_new, items_count=len(items))
    return total_new


async def get_linked_accounts() -> list[dict]:
    async with get_session() as session:
        result = await session.execute(select(PlaidItem))
        items = result.scalars().all()

    return [
        {
            "id": str(item.id),
            "institution_name": item.institution_name,
            "last_synced_at": item.last_synced_at.isoformat() if item.last_synced_at else None,
        }
        for item in items
    ]
