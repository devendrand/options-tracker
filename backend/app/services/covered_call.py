"""Covered call detection service.

Pure functions — no I/O, no database interaction, no side effects.

A short CALL position is considered covered if the user holds at least
100 shares of the underlying equity per open contract.

Rule (from CLAUDE.md §Covered Call Detection):
    Short CALL is covered if user holds >= 100 shares per contract of
    the underlying.

Re-evaluation triggers (handled by the upload orchestrator, not here):
    - EQUITY_BUY
    - OPTIONS_ASSIGNED
    - OPTIONS_EXERCISED
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ShortCallPosition:
    """Minimal data about a short call position needed for coverage evaluation."""

    underlying: str
    option_type: str  # expected value: "CALL"
    direction: str  # expected value: "SHORT"
    quantity: Decimal  # number of contracts


@dataclass
class EquityHolding:
    """Aggregate equity holding for a single symbol.

    Represents the total open shares across all lots for a symbol.
    """

    symbol: str
    total_shares: Decimal  # total open shares across all lots


def _is_short_call(position: ShortCallPosition) -> bool:
    """Return True only when the position is a SHORT CALL.

    Any other combination (LONG CALL, SHORT PUT, LONG PUT) is ineligible
    for covered-call stamping and should always produce False.
    """
    return position.direction == "SHORT" and position.option_type == "CALL"


def is_covered_call(
    position: ShortCallPosition,
    equity_holdings: list[EquityHolding],
) -> bool:
    """Determine if a short call position is covered by sufficient equity.

    A short CALL is covered if the user holds >= 100 shares per contract
    of the underlying symbol.

    Args:
        position: The options position to evaluate.
        equity_holdings: Aggregate equity holdings keyed by symbol.

    Returns:
        True if the position is a SHORT CALL and the user holds at least
        ``position.quantity * 100`` shares of the underlying.
        False in all other cases (wrong direction, wrong option type,
        insufficient shares, or no matching holding).
    """
    if not _is_short_call(position):
        return False

    required_shares: Decimal = position.quantity * Decimal("100")

    # Zero contracts require zero shares — always covered.
    if required_shares == Decimal("0"):
        return True

    for holding in equity_holdings:
        if holding.symbol == position.underlying:
            return holding.total_shares >= required_shares

    # No equity holding found for this underlying — naked position.
    return False


def evaluate_covered_calls(
    short_call_positions: list[ShortCallPosition],
    equity_holdings: list[EquityHolding],
) -> list[tuple[int, bool]]:
    """Evaluate covered call status for a list of positions.

    Each position is evaluated independently against the same
    ``equity_holdings`` snapshot. Positions are not aware of each other —
    two 1-contract SHORT CALLs on the same underlying are each individually
    checked against the total share balance.

    Per CLAUDE.md:
    - Stamped at position-creation time.
    - Re-evaluated after any upload that contains EQUITY_BUY,
      OPTIONS_ASSIGNED, or OPTIONS_EXERCISED transactions.

    Args:
        short_call_positions: List of positions to evaluate (may contain
            non-SHORT-CALL positions; those always yield False).
        equity_holdings: Aggregate equity holdings keyed by symbol.

    Returns:
        List of ``(index, is_covered)`` tuples preserving the original
        list order.  An empty input list produces an empty result.
    """
    return [
        (index, is_covered_call(position, equity_holdings))
        for index, position in enumerate(short_call_positions)
    ]
