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

_OPTIONS_CLOSED_STATUSES = [
    OptionsPositionStatus.CLOSED,
    OptionsPositionStatus.EXPIRED,
    OptionsPositionStatus.ASSIGNED,
    OptionsPositionStatus.EXERCISED,
]


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
        group_by: str = "period",
    ) -> list[PnlPeriodResponse]:
        """Return chronologically-ordered P&L buckets per period.

        Args:
            period: ``'month'`` or ``'year'`` grouping.
            pnl_type: ``'options'``, ``'equity'``, or ``'all'``.
            underlying: Optional ticker filter applied to both options and equity.
            group_by: ``'period'``, ``'underlying'``, or ``'period_underlying'``.

        Returns:
            List of :class:`PnlPeriodResponse` ordered ascending by period label.
        """
        options_by_period = await self._options_pnl_grouped(
            period=period, underlying=underlying, group_by=group_by
        )
        equity_by_period = await self._equity_pnl_grouped(
            period=period, underlying=underlying, group_by=group_by
        )

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

    def _period_fmt(self, period: str) -> str:
        """Return the ``to_char`` format string for the given period bucket."""
        return "YYYY-MM" if period == "month" else "YYYY"

    def _build_grp_label_options(
        self,
        *,
        period: str,
        group_by: str,
        close_date_col: object,
        underlying_col: object,
    ) -> object:
        """Build the SQL label expression for options P&L grouping."""
        fmt = self._period_fmt(period)
        period_expr = func.to_char(close_date_col, fmt)
        if group_by == "underlying":
            return underlying_col
        if group_by == "period_underlying":
            return func.concat(period_expr, " | ", underlying_col)
        return period_expr

    def _build_grp_label_equity(
        self,
        *,
        period: str,
        group_by: str,
        closed_at_col: object,
        symbol_col: object,
    ) -> object:
        """Build the SQL label expression for equity P&L grouping."""
        fmt = self._period_fmt(period)
        period_expr = func.to_char(closed_at_col, fmt)
        if group_by == "underlying":
            return symbol_col
        if group_by == "period_underlying":
            return func.concat(period_expr, " | ", symbol_col)
        return period_expr

    async def _options_pnl_grouped(
        self,
        *,
        period: str,
        underlying: str | None,
        group_by: str = "period",
    ) -> dict[str, Decimal]:
        """Aggregate realized P&L from closed OptionsPosition records."""
        closed_statuses = _OPTIONS_CLOSED_STATUSES

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

        grp_label = self._build_grp_label_options(
            period=period,
            group_by=group_by,
            close_date_col=close_leg_date.c.close_date,
            underlying_col=pos_sub.c.underlying,
        )

        final_q = (
            select(grp_label.label("lbl"), func.sum(pos_sub.c.realized_pnl).label("pnl"))
            .select_from(pos_sub)
            .join(close_leg_date, close_leg_date.c.position_id == pos_sub.c.id)
            .group_by(grp_label)
        )

        rows = (await self._session.execute(final_q)).all()
        return {str(row.lbl): Decimal(str(row.pnl)) for row in rows}

    async def _equity_pnl_grouped(
        self,
        *,
        period: str,
        underlying: str | None,
        group_by: str = "period",
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

        grp_label = self._build_grp_label_equity(
            period=period,
            group_by=group_by,
            closed_at_col=eq_sub.c.closed_at,
            symbol_col=eq_sub.c.symbol,
        )

        final_q = (
            select(grp_label.label("lbl"), func.sum(eq_sub.c.equity_realized_pnl).label("pnl"))
            .select_from(eq_sub)
            .group_by(grp_label)
        )

        rows = (await self._session.execute(final_q)).all()
        return {str(row.lbl): Decimal(str(row.pnl)) for row in rows}

    async def get_positions_for_bucket(
        self,
        *,
        period: str = "year",
        group_by: str = "period",
        period_label: str,
        underlying: str | None = None,
        pnl_type: str = "all",
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[OptionsPosition], int, list[EquityPosition]]:
        """Return positions belonging to a specific P&L bucket.

        Args:
            period: ``'month'`` or ``'year'`` — controls the ``to_char`` format
                used when ``group_by='period'``.
            group_by: ``'period'`` filters by close-date period; ``'underlying'``
                filters by ticker (the ``period_label`` IS the ticker in that mode).
            period_label: The label that identifies the bucket — either a period
                string (``'2026'`` / ``'2026-03'``) or a ticker symbol.
            underlying: Optional additional ticker filter (only applies on top of
                the bucket filter when ``group_by='period'``).
            pnl_type: ``'options'``, ``'equity'``, or ``'all'``.
            offset: Pagination offset applied to both options and equity queries.
            limit: Maximum rows returned per position type.

        Returns:
            A 4-tuple of ``(options_total, options_rows, equity_total, equity_rows)``.
        """
        opts_total, opts_rows = 0, []
        eq_total, eq_rows = 0, []

        if pnl_type in ("options", "all"):
            opts_total, opts_rows = await self._options_positions_for_bucket(
                period=period,
                group_by=group_by,
                period_label=period_label,
                underlying=underlying,
                offset=offset,
                limit=limit,
            )

        if pnl_type in ("equity", "all"):
            eq_total, eq_rows = await self._equity_positions_for_bucket(
                period=period,
                group_by=group_by,
                period_label=period_label,
                underlying=underlying,
                offset=offset,
                limit=limit,
            )

        return opts_total, opts_rows, eq_total, eq_rows

    async def _options_positions_for_bucket(
        self,
        *,
        period: str,
        group_by: str,
        period_label: str,
        underlying: str | None,
        offset: int,
        limit: int,
    ) -> tuple[int, list[OptionsPosition]]:
        """Query closed OptionsPosition rows for the requested bucket."""
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
            .where(OptionsPosition.status.in_(_OPTIONS_CLOSED_STATUSES))
            .where(OptionsPosition.deleted_at.is_(None))
            .where(OptionsPosition.realized_pnl.is_not(None))
            .join(close_leg_date, close_leg_date.c.position_id == OptionsPosition.id)
        )

        if group_by == "underlying":
            base_q = base_q.where(OptionsPosition.underlying == period_label)
        else:
            fmt = self._period_fmt(period)
            base_q = base_q.where(
                func.to_char(close_leg_date.c.close_date, fmt) == period_label
            )

        if underlying is not None:
            base_q = base_q.where(OptionsPosition.underlying == underlying)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = base_q.offset(offset).limit(limit)
        rows: list[OptionsPosition] = list(
            (await self._session.execute(rows_q)).scalars().all()
        )

        return total, rows

    async def _equity_positions_for_bucket(
        self,
        *,
        period: str,
        group_by: str,
        period_label: str,
        underlying: str | None,
        offset: int,
        limit: int,
    ) -> tuple[int, list[EquityPosition]]:
        """Query closed EquityPosition rows for the requested bucket."""
        base_q = (
            select(EquityPosition)
            .where(EquityPosition.status == EquityPositionStatus.CLOSED)
            .where(EquityPosition.deleted_at.is_(None))
            .where(EquityPosition.equity_realized_pnl.is_not(None))
            .where(EquityPosition.closed_at.is_not(None))
        )

        if group_by == "underlying":
            base_q = base_q.where(EquityPosition.symbol == period_label)
        else:
            fmt = self._period_fmt(period)
            base_q = base_q.where(
                func.to_char(EquityPosition.closed_at, fmt) == period_label
            )

        if underlying is not None:
            base_q = base_q.where(EquityPosition.symbol == underlying)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        rows_q = base_q.offset(offset).limit(limit)
        rows: list[EquityPosition] = list(
            (await self._session.execute(rows_q)).scalars().all()
        )

        return total, rows
