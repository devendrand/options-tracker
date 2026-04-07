"""GET /api/v1/positions and GET /api/v1/positions/{id} endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.enums import EquityPositionStatus, OptionsPositionStatus
from app.repositories.position_repository import PositionRepository
from app.schemas.position import (
    EquityPositionResponse,
    OptionsPositionDetailResponse,
    OptionsPositionLegResponse,
    OptionsPositionResponse,
    PositionListResponse,
)

router = APIRouter(prefix="/positions", tags=["positions"])

_MAX_LIMIT = 500
_AssetType = Literal["options", "equity", "all"]


@router.get("", response_model=PositionListResponse)
async def list_positions(
    asset_type: _AssetType = Query(default="options"),
    underlying: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=_MAX_LIMIT),
    db: AsyncSession = Depends(get_db),
) -> PositionListResponse:
    """Return a paginated list of options and/or equity positions."""
    repo = PositionRepository(db)

    opts_status: OptionsPositionStatus | None = None
    eq_status: EquityPositionStatus | None = None

    if status is not None:
        # Attempt to parse as options status first, then equity
        try:
            opts_status = OptionsPositionStatus(status)
        except ValueError:
            pass
        try:
            eq_status = EquityPositionStatus(status)
        except ValueError:
            pass

    options_items: list[OptionsPositionResponse] = []
    equity_items: list[EquityPositionResponse] = []
    total = 0

    if asset_type in ("options", "all"):
        opts_total, opts_rows = await repo.list_options_positions(
            underlying=underlying,
            status=opts_status,
            offset=offset,
            limit=limit,
        )
        total += opts_total
        for pos, opened_at, closed_at in opts_rows:
            resp = OptionsPositionResponse.model_validate(pos)
            resp.opened_at = opened_at
            resp.closed_at = closed_at
            options_items.append(resp)

    if asset_type in ("equity", "all"):
        eq_total, eq_rows = await repo.list_equity_positions(
            underlying=underlying,
            status=eq_status,
            offset=offset,
            limit=limit,
        )
        total += eq_total
        equity_items = [EquityPositionResponse.model_validate(r) for r in eq_rows]

    return PositionListResponse(
        total=total,
        offset=offset,
        limit=limit,
        options_items=options_items,
        equity_items=equity_items,
    )


@router.get("/{position_id}", response_model=OptionsPositionDetailResponse)
async def get_position_detail(
    position_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> OptionsPositionDetailResponse:
    """Return an options position with all legs."""
    repo = PositionRepository(db)
    result = await repo.get_options_position_detail(position_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Position not found")
    position, opened_at, closed_at = result

    detail = OptionsPositionDetailResponse.model_validate(position)
    detail.opened_at = opened_at
    detail.closed_at = closed_at
    detail.legs = [OptionsPositionLegResponse.model_validate(leg) for leg in position.legs]
    detail.total_realized_pnl = position.realized_pnl
    return detail
