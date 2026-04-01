"""Pydantic schemas for the Transaction API layer."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import OptionType, TransactionCategory, TransactionStatus


class TransactionResponse(BaseModel):
    """Schema returned by the transactions list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    upload_id: uuid.UUID
    broker_name: str
    trade_date: date
    transaction_date: date
    settlement_date: date | None
    symbol: str
    option_symbol: str | None
    strike: Decimal | None
    expiry: date | None
    option_type: OptionType | None
    action: str
    description: str | None
    quantity: Decimal
    price: Decimal | None
    commission: Decimal
    amount: Decimal
    category: TransactionCategory
    status: TransactionStatus
    deleted_at: datetime | None


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""

    total: int
    offset: int
    limit: int
    items: list[TransactionResponse]
