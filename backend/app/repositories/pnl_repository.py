"""Repository for P&L summary aggregation queries."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EquityPositionStatus, OptionsPositionStatus
from app.models.equity_position import EquityPosition
from app.models.options_position import OptionsPosition
from app.models.options_position_leg import OptionsPositionLeg
from app.models.transaction import Transaction
from app.schemas.pnl import PnlPeriodResponse


class PnlRepository:
    """Data-access layer for P&L aggregation across positions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def get_pnl_summary(
        self,
        *,
        period: str = "year",
        pnl_type: str = "all",
        underlying: str | None = None,
    ) -> list[PnlPeriodResponse]:
        """Return chronologically-ordered P&L buckets per period.

        Args:
            period: ``'month'`` or ``'year'`` grouping.
            pnl_type: ``'options'``, ``'equity'``, or ``'all'``.
            underlying: Optional ticker filter applied to both options and equity.

        Returns:
            List of :class:`PnlPeriodResponse` ordered ascending by period label.
        """
        options_by_period = await self._options_pnl_by_period(period=period, underlying=underlying)
        equity_by_period = await self._equity_pnl_by_period(period=period, underlying=underlying)

        all_labels: set[str] = set()
        if pnl_type in ("options", "all"):
            all_labels |= options_by_period.keys()
        if pnl_type in ("equity", "all"):
            all_labels |= equity_by_period.keys()

        results: list[PnlPeriodResponse] = []
        for label in sorted(all_labels):
            opts_pnl = options_by_period.get(label, Decimal("0.00"))
            eq_pnl = equity_by_period.get(label, Decimal("0.00"))

            if pnl_type == "options":
                eq_pnl = Decimal("0.00")
            elif pnl_type == "equity":
                opts_pnl = Decimal("0.00")

            results.append(
                PnlPeriodResponse(
                    period_label=label,
                    options_pnl=opts_pnl,
                    equity_pnl=eq_pnl,
                    total_pnl=opts_pnl + eq_pnl,
                )
            )

        return results

    async def _options_pnl_by_period(
        self,
        *,
        period: str,
        underlying: str | None,
    ) -> dict[str, Decimal]:
        """Aggregate realized P&L from closed OptionsPosition records."""
        closed_statuses = [
            OptionsPositionStatus.CLOSED,
            OptionsPositionStatus.EXPIRED,
            OptionsPositionStatus.ASSIGNED,
            OptionsPositionStatus.EXERCISED,
        ]

        # We use the transaction_date of the close leg as the P&L date.
        # Join: options_positions -> options_position_legs (CLOSE) -> transactions
        close_leg_date = (
            select(
                OptionsPositionLeg.position_id,
                func.min(Transaction.transaction_date).label("close_date"),
            )
            .join(Transaction, Transaction.id == OptionsPositionLeg.transaction_id)
            .where(OptionsPositionLeg.leg_role == "CLOSE")
            .group_by(OptionsPositionLeg.position_id)
            .subquery("close_leg_date")
        )

        base_q = (
            select(OptionsPosition)
            .where(OptionsPosition.status.in_(closed_statuses))
            .where(OptionsPosition.deleted_at.is_(None))
            .where(OptionsPosition.realized_pnl.is_not(None))
            .join(close_leg_date, close_leg_date.c.position_id == OptionsPosition.id)
        )
        if underlying is not None:
            base_q = base_q.where(OptionsPosition.underlying == underlying)

        pos_sub = base_q.subquery("opts_pos")

        if period == "month":
            grp_label = func.to_char(close_leg_date.c.close_date, "YYYY-MM")
        else:
            grp_label = func.to_char(close_leg_date.c.close_date, "YYYY")

        final_q = (
            select(grp_label.label("lbl"), func.sum(pos_sub.c.realized_pnl).label("pnl"))
            .select_from(pos_sub)
            .join(close_leg_date, close_leg_date.c.position_id == pos_sub.c.id)
            .group_by(grp_label)
        )

        rows = (await self._session.execute(final_q)).all()
        return {str(row.lbl): Decimal(str(row.pnl)) for row in rows}

    async def _equity_pnl_by_period(
        self,
        *,
        period: str,
        underlying: str | None,
    ) -> dict[str, Decimal]:
        """Aggregate realized P&L from closed EquityPosition records."""
        base_q = (
            select(EquityPosition)
            .where(EquityPosition.status == EquityPositionStatus.CLOSED)
            .where(EquityPosition.deleted_at.is_(None))
            .where(EquityPosition.equity_realized_pnl.is_not(None))
            .where(EquityPosition.closed_at.is_not(None))
        )
        if underlying is not None:
            base_q = base_q.where(EquityPosition.symbol == underlying)

        eq_sub = base_q.subquery("eq_pos")

        if period == "month":
            grp_label = func.to_char(eq_sub.c.closed_at, "YYYY-MM")
        else:
            grp_label = func.to_char(eq_sub.c.closed_at, "YYYY")

        final_q = (
            select(grp_label.label("lbl"), func.sum(eq_sub.c.equity_realized_pnl).label("pnl"))
            .select_from(eq_sub)
            .group_by(grp_label)
        )

        rows = (await self._session.execute(final_q)).all()
        return {str(row.lbl): Decimal(str(row.pnl)) for row in rows}
