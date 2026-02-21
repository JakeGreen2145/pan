import os
import uuid

import aiofiles
import anyio
import structlog
from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from pan.services.database import get_session
from pan.services.models import LeaseDocument, Tenant

logger = structlog.get_logger()
router = APIRouter()

DATA_DIR = os.environ.get("PAN_DATA_DIR", "data")
LEASES_DIR = os.path.join(DATA_DIR, "leases")


class LeaseResponse(BaseModel):
    id: str
    tenant_id: str
    filename: str
    lease_start: str | None
    lease_end: str | None
    uploaded_at: str


def _lease_to_response(doc: LeaseDocument) -> LeaseResponse:
    return LeaseResponse(
        id=str(doc.id),
        tenant_id=str(doc.tenant_id),
        filename=doc.filename,
        lease_start=doc.lease_start.isoformat() if doc.lease_start else None,
        lease_end=doc.lease_end.isoformat() if doc.lease_end else None,
        uploaded_at=doc.uploaded_at.isoformat(),
    )


@router.get("")
async def list_leases() -> list[LeaseResponse]:
    async with get_session() as session:
        result = await session.execute(
            select(LeaseDocument).order_by(LeaseDocument.uploaded_at.desc())
        )
        docs = result.scalars().all()

    return [_lease_to_response(d) for d in docs]


@router.get("/{tenant_id}")
async def list_tenant_leases(tenant_id: str) -> list[LeaseResponse]:
    tenant_uuid = _parse_uuid(tenant_id)
    async with get_session() as session:
        result = await session.execute(
            select(LeaseDocument)
            .where(LeaseDocument.tenant_id == tenant_uuid)
            .order_by(LeaseDocument.uploaded_at.desc())
        )
        docs = result.scalars().all()

    return [_lease_to_response(d) for d in docs]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_lease(
    tenant_id: str = Form(...),
    file: UploadFile | None = None,
) -> LeaseResponse:
    if file is None:
        raise HTTPException(status_code=422, detail="File is required")

    tenant_uuid = _parse_uuid(tenant_id)

    async with get_session() as session:
        result = await session.execute(select(Tenant).where(Tenant.id == tenant_uuid))
        tenant = result.scalars().first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

    await anyio.Path(LEASES_DIR).mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4()
    safe_filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(LEASES_DIR, safe_filename)

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    async with get_session() as session:
        doc = LeaseDocument(
            id=file_id,
            tenant_id=tenant_uuid,
            filename=file.filename or "lease.pdf",
            file_path=file_path,
        )
        session.add(doc)
        await session.flush()

        result = await session.execute(select(LeaseDocument).where(LeaseDocument.id == file_id))
        doc = result.scalars().first()

        logger.info(
            "lease_uploaded",
            lease_id=str(file_id),
            tenant_id=tenant_id,
            filename=file.filename,
        )

    return _lease_to_response(doc)  # type: ignore[arg-type]


@router.get("/{lease_id}/download")
async def download_lease(lease_id: str) -> FileResponse:
    lease_uuid = _parse_uuid(lease_id)
    async with get_session() as session:
        result = await session.execute(select(LeaseDocument).where(LeaseDocument.id == lease_uuid))
        doc = result.scalars().first()

    if not doc:
        raise HTTPException(status_code=404, detail="Lease document not found")

    if not await anyio.Path(doc.file_path).exists():
        raise HTTPException(status_code=404, detail="Lease file missing from storage")

    return FileResponse(
        path=doc.file_path,
        filename=doc.filename,
        media_type="application/pdf",
    )


@router.delete("/{lease_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lease(lease_id: str) -> None:
    lease_uuid = _parse_uuid(lease_id)
    async with get_session() as session:
        result = await session.execute(select(LeaseDocument).where(LeaseDocument.id == lease_uuid))
        doc = result.scalars().first()

        if not doc:
            raise HTTPException(status_code=404, detail="Lease document not found")

        async_path = anyio.Path(doc.file_path)
        if await async_path.exists():
            await async_path.unlink()

        await session.delete(doc)
        logger.info("lease_deleted", lease_id=lease_id)


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid UUID format") from err
