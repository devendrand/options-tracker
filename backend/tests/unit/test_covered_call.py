"""Unit tests for the covered call detection service.

Tests are written BEFORE the implementation (TDD: Red phase).

Coverage strategy:
- is_covered_call: short CALL with/without sufficient shares
- is_covered_call: boundary conditions (exactly 100 shares, 99 shares)
- is_covered_call: multiple contracts require proportionally more shares
- is_covered_call: non-SHORT-CALL positions always return False
- is_covered_call: no matching equity holding returns False
- is_covered_call: fractional shares above threshold
- evaluate_covered_calls: evaluates each position independently
- evaluate_covered_calls: empty inputs produce empty output
- evaluate_covered_calls: returns correct (index, bool) tuples
"""

from __future__ import annotations

from decimal import Decimal

from app.services.covered_call import (
    EquityHolding,
    ShortCallPosition,
    evaluate_covered_calls,
    is_covered_call,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _short_call(
    underlying: str = "AAPL",
    quantity: Decimal = Decimal("1"),
) -> ShortCallPosition:
    """Return a SHORT CALL position for the given underlying."""
    return ShortCallPosition(
        underlying=underlying,
        option_type="CALL",
        direction="SHORT",
        quantity=quantity,
    )


def _long_call(underlying: str = "AAPL") -> ShortCallPosition:
    """Return a LONG CALL position (not eligible for covered-call)."""
    return ShortCallPosition(
        underlying=underlying,
        option_type="CALL",
        direction="LONG",
        quantity=Decimal("1"),
    )


def _short_put(underlying: str = "AAPL") -> ShortCallPosition:
    """Return a SHORT PUT position (not eligible for covered-call)."""
    return ShortCallPosition(
        underlying=underlying,
        option_type="PUT",
        direction="SHORT",
        quantity=Decimal("1"),
    )


def _holding(symbol: str, shares: Decimal) -> EquityHolding:
    return EquityHolding(symbol=symbol, total_shares=shares)


# ---------------------------------------------------------------------------
# is_covered_call — basic coverage scenarios
# ---------------------------------------------------------------------------


class TestIsCoveredCall:
    """Tests for is_covered_call()."""

    def test_short_call_with_enough_shares_returns_true(self) -> None:
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("AAPL", Decimal("100"))]
        assert is_covered_call(position, holdings) is True

    def test_short_call_with_more_than_enough_shares_returns_true(self) -> None:
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("AAPL", Decimal("200"))]
        assert is_covered_call(position, holdings) is True

    def test_short_call_without_enough_shares_returns_false(self) -> None:
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("AAPL", Decimal("50"))]
        assert is_covered_call(position, holdings) is False

    def test_short_call_with_no_equity_holding_returns_false(self) -> None:
        position = _short_call("AAPL", Decimal("1"))
        assert is_covered_call(position, []) is False

    def test_short_call_equity_holding_for_different_symbol_returns_false(self) -> None:
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("NVDA", Decimal("500"))]
        assert is_covered_call(position, holdings) is False

    # --- multi-contract scenarios ---

    def test_two_contracts_with_200_shares_returns_true(self) -> None:
        position = _short_call("AAPL", Decimal("2"))
        holdings = [_holding("AAPL", Decimal("200"))]
        assert is_covered_call(position, holdings) is True

    def test_two_contracts_with_150_shares_returns_false(self) -> None:
        """2 contracts require 200 shares; 150 is insufficient."""
        position = _short_call("AAPL", Decimal("2"))
        holdings = [_holding("AAPL", Decimal("150"))]
        assert is_covered_call(position, holdings) is False

    # --- boundary conditions ---

    def test_one_contract_exactly_100_shares_returns_true(self) -> None:
        """Boundary: exactly 100 shares covers exactly 1 contract."""
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("AAPL", Decimal("100"))]
        assert is_covered_call(position, holdings) is True

    def test_one_contract_99_shares_returns_false(self) -> None:
        """Boundary: 99 shares is one short of covering 1 contract."""
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("AAPL", Decimal("99"))]
        assert is_covered_call(position, holdings) is False

    # --- fractional shares ---

    def test_fractional_shares_above_threshold_returns_true(self) -> None:
        """100.5 shares covers 1 contract (>= 100)."""
        position = _short_call("AAPL", Decimal("1"))
        holdings = [_holding("AAPL", Decimal("100.5"))]
        assert is_covered_call(position, holdings) is True

    # --- non-SHORT-CALL positions ---

    def test_long_call_always_returns_false(self) -> None:
        """LONG CALL is not eligible for covered-call stamping."""
        position = _long_call("AAPL")
        holdings = [_holding("AAPL", Decimal("1000"))]
        assert is_covered_call(position, holdings) is False

    def test_short_put_always_returns_false(self) -> None:
        """SHORT PUT is not a covered call regardless of equity held."""
        position = _short_put("AAPL")
        holdings = [_holding("AAPL", Decimal("1000"))]
        assert is_covered_call(position, holdings) is False

    def test_long_put_always_returns_false(self) -> None:
        """LONG PUT is never a covered call."""
        position = ShortCallPosition(
            underlying="AAPL",
            option_type="PUT",
            direction="LONG",
            quantity=Decimal("1"),
        )
        holdings = [_holding("AAPL", Decimal("1000"))]
        assert is_covered_call(position, holdings) is False


# ---------------------------------------------------------------------------
# evaluate_covered_calls — batch evaluation
# ---------------------------------------------------------------------------


class TestEvaluateCoveredCalls:
    """Tests for evaluate_covered_calls()."""

    def test_empty_positions_returns_empty_list(self) -> None:
        result = evaluate_covered_calls([], [_holding("AAPL", Decimal("100"))])
        assert result == []

    def test_empty_holdings_all_positions_uncovered(self) -> None:
        positions = [_short_call("AAPL"), _short_call("NVDA")]
        result = evaluate_covered_calls(positions, [])
        assert result == [(0, False), (1, False)]

    def test_single_covered_position_returns_true(self) -> None:
        positions = [_short_call("AAPL", Decimal("1"))]
        holdings = [_holding("AAPL", Decimal("100"))]
        result = evaluate_covered_calls(positions, holdings)
        assert result == [(0, True)]

    def test_single_uncovered_position_returns_false(self) -> None:
        positions = [_short_call("AAPL", Decimal("1"))]
        holdings = [_holding("AAPL", Decimal("50"))]
        result = evaluate_covered_calls(positions, holdings)
        assert result == [(0, False)]

    def test_multiple_positions_different_underlyings_evaluated_independently(
        self,
    ) -> None:
        """Each position is evaluated against its own underlying's holding."""
        positions = [
            _short_call("AAPL", Decimal("1")),
            _short_call("NVDA", Decimal("1")),
        ]
        holdings = [
            _holding("AAPL", Decimal("100")),
            _holding("NVDA", Decimal("50")),
        ]
        result = evaluate_covered_calls(positions, holdings)
        assert result == [(0, True), (1, False)]

    def test_multiple_positions_same_underlying_each_checked_independently(
        self,
    ) -> None:
        """Two 1-contract SHORT CALLs on the same underlying are each
        independently evaluated against total_shares.  If total_shares >= 100
        both are covered, because each position individually needs only 100
        shares (not 200 combined)."""
        positions = [
            _short_call("AAPL", Decimal("1")),
            _short_call("AAPL", Decimal("1")),
        ]
        holdings = [_holding("AAPL", Decimal("100"))]
        result = evaluate_covered_calls(positions, holdings)
        # Each position independently sees 100 shares >= 100 required
        assert result == [(0, True), (1, True)]

    def test_non_short_call_positions_in_batch_return_false(self) -> None:
        """Mixed batch: long call and short put positions are always False."""
        positions = [
            _long_call("AAPL"),
            _short_put("AAPL"),
            _short_call("AAPL", Decimal("1")),
        ]
        holdings = [_holding("AAPL", Decimal("1000"))]
        result = evaluate_covered_calls(positions, holdings)
        assert result == [(0, False), (1, False), (2, True)]

    def test_indices_in_result_match_input_list_order(self) -> None:
        """Result tuples preserve the original list index."""
        positions = [
            _short_call("AAPL", Decimal("2")),  # needs 200 — uncovered with 100
            _short_call("NVDA", Decimal("1")),  # needs 100 — covered with 100
            _short_call("MSFT", Decimal("1")),  # no holding — uncovered
        ]
        holdings = [
            _holding("AAPL", Decimal("100")),
            _holding("NVDA", Decimal("100")),
        ]
        result = evaluate_covered_calls(positions, holdings)
        assert result == [(0, False), (1, True), (2, False)]

    def test_zero_quantity_position_requires_zero_shares_covered(self) -> None:
        """A position with 0 contracts requires 0 shares — always covered."""
        position = ShortCallPosition(
            underlying="AAPL",
            option_type="CALL",
            direction="SHORT",
            quantity=Decimal("0"),
        )
        result = evaluate_covered_calls([position], [])
        # 0 * 100 = 0 required; 0 shares >= 0 → True
        assert result == [(0, True)]
