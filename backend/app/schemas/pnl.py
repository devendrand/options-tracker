"""Pydantic schemas for the P&L Summary API layer."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class PnlPeriodResponse(BaseModel):
    """P&L aggregated for a single time period."""

    period_label: str
    options_pnl: Decimal
    equity_pnl: Decimal
    total_pnl: Decimal


class PnlSummaryResponse(BaseModel):
    """Response envelope for the P&L summary endpoint."""

    period: str
    group_by: str = "period"
    items: list[PnlPeriodResponse]
