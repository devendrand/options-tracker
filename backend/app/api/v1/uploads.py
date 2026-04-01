"""Upload API endpoints: POST, GET, GET/{id}, DELETE/{id}."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.upload_repository import UploadRepository
from app.schemas.upload import (
    UploadDeleteResponse,
    UploadDetailResponse,
    UploadListResponse,
    UploadResponse,
)
from app.services.upload_orchestrator import process_upload

router = APIRouter(prefix="/uploads", tags=["uploads"])

_MAX_LIMIT = 500


@router.post("", response_model=UploadResponse, status_code=201)
async def create_upload(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Upload a CSV file and run the full processing pipeline."""
    if file.filename is None or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content_bytes = await file.read()
    csv_content = content_bytes.decode("utf-8")

    result = await process_upload(db, filename=file.filename, csv_content=csv_content)
    await db.commit()

    return UploadResponse.model_validate(result.upload)


@router.get("", response_model=UploadListResponse)
async def list_uploads(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=_MAX_LIMIT),
    db: AsyncSession = Depends(get_db),
) -> UploadListResponse:
    """Return a paginated list of active uploads."""
    repo = UploadRepository(db)
    total, rows = await repo.list_uploads(offset=offset, limit=limit)
    return UploadListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[UploadResponse.model_validate(r) for r in rows],
    )


@router.get("/{upload_id}", response_model=UploadDetailResponse)
async def get_upload_detail(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UploadDetailResponse:
    """Return upload details including transaction count."""
    repo = UploadRepository(db)
    upload = await repo.get_by_id(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    txn_count = await repo.get_transaction_count(upload_id)
    detail = UploadDetailResponse.model_validate(upload)
    detail.transaction_count = txn_count
    return detail


@router.delete("/{upload_id}", response_model=UploadDeleteResponse)
async def delete_upload(
    upload_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> UploadDeleteResponse:
    """Soft-delete an upload and cascade to related records."""
    repo = UploadRepository(db)
    upload = await repo.soft_delete(upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    await db.commit()
    return UploadDeleteResponse(
        id=upload.id,
        status=upload.status,
        warning=(
            "Previously deduplicated rows from this upload may resurface"
            " as new in future uploads."
        ),
    )
