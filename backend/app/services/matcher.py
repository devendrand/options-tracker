"""FIFO options position matcher service.

This is a pure logic module — no SQLAlchemy session, no async I/O, no DB
queries.  It operates entirely on in-memory data structures.  The upload API
layer (F-12) is responsible for persisting the returned :class:`MatchResult`
to the database.

Matching rules (CLAUDE.md + F-09 plan)
---------------------------------------
Contract identity key: ``(underlying, strike, expiry, option_type)`` — all
four fields must match exactly.

FIFO: The oldest open leg (by ``transaction_date``) is matched against the
earliest close leg for the same contract.

Open categories:
    ``OPTIONS_BUY_TO_OPEN``, ``OPTIONS_SELL_TO_OPEN``

Close categories:
    ``OPTIONS_BUY_TO_CLOSE``, ``OPTIONS_SELL_TO_CLOSE``,
    ``OPTIONS_EXPIRED``, ``OPTIONS_ASSIGNED``, ``OPTIONS_EXERCISED``

Direction:
    ``OPTIONS_SELL_TO_OPEN`` → ``SHORT``
    ``OPTIONS_BUY_TO_OPEN``  → ``LONG``

Status after matching:
    open_qty > close_qty              → ``OPEN``
    0 < close_qty < open_qty          → ``PARTIALLY_CLOSED``
    close_qty == open_qty (std close) → ``CLOSED``
    terminal close is EXPIRED         → ``EXPIRED``
    terminal close is ASSIGNED        → ``ASSIGNED``
    terminal close is EXERCISED       → ``EXERCISED``

Equity lot rules:
    ``EQUITY_BUY``       → new lot (source=PURCHASE, cost_basis=price)
    ``OPTIONS_ASSIGNED`` → new lot (source=ASSIGNMENT, cost_basis=strike,
                           quantity=contract_qty × 100)
    ``OPTIONS_EXERCISED``→ new lot (source=EXERCISE,  cost_basis=strike,
                           quantity=contract_qty × 100)
    ``EQUITY_SELL``      → FIFO close oldest open lots for same symbol;
                           if sell qty > available qty, exhaust all lots
                           (oversell guard — no crash).

Ignored categories: DIVIDEND, TRANSFER, INTEREST, FEE, JOURNAL, OTHER.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.enums import (
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPositionStatus,
    PositionDirection,
    TransactionCategory,
)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

_OPEN_CATEGORIES: frozenset[TransactionCategory] = frozenset(
    {
        TransactionCategory.OPTIONS_BUY_TO_OPEN,
        TransactionCategory.OPTIONS_SELL_TO_OPEN,
    }
)

_CLOSE_CATEGORIES: frozenset[TransactionCategory] = frozenset(
    {
        TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        TransactionCategory.OPTIONS_SELL_TO_CLOSE,
        TransactionCategory.OPTIONS_EXPIRED,
        TransactionCategory.OPTIONS_ASSIGNED,
        TransactionCategory.OPTIONS_EXERCISED,
    }
)

_TERMINAL_STATUS: dict[TransactionCategory, OptionsPositionStatus] = {
    TransactionCategory.OPTIONS_EXPIRED: OptionsPositionStatus.EXPIRED,
    TransactionCategory.OPTIONS_ASSIGNED: OptionsPositionStatus.ASSIGNED,
    TransactionCategory.OPTIONS_EXERCISED: OptionsPositionStatus.EXERCISED,
}


@dataclass
class TransactionInput:
    """Minimal transaction data needed by the matcher.

    Options-specific fields (``underlying``, ``strike``, ``expiry``,
    ``option_type``) are ``None`` for equity transactions.
    """

    index: int
    category: TransactionCategory
    symbol: str
    quantity: Decimal
    price: Decimal | None
    amount: Decimal
    commission: Decimal
    transaction_date: date
    # Options-specific (None for equity)
    underlying: str | None = None
    strike: Decimal | None = None
    expiry: date | None = None
    option_type: str | None = None  # "CALL" or "PUT"


@dataclass
class MatchedLeg:
    """A single open or close leg attached to a :class:`MatchedPosition`."""

    transaction_index: int
    leg_role: LegRole
    quantity: Decimal


@dataclass
class MatchedPosition:
    """An options position built by the matcher.

    ``legs`` contains both OPEN and CLOSE legs in insertion order.
    The caller (F-12) maps these back to database records.
    """

    underlying: str
    strike: Decimal
    expiry: date
    option_type: str  # "CALL" or "PUT"
    direction: PositionDirection
    status: OptionsPositionStatus
    legs: list[MatchedLeg] = field(default_factory=list)
    realized_pnl: Decimal | None = None


@dataclass
class EquityLot:
    """An equity position lot produced by the matcher."""

    symbol: str
    quantity: Decimal
    cost_basis_per_share: Decimal
    source: EquityPositionSource
    status: EquityPositionStatus = EquityPositionStatus.OPEN
    from_position_index: int | None = None  # index into MatchResult.positions
    close_transaction_index: int | None = None


@dataclass
class MatchResult:
    """The complete output of :func:`match_transactions`."""

    positions: list[MatchedPosition]
    equity_lots: list[EquityLot]


# ---------------------------------------------------------------------------
# Type alias for contract key
# ---------------------------------------------------------------------------

_ContractKey = tuple[str, Decimal, date, str]  # (underlying, strike, expiry, option_type)


def _contract_key(tx: TransactionInput) -> _ContractKey:
    """Build the four-tuple contract identity key from a transaction."""
    assert tx.underlying is not None
    assert tx.strike is not None
    assert tx.expiry is not None
    assert tx.option_type is not None
    return (tx.underlying, tx.strike, tx.expiry, tx.option_type)


def _derive_direction(category: TransactionCategory) -> PositionDirection:
    """Return position direction from an open-leg category."""
    if category == TransactionCategory.OPTIONS_SELL_TO_OPEN:
        return PositionDirection.SHORT
    return PositionDirection.LONG  # OPTIONS_BUY_TO_OPEN


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def match_transactions(
    transactions: list[TransactionInput],
    existing_positions: list[MatchedPosition] | None = None,
    existing_equity_lots: list[EquityLot] | None = None,
) -> MatchResult:
    """FIFO-match a batch of classified transactions into positions and equity lots.

    :param transactions: All classified transactions to process.
    :param existing_positions: Previously persisted (open) positions from
        earlier uploads.  These can receive new close legs from the current
        batch.  Passed by the caller to support cross-upload matching.
    :param existing_equity_lots: Previously persisted open equity lots from
        earlier uploads.  Passed for cross-upload EQUITY_SELL closure.
    :returns: A :class:`MatchResult` containing all affected/new positions
        and equity lots.  The caller is responsible for persistence.
    """
    # Work on a mutable copy of positions and lots so callers retain their
    # original objects unchanged.
    positions: list[MatchedPosition] = list(existing_positions or [])
    equity_lots: list[EquityLot] = list(existing_equity_lots or [])

    # Separate transactions by role (open, close, equity).
    opens = sorted(
        [tx for tx in transactions if tx.category in _OPEN_CATEGORIES],
        key=lambda t: t.transaction_date,
    )
    closes = sorted(
        [tx for tx in transactions if tx.category in _CLOSE_CATEGORIES],
        key=lambda t: t.transaction_date,
    )
    equity_buys = [tx for tx in transactions if tx.category == TransactionCategory.EQUITY_BUY]
    equity_sells = sorted(
        [tx for tx in transactions if tx.category == TransactionCategory.EQUITY_SELL],
        key=lambda t: t.transaction_date,
    )

    # ------------------------------------------------------------------
    # Step 1: Process open legs
    # ------------------------------------------------------------------
    for tx in opens:
        key = _contract_key(tx)
        direction = _derive_direction(tx.category)

        # Look for an existing OPEN position with the same contract key and
        # direction (scale-in path).
        existing = _find_open_position(positions, key, direction)
        if existing is not None:
            existing.legs.append(
                MatchedLeg(
                    transaction_index=tx.index,
                    leg_role=LegRole.OPEN,
                    quantity=tx.quantity,
                )
            )
        else:
            new_pos = MatchedPosition(
                underlying=key[0],
                strike=key[1],
                expiry=key[2],
                option_type=key[3],
                direction=direction,
                status=OptionsPositionStatus.OPEN,
                legs=[
                    MatchedLeg(
                        transaction_index=tx.index,
                        leg_role=LegRole.OPEN,
                        quantity=tx.quantity,
                    )
                ],
            )
            positions.append(new_pos)

    # ------------------------------------------------------------------
    # Step 2: Process close legs (FIFO)
    # ------------------------------------------------------------------
    for tx in closes:
        key = _contract_key(tx)

        # Find open/partially-closed position for this contract (any direction).
        pos = _find_closeable_position(positions, key)
        if pos is None:
            _logger.warning(
                "Close transaction %d has no matching open position for contract %s — skipped.",
                tx.index,
                key,
            )
            continue

        remaining_close_qty = tx.quantity

        # FIFO: consume open legs oldest-first.
        open_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.OPEN]

        for open_leg in open_legs:
            if remaining_close_qty <= Decimal("0"):
                break

            matched_qty = min(open_leg.quantity, remaining_close_qty)
            remaining_close_qty -= matched_qty

            # Add a CLOSE leg for the matched portion.
            pos.legs.append(
                MatchedLeg(
                    transaction_index=tx.index,
                    leg_role=LegRole.CLOSE,
                    quantity=matched_qty,
                )
            )

        # Recompute status.
        _recompute_status(pos, tx.category)

        # Assignment / Exercise → create an equity lot.
        if tx.category in (
            TransactionCategory.OPTIONS_ASSIGNED,
            TransactionCategory.OPTIONS_EXERCISED,
        ):
            source = (
                EquityPositionSource.ASSIGNMENT
                if tx.category == TransactionCategory.OPTIONS_ASSIGNED
                else EquityPositionSource.EXERCISE
            )
            pos_index = positions.index(pos)
            equity_lots.append(
                EquityLot(
                    symbol=pos.underlying,
                    quantity=tx.quantity * Decimal("100"),
                    cost_basis_per_share=pos.strike,
                    source=source,
                    status=EquityPositionStatus.OPEN,
                    from_position_index=pos_index,
                )
            )

    # ------------------------------------------------------------------
    # Step 3: Process equity transactions
    # ------------------------------------------------------------------

    # EQUITY_BUY → new PURCHASE lot.
    for tx in equity_buys:
        assert tx.price is not None
        equity_lots.append(
            EquityLot(
                symbol=tx.symbol,
                quantity=tx.quantity,
                cost_basis_per_share=tx.price,
                source=EquityPositionSource.PURCHASE,
                status=EquityPositionStatus.OPEN,
            )
        )

    # EQUITY_SELL → FIFO close lots for same symbol.
    for tx in equity_sells:
        _apply_equity_sell(equity_lots, tx)

    return MatchResult(positions=positions, equity_lots=equity_lots)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _find_open_position(
    positions: list[MatchedPosition],
    key: _ContractKey,
    direction: PositionDirection,
) -> MatchedPosition | None:
    """Return the first OPEN position matching *key* and *direction*, or None."""
    for pos in positions:
        if (
            (pos.underlying, pos.strike, pos.expiry, pos.option_type) == key
            and pos.direction == direction
            and pos.status == OptionsPositionStatus.OPEN
        ):
            return pos
    return None


def _find_closeable_position(
    positions: list[MatchedPosition],
    key: _ContractKey,
) -> MatchedPosition | None:
    """Return the first OPEN or PARTIALLY_CLOSED position matching *key*, or None."""
    closeable = {OptionsPositionStatus.OPEN, OptionsPositionStatus.PARTIALLY_CLOSED}
    for pos in positions:
        if (
            pos.underlying,
            pos.strike,
            pos.expiry,
            pos.option_type,
        ) == key and pos.status in closeable:
            return pos
    return None


def _recompute_status(
    pos: MatchedPosition,
    close_category: TransactionCategory,
) -> None:
    """Recompute and set *pos.status* after a close leg has been appended.

    Terminal categories (EXPIRED, ASSIGNED, EXERCISED) take precedence over
    CLOSED.  PARTIALLY_CLOSED is used when the position is not yet fully
    consumed.
    """
    total_open_qty = sum(leg.quantity for leg in pos.legs if leg.leg_role == LegRole.OPEN)
    total_close_qty = sum(leg.quantity for leg in pos.legs if leg.leg_role == LegRole.CLOSE)

    if total_close_qty >= total_open_qty:
        # Fully closed — check for terminal category.
        terminal = _TERMINAL_STATUS.get(close_category)
        pos.status = terminal if terminal is not None else OptionsPositionStatus.CLOSED
    else:
        # total_close_qty > 0 is guaranteed here because _recompute_status is
        # only called after appending at least one CLOSE leg.
        pos.status = OptionsPositionStatus.PARTIALLY_CLOSED


def _apply_equity_sell(lots: list[EquityLot], tx: TransactionInput) -> None:
    """Apply FIFO equity lot closure for an EQUITY_SELL transaction.

    :param lots: All equity lots (mutated in-place).
    :param tx: The EQUITY_SELL transaction.
    """
    # Gather open lots for the symbol in FIFO order (creation order = list order).
    open_lots = [
        lot for lot in lots if lot.symbol == tx.symbol and lot.status == EquityPositionStatus.OPEN
    ]

    remaining_sell_qty = tx.quantity

    for lot in open_lots:
        if remaining_sell_qty <= Decimal("0"):
            break

        if lot.quantity <= remaining_sell_qty:
            # Fully close this lot.
            remaining_sell_qty -= lot.quantity
            lot.quantity = lot.quantity  # quantity stays for record; status changes
            lot.status = EquityPositionStatus.CLOSED
            lot.close_transaction_index = tx.index
        else:
            # Partially consume this lot.
            lot.quantity -= remaining_sell_qty
            remaining_sell_qty = Decimal("0")

    if remaining_sell_qty > Decimal("0"):
        # Oversell — log a warning but do not raise.
        _logger.warning(
            "EQUITY_SELL transaction %d: sold %s shares of %s but only %s available. "
            "Oversell guard engaged — remaining sell quantity %s not applied.",
            tx.index,
            tx.quantity,
            tx.symbol,
            tx.quantity - remaining_sell_qty,
            remaining_sell_qty,
        )
