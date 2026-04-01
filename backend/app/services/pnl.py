"""P&L calculation service.

Pure calculation functions — no database interaction, no async, no side effects.
All financial values use :class:`decimal.Decimal` throughout; never float.

Cash-flow sign convention (from CLAUDE.md):
  Positive amount = cash credited (premium received, sale proceeds)
  Negative amount = cash debited (premium paid, purchase cost)

Options P&L formula:
  Realized P&L = Open Amount + Close Amount − |open_commission| − |close_commission|

Equity P&L formula:
  Realized P&L = (sell_price − cost_basis_per_share) × quantity_sold − commissions
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class LegData:
    """Minimal leg data required for options P&L calculation.

    :param quantity: Number of contracts (absolute value).
    :param price: Per-contract price (informational; amount is authoritative).
    :param amount: Total cash-flow amount (signed per cash-flow convention).
    :param commission: Absolute commission paid for this leg.
    :param is_open: ``True`` for an open leg; ``False`` for a close leg.
    """

    quantity: Decimal
    price: Decimal
    amount: Decimal
    commission: Decimal
    is_open: bool


@dataclass
class OptionsPnlResult:
    """P&L result for a single options position.

    :param realized_pnl: Realized P&L, or ``None`` when no close legs exist
        (position still fully open).
    :param open_amount: Sum of all open-leg amounts.
    :param close_amount: Sum of all close-leg amounts.
    :param total_commission: Sum of absolute commissions across all legs.
    """

    realized_pnl: Decimal | None
    open_amount: Decimal
    close_amount: Decimal
    total_commission: Decimal


@dataclass
class EquityPnlResult:
    """P&L result for a single equity lot closure.

    :param realized_pnl: Realized P&L after commissions.
    :param cost_basis: Total cost basis (cost_basis_per_share × quantity_sold).
    :param sale_proceeds: Total sale proceeds (sell_price × quantity_sold).
    :param total_commission: Sum of absolute open and close commissions.
    """

    realized_pnl: Decimal
    cost_basis: Decimal
    sale_proceeds: Decimal
    total_commission: Decimal


@dataclass
class PnlSummaryEntry:
    """A single aggregated P&L entry for a given period and symbol.

    :param period: ISO-style period string — ``"YYYY-MM"`` for month mode,
        ``"YYYY"`` for year mode.
    :param symbol: Underlying ticker symbol.
    :param options_pnl: Total realized options P&L for this period/symbol.
    :param equity_pnl: Total realized equity P&L for this period/symbol.
    :param total_pnl: ``options_pnl + equity_pnl``.
    """

    period: str
    symbol: str
    options_pnl: Decimal
    equity_pnl: Decimal
    total_pnl: Decimal


# ---------------------------------------------------------------------------
# Internal accumulator (not exported)
# ---------------------------------------------------------------------------


@dataclass
class _PnlAccumulator:
    """Mutable accumulator used during aggregation."""

    options_pnl: Decimal = field(default_factory=lambda: Decimal("0.00"))
    equity_pnl: Decimal = field(default_factory=lambda: Decimal("0.00"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_options_pnl(legs: list[LegData]) -> OptionsPnlResult:
    """Calculate realized P&L for an options position from its legs.

    The formula follows the cash-flow convention:

        Realized P&L = Open Amount + Close Amount − |open_commission| − |close_commission|

    where *Open Amount* and *Close Amount* are the sums of the ``amount``
    fields of the respective leg types.

    If **no close legs** are present, ``realized_pnl`` is returned as
    ``None`` (the position is still fully open).

    :param legs: List of :class:`LegData` instances for the position.
        May be empty.
    :returns: :class:`OptionsPnlResult` with computed fields.
    """
    open_amount = Decimal("0.00")
    close_amount = Decimal("0.00")
    total_commission = Decimal("0.00")
    has_close_leg = False

    for leg in legs:
        total_commission += abs(leg.commission)
        if leg.is_open:
            open_amount += leg.amount
        else:
            close_amount += leg.amount
            has_close_leg = True

    realized_pnl: Decimal | None
    if has_close_leg:
        realized_pnl = open_amount + close_amount - total_commission
    else:
        realized_pnl = None

    return OptionsPnlResult(
        realized_pnl=realized_pnl,
        open_amount=open_amount,
        close_amount=close_amount,
        total_commission=total_commission,
    )


def calculate_equity_pnl(
    cost_basis_per_share: Decimal,
    quantity_sold: Decimal,
    sell_price: Decimal,
    open_commission: Decimal,
    close_commission: Decimal,
) -> EquityPnlResult:
    """Calculate realized P&L for an equity lot sale.

    Formula:

        Realized P&L = (sell_price − cost_basis_per_share) × quantity_sold
                       − |open_commission| − |close_commission|

    :param cost_basis_per_share: Per-share cost basis of the equity lot.
    :param quantity_sold: Number of shares sold (absolute value).
    :param sell_price: Per-share sale price.
    :param open_commission: Commission paid when the lot was opened.
    :param close_commission: Commission paid when the lot was closed (this sale).
    :returns: :class:`EquityPnlResult` with computed fields.
    """
    cost_basis = cost_basis_per_share * quantity_sold
    sale_proceeds = sell_price * quantity_sold
    total_commission = abs(open_commission) + abs(close_commission)
    realized_pnl = sale_proceeds - cost_basis - total_commission

    return EquityPnlResult(
        realized_pnl=realized_pnl,
        cost_basis=cost_basis,
        sale_proceeds=sale_proceeds,
        total_commission=total_commission,
    )


def aggregate_pnl(
    options_results: list[tuple[str, date, OptionsPnlResult]],
    equity_results: list[tuple[str, date, EquityPnlResult]],
    period: str = "month",
) -> list[PnlSummaryEntry]:
    """Aggregate P&L results by period (month or year) and symbol.

    Each unique ``(period_key, symbol)`` pair produces one
    :class:`PnlSummaryEntry`.  Options positions whose ``realized_pnl`` is
    ``None`` (still open) are excluded from aggregation.

    :param options_results: Sequence of ``(symbol, close_date, result)``
        tuples for closed options positions.
    :param equity_results: Sequence of ``(symbol, close_date, result)``
        tuples for closed equity lots.
    :param period: Aggregation granularity — ``"month"`` (``"YYYY-MM"``) or
        ``"year"`` (``"YYYY"``).  Any other value raises :exc:`ValueError`.
    :returns: List of :class:`PnlSummaryEntry` instances, one per unique
        ``(period, symbol)`` pair.
    :raises ValueError: If ``period`` is not ``"month"`` or ``"year"``.
    """
    if period not in ("month", "year"):
        raise ValueError(f"Unsupported period '{period}': must be 'month' or 'year'.")

    accumulators: dict[tuple[str, str], _PnlAccumulator] = defaultdict(_PnlAccumulator)

    for symbol, close_date, options_result in options_results:
        if options_result.realized_pnl is None:
            continue
        period_key = _period_key(close_date, period)
        accumulators[(period_key, symbol)].options_pnl += options_result.realized_pnl

    for symbol, close_date, equity_result in equity_results:
        period_key = _period_key(close_date, period)
        accumulators[(period_key, symbol)].equity_pnl += equity_result.realized_pnl

    return [
        PnlSummaryEntry(
            period=period_key,
            symbol=symbol,
            options_pnl=acc.options_pnl,
            equity_pnl=acc.equity_pnl,
            total_pnl=acc.options_pnl + acc.equity_pnl,
        )
        for (period_key, symbol), acc in accumulators.items()
    ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _period_key(d: date, period: str) -> str:
    """Format a :class:`~datetime.date` as a period key string.

    :param d: The date to format.
    :param period: ``"month"`` → ``"YYYY-MM"``; ``"year"`` → ``"YYYY"``.
    :returns: Formatted period string.
    """
    if period == "month":
        return d.strftime("%Y-%m")
    return d.strftime("%Y")
