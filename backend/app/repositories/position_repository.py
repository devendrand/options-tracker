"""Repository for filtered, paginated Position queries."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import EquityPositionStatus, OptionsPositionStatus
from app.models.equity_position import EquityPosition
from app.models.options_position import OptionsPosition
from app.models.options_position_leg import OptionsPositionLeg
from app.models.transaction import Transaction


def _open_leg_date_subquery() -> object:
    """Return a subquery yielding (position_id, min open transaction_date)."""
    return (
        select(
            OptionsPositionLeg.position_id,
            func.min(Transaction.transaction_date).label("open_date"),
        )
        .join(Transaction, Transaction.id == OptionsPositionLeg.transaction_id)
        .where(OptionsPositionLeg.leg_role == "OPEN")
        .group_by(OptionsPositionLeg.position_id)
        .subquery("open_leg_date")
    )


def _close_leg_date_subquery() -> object:
    """Return a subquery yielding (position_id, min close transaction_date)."""
    return (
        select(
            OptionsPositionLeg.position_id,
            func.min(Transaction.transaction_date).label("close_date"),
        )
        .join(Transaction, Transaction.id == OptionsPositionLeg.transaction_id)
        .where(OptionsPositionLeg.leg_role == "CLOSE")
        .group_by(OptionsPositionLeg.position_id)
        .subquery("close_leg_date")
    )


class PositionRepository:
    """Data-access layer for OptionsPosition and EquityPosition records."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def list_options_positions(
        self,
        *,
        underlying: str | None = None,
        status: OptionsPositionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[tuple[OptionsPosition, date | None, date | None]]]:
        """Return (total_count, page) of options positions matching filters.

        Each row in the page is a 3-tuple of
        ``(OptionsPosition, opened_at, closed_at)`` where the dates are
        derived from the earliest OPEN/CLOSE leg transaction_date respectively.

        Soft-deleted positions (deleted_at IS NOT NULL) are excluded.
        """
        open_sub = _open_leg_date_subquery()
        close_sub = _close_leg_date_subquery()

        base_q = select(OptionsPosition).where(OptionsPosition.deleted_at.is_(None))

        if underlying is not None:
            base_q = base_q.where(OptionsPosition.underlying == underlying)
        if status is not None:
            base_q = base_q.where(OptionsPosition.status == status)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = (
            select(OptionsPosition, open_sub.c.open_date, close_sub.c.close_date)
            .where(OptionsPosition.deleted_at.is_(None))
        )
        if underlying is not None:
            rows_q = rows_q.where(OptionsPosition.underlying == underlying)
        if status is not None:
            rows_q = rows_q.where(OptionsPosition.status == status)
        rows_q = (
            rows_q
            .outerjoin(open_sub, open_sub.c.position_id == OptionsPosition.id)
            .outerjoin(close_sub, close_sub.c.position_id == OptionsPosition.id)
            .order_by(OptionsPosition.expiry.asc(), OptionsPosition.id)
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self._session.execute(rows_q)).all())
        return total, rows

    async def get_options_position_detail(
        self,
        position_id: uuid.UUID,
    ) -> tuple[OptionsPosition, date | None, date | None] | None:
        """Return an OptionsPosition with eagerly-loaded legs and date annotations.

        Returns a 3-tuple of ``(OptionsPosition, opened_at, closed_at)``,
        or ``None`` if the position does not exist or is soft-deleted.
        """
        open_sub = _open_leg_date_subquery()
        close_sub = _close_leg_date_subquery()

        q = (
            select(OptionsPosition, open_sub.c.open_date, close_sub.c.close_date)
            .where(OptionsPosition.id == position_id)
            .where(OptionsPosition.deleted_at.is_(None))
            .options(
                selectinload(OptionsPosition.legs).selectinload(OptionsPositionLeg.transaction)
            )
            .outerjoin(open_sub, open_sub.c.position_id == OptionsPosition.id)
            .outerjoin(close_sub, close_sub.c.position_id == OptionsPosition.id)
        )
        result = await self._session.execute(q)
        return result.first()

    async def list_equity_positions(
        self,
        *,
        underlying: str | None = None,
        status: EquityPositionStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[EquityPosition]]:
        """Return (total_count, page) of equity positions matching filters.

        Soft-deleted positions (deleted_at IS NOT NULL) are excluded.
        """
        base_q = select(EquityPosition).where(EquityPosition.deleted_at.is_(None))

        if underlying is not None:
            base_q = base_q.where(EquityPosition.symbol == underlying)
        if status is not None:
            base_q = base_q.where(EquityPosition.status == status)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = base_q.order_by(EquityPosition.id).offset(offset).limit(limit)
        rows = list((await self._session.execute(rows_q)).scalars().all())
        return total, rows
