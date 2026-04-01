"""Repository for filtered, paginated Transaction queries."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TransactionCategory, TransactionStatus
from app.models.transaction import Transaction


class TransactionRepository:
    """Data-access layer for Transaction records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def list_transactions(
        self,
        *,
        upload_id: uuid.UUID | None = None,
        category: TransactionCategory | None = None,
        symbol: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[Transaction]]:
        """Return (total_count, page) of active transactions matching filters.

        Only ACTIVE transactions (deleted_at IS NULL) are returned.
        """
        base_q = (
            select(Transaction)
            .where(Transaction.status == TransactionStatus.ACTIVE)
            .where(Transaction.deleted_at.is_(None))
        )

        if upload_id is not None:
            base_q = base_q.where(Transaction.upload_id == upload_id)
        if category is not None:
            base_q = base_q.where(Transaction.category == category)
        if symbol is not None:
            base_q = base_q.where(Transaction.symbol == symbol)
        if date_from is not None:
            base_q = base_q.where(Transaction.transaction_date >= date_from)
        if date_to is not None:
            base_q = base_q.where(Transaction.transaction_date <= date_to)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = (
            base_q.order_by(Transaction.transaction_date.desc(), Transaction.id)
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self._session.execute(rows_q)).scalars().all())
        return total, rows
