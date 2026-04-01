"""Repository for filtered, paginated Position queries."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import EquityPositionStatus, OptionsPositionStatus
from app.models.equity_position import EquityPosition
from app.models.options_position import OptionsPosition
from app.models.options_position_leg import OptionsPositionLeg


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
    ) -> tuple[int, list[OptionsPosition]]:
        """Return (total_count, page) of options positions matching filters.

        Soft-deleted positions (deleted_at IS NOT NULL) are excluded.
        """
        base_q = select(OptionsPosition).where(OptionsPosition.deleted_at.is_(None))

        if underlying is not None:
            base_q = base_q.where(OptionsPosition.underlying == underlying)
        if status is not None:
            base_q = base_q.where(OptionsPosition.status == status)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = (
            base_q.order_by(OptionsPosition.expiry.asc(), OptionsPosition.id)
            .offset(offset)
            .limit(limit)
        )
        rows = list((await self._session.execute(rows_q)).scalars().all())
        return total, rows

    async def get_options_position_detail(
        self,
        position_id: uuid.UUID,
    ) -> OptionsPosition | None:
        """Return an OptionsPosition with eagerly-loaded legs, or None."""
        q = (
            select(OptionsPosition)
            .where(OptionsPosition.id == position_id)
            .where(OptionsPosition.deleted_at.is_(None))
            .options(
                selectinload(OptionsPosition.legs).selectinload(OptionsPositionLeg.transaction)
            )
        )
        result = await self._session.execute(q)
        return result.scalar_one_or_none()

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
