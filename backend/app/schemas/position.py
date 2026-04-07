"""Pydantic schemas for the Position API layer."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import (
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPositionStatus,
    OptionType,
    PositionDirection,
)


class OptionsPositionLegResponse(BaseModel):
    """Schema for an individual leg within an options position.

    When validated from an ORM ``OptionsPositionLeg`` instance, the
    ``price``, ``amount``, ``commission``, and ``trade_date`` fields are
    lifted from the eagerly-loaded ``transaction`` relationship.  They can
    also be supplied directly for non-ORM construction (e.g. in tests).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    leg_role: LegRole
    quantity: Decimal
    # Transaction-sourced fields — populated via model_validator from ORM
    trade_date: date
    price: Decimal | None
    amount: Decimal
    commission: Decimal

    @model_validator(mode="before")
    @classmethod
    def _lift_transaction_fields(cls, data: Any) -> Any:
        """Pull trade_date/price/amount/commission from the linked Transaction.

        This validator fires when validating from an ORM object (where
        ``data`` is the ``OptionsPositionLeg`` instance) and populates the
        four transaction-sourced fields from ``data.transaction``.

        When ``data`` is already a plain dict (direct construction), no-op.
        """
        if isinstance(data, dict):
            return data
        txn = getattr(data, "transaction", None)
        if txn is not None:
            # Pydantic calls model_validator before extracting field values,
            # so we convert to a dict and inject the extra fields.
            return {
                "id": getattr(data, "id", None),
                "transaction_id": getattr(data, "transaction_id", None),
                "leg_role": getattr(data, "leg_role", None),
                "quantity": getattr(data, "quantity", None),
                "trade_date": getattr(txn, "trade_date", None),
                "price": getattr(txn, "price", None),
                "amount": getattr(txn, "amount", None),
                "commission": getattr(txn, "commission", None),
            }
        return data


class OptionsPositionResponse(BaseModel):
    """Schema for an options position list item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    underlying: str
    option_symbol: str
    strike: Decimal
    expiry: date
    option_type: OptionType
    direction: PositionDirection
    status: OptionsPositionStatus
    realized_pnl: Decimal | None
    is_covered_call: bool
    opened_at: date | None = None
    closed_at: date | None = None


class OptionsPositionDetailResponse(OptionsPositionResponse):
    """Options position with full leg detail and aggregate P&L."""

    legs: list[OptionsPositionLegResponse]
    total_realized_pnl: Decimal | None = None


class EquityPositionResponse(BaseModel):
    """Schema for an equity position list item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    quantity: Decimal
    cost_basis_per_share: Decimal
    status: EquityPositionStatus
    source: EquityPositionSource
    equity_realized_pnl: Decimal | None
    closed_at: datetime | None


class PositionListResponse(BaseModel):
    """Paginated list of positions (options and/or equity)."""

    total: int
    offset: int
    limit: int
    options_items: list[OptionsPositionResponse]
    equity_items: list[EquityPositionResponse]
