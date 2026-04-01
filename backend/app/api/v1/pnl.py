"""GET /api/v1/pnl/summary — aggregated realized P&L by period."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.pnl_repository import PnlRepository
from app.schemas.pnl import PnlSummaryResponse

router = APIRouter(prefix="/pnl", tags=["pnl"])

_Period = Literal["month", "year"]
_PnlType = Literal["options", "equity", "all"]


@router.get("/summary", response_model=PnlSummaryResponse)
async def get_pnl_summary(
    period: _Period = Query(default="year"),
    type: _PnlType = Query(default="all"),
    underlying: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PnlSummaryResponse:
    """Return realized P&L aggregated by period (month or year)."""
    repo = PnlRepository(db)
    items = await repo.get_pnl_summary(
        period=period,
        pnl_type=type,
        underlying=underlying,
    )
    return PnlSummaryResponse(period=period, items=items)
