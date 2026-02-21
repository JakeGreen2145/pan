import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from pan.services.plaid_service import (
    create_link_token,
    exchange_public_token,
    get_linked_accounts,
)

logger = structlog.get_logger()
router = APIRouter()


class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangeRequest(BaseModel):
    public_token: str
    institution_name: str


class ExchangeResponse(BaseModel):
    item_id: str
    institution_name: str


class LinkedAccount(BaseModel):
    item_id: str
    institution_name: str
    account_id: str | None = None
    account_name: str | None = None
    account_type: str | None = None
    last_synced_at: str | None = None


@router.get("/accounts")
async def list_accounts() -> list[LinkedAccount]:
    accounts = await get_linked_accounts()
    return [LinkedAccount(**a) for a in accounts]


@router.post("/link-token")
async def generate_link_token() -> LinkTokenResponse:
    token = await create_link_token()
    return LinkTokenResponse(link_token=token)


@router.post("/exchange")
async def exchange_token(body: ExchangeRequest) -> ExchangeResponse:
    result = await exchange_public_token(body.public_token, body.institution_name)
    logger.info("plaid_token_exchanged", institution=body.institution_name)
    return ExchangeResponse(**result)
