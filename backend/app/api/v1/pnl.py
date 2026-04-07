"""GET /api/v1/pnl/summary and GET /api/v1/pnl/positions — P&L aggregation."""

from __future__ import annotations

from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.pnl_repository import PnlRepository
from app.schemas.pnl import PnlSummaryResponse
from app.schemas.position import (
    EquityPositionResponse,
    OptionsPositionResponse,
    PositionListResponse,
)

router = APIRouter(prefix="/pnl", tags=["pnl"])

_Period = Literal["month", "year"]
_PnlType = Literal["options", "equity", "all"]
_GroupBy = Literal["period", "underlying", "period_underlying"]


@router.get("/positions", response_model=PositionListResponse)
async def get_pnl_positions(
    period: _Period = Query(default="year"),
    group_by: Literal["period", "underlying"] = Query(default="period"),
    period_label: str = Query(...),
    underlying: str | None = Query(default=None),
    type: _PnlType = Query(default="all"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    closed_after: date_type | None = Query(default=None),
    closed_before: date_type | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PositionListResponse:
    """Return positions that contribute to a specific P&L bucket.

    The ``period_label`` parameter is required and identifies which bucket
    to drill into — either a period string (``'2026'``, ``'2026-03'``) when
    ``group_by='period'``, or a ticker symbol when ``group_by='underlying'``.

    ``closed_after`` and ``closed_before`` are optional inclusive date filters
    applied to the position close date.
    """
    repo = PnlRepository(db)
    opts_total, opts_rows, eq_total, eq_rows = await repo.get_positions_for_bucket(
        period=period,
        group_by=group_by,
        period_label=period_label,
        underlying=underlying,
        pnl_type=type,
        offset=offset,
        limit=limit,
        closed_after=closed_after,
        closed_before=closed_before,
    )
    options_items: list[OptionsPositionResponse] = []
    for pos, opened_at, closed_at in opts_rows:
        resp = OptionsPositionResponse.model_validate(pos)
        resp.opened_at = opened_at
        resp.closed_at = closed_at
        options_items.append(resp)

    return PositionListResponse(
        total=opts_total + eq_total,
        offset=offset,
        limit=limit,
        options_items=options_items,
        equity_items=[EquityPositionResponse.model_validate(p) for p in eq_rows],
    )


@router.get("/summary", response_model=PnlSummaryResponse)
async def get_pnl_summary(
    period: _Period = Query(default="year"),
    type: _PnlType = Query(default="all"),
    underlying: str | None = Query(default=None),
    group_by: _GroupBy = Query(default="period"),
    closed_after: date_type | None = Query(default=None),
    closed_before: date_type | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> PnlSummaryResponse:
    """Return realized P&L aggregated by period (month or year).

    ``closed_after`` and ``closed_before`` are optional inclusive date filters
    applied to the position close date.
    """
    repo = PnlRepository(db)
    items = await repo.get_pnl_summary(
        period=period,
        pnl_type=type,
        underlying=underlying,
        group_by=group_by,
        closed_after=closed_after,
        closed_before=closed_before,
    )
    return PnlSummaryResponse(period=period, group_by=group_by, items=items)
