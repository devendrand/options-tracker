"""GET /api/v1/transactions — list and filter transactions."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import TransactionCategory
from app.repositories.transaction_repository import TransactionRepository
from app.schemas.transaction import TransactionListResponse, TransactionResponse

router = APIRouter(prefix="/transactions", tags=["transactions"])

_MAX_LIMIT = 500


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    upload_id: uuid.UUID | None = Query(default=None),
    category: TransactionCategory | None = Query(default=None),
    symbol: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=_MAX_LIMIT),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    """Return a paginated, optionally-filtered list of active transactions."""
    repo = TransactionRepository(db)
    total, rows = await repo.list_transactions(
        upload_id=upload_id,
        category=category,
        symbol=symbol,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
    return TransactionListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[TransactionResponse.model_validate(r) for r in rows],
    )
