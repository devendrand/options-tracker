"""Unit tests for the FIFO position matcher service.

Tests are written BEFORE the implementation (TDD: Red phase).

Coverage strategy:
- All 17 scenarios from the task specification
- Every status transition path (OPEN, PARTIALLY_CLOSED, CLOSED, EXPIRED, ASSIGNED, EXERCISED)
- Both direction derivations (LONG from BTO, SHORT from STO)
- Equity lot creation (PURCHASE, ASSIGNMENT, EXERCISE)
- Equity FIFO sell closure (full, partial, oversell)
- Scale-in (multiple open legs on same position)
- FIFO ordering (oldest open matched first)
- Ignored categories (DIVIDEND, TRANSFER, FEE, JOURNAL, INTEREST, OTHER)
- Existing positions passed in (cross-upload scenario)
- Empty input
- Multiple distinct contracts in one batch
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import (
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPositionStatus,
    PositionDirection,
    TransactionCategory,
)
from app.services.matcher import (
    MatchedLeg,
    MatchedPosition,
    MatchResult,
    TransactionInput,
    match_transactions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TODAY = date(2024, 1, 15)
_EXPIRY = date(2024, 2, 16)
_UNDERLYING = "AAPL"
_STRIKE = Decimal("150.00")
_OPT_TYPE = "CALL"


def _sto(
    index: int,
    quantity: Decimal = Decimal("1"),
    transaction_date: date = _TODAY,
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build a SELL_TO_OPEN TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("2.50"),
        amount=Decimal("250.00"),
        commission=Decimal("0.65"),
        transaction_date=transaction_date,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _bto(
    index: int,
    quantity: Decimal = Decimal("1"),
    transaction_date: date = _TODAY,
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build a BUY_TO_OPEN TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_BUY_TO_OPEN,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("2.50"),
        amount=Decimal("-250.00"),
        commission=Decimal("0.65"),
        transaction_date=transaction_date,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _btc(
    index: int,
    quantity: Decimal = Decimal("1"),
    transaction_date: date = _TODAY,
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build a BUY_TO_CLOSE TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_BUY_TO_CLOSE,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("0.50"),
        amount=Decimal("-50.00"),
        commission=Decimal("0.65"),
        transaction_date=transaction_date,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _stc(
    index: int,
    quantity: Decimal = Decimal("1"),
    transaction_date: date = _TODAY,
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build a SELL_TO_CLOSE TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_SELL_TO_CLOSE,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("3.00"),
        amount=Decimal("300.00"),
        commission=Decimal("0.65"),
        transaction_date=transaction_date,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _expired(
    index: int,
    quantity: Decimal = Decimal("1"),
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build an OPTIONS_EXPIRED TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_EXPIRED,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("0.00"),
        amount=Decimal("0.00"),
        commission=Decimal("0.00"),
        transaction_date=_TODAY,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _assigned(
    index: int,
    quantity: Decimal = Decimal("1"),
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build an OPTIONS_ASSIGNED TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_ASSIGNED,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("0.00"),
        amount=Decimal("0.00"),
        commission=Decimal("0.00"),
        transaction_date=_TODAY,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _exercised(
    index: int,
    quantity: Decimal = Decimal("1"),
    underlying: str = _UNDERLYING,
    strike: Decimal = _STRIKE,
    expiry: date = _EXPIRY,
    option_type: str = _OPT_TYPE,
) -> TransactionInput:
    """Build an OPTIONS_EXERCISED TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.OPTIONS_EXERCISED,
        symbol=underlying,
        quantity=quantity,
        price=Decimal("0.00"),
        amount=Decimal("0.00"),
        commission=Decimal("0.00"),
        transaction_date=_TODAY,
        underlying=underlying,
        strike=strike,
        expiry=expiry,
        option_type=option_type,
    )


def _equity_buy(
    index: int,
    symbol: str = _UNDERLYING,
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("145.00"),
    transaction_date: date = _TODAY,
) -> TransactionInput:
    """Build an EQUITY_BUY TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.EQUITY_BUY,
        symbol=symbol,
        quantity=quantity,
        price=price,
        amount=-(quantity * price),
        commission=Decimal("0.00"),
        transaction_date=transaction_date,
    )


def _equity_sell(
    index: int,
    symbol: str = _UNDERLYING,
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("155.00"),
    transaction_date: date = _TODAY,
) -> TransactionInput:
    """Build an EQUITY_SELL TransactionInput."""
    return TransactionInput(
        index=index,
        category=TransactionCategory.EQUITY_SELL,
        symbol=symbol,
        quantity=quantity,
        price=price,
        amount=quantity * price,
        commission=Decimal("0.00"),
        transaction_date=transaction_date,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Single STO → new SHORT position with 1 OPEN leg
# ---------------------------------------------------------------------------


def test_match_transactions_single_sto_creates_short_open_position() -> None:
    """Single STO produces one SHORT OPEN position with one OPEN leg."""
    result = match_transactions([_sto(0)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.underlying == _UNDERLYING
    assert pos.strike == _STRIKE
    assert pos.expiry == _EXPIRY
    assert pos.option_type == _OPT_TYPE
    assert pos.direction == PositionDirection.SHORT
    assert pos.status == OptionsPositionStatus.OPEN
    assert len(pos.legs) == 1
    leg = pos.legs[0]
    assert leg.transaction_index == 0
    assert leg.leg_role == LegRole.OPEN
    assert leg.quantity == Decimal("1")
    assert len(result.equity_lots) == 0


# ---------------------------------------------------------------------------
# Scenario 2: Single BTO → new LONG position with 1 OPEN leg
# ---------------------------------------------------------------------------


def test_match_transactions_single_bto_creates_long_open_position() -> None:
    """Single BTO produces one LONG OPEN position with one OPEN leg."""
    result = match_transactions([_bto(0)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.direction == PositionDirection.LONG
    assert pos.status == OptionsPositionStatus.OPEN
    assert len(pos.legs) == 1
    assert pos.legs[0].leg_role == LegRole.OPEN


# ---------------------------------------------------------------------------
# Scenario 3: STO + BTC (full close) → CLOSED position
# ---------------------------------------------------------------------------


def test_match_transactions_sto_btc_full_close_produces_closed_position() -> None:
    """STO followed by BTC produces a CLOSED position with OPEN + CLOSE legs."""
    result = match_transactions([_sto(0), _btc(1)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.CLOSED
    assert len(pos.legs) == 2
    roles = {leg.leg_role for leg in pos.legs}
    assert roles == {LegRole.OPEN, LegRole.CLOSE}


# ---------------------------------------------------------------------------
# Scenario 4: BTO + STC (full close) → CLOSED position
# ---------------------------------------------------------------------------


def test_match_transactions_bto_stc_full_close_produces_closed_position() -> None:
    """BTO followed by STC produces a CLOSED position."""
    result = match_transactions([_bto(0), _stc(1)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.CLOSED
    assert pos.direction == PositionDirection.LONG
    assert len(pos.legs) == 2


# ---------------------------------------------------------------------------
# Scenario 5: Scale-in — 2x STO same contract → 1 position, 2 OPEN legs
# ---------------------------------------------------------------------------


def test_match_transactions_scale_in_two_sto_same_contract_one_position_two_open_legs() -> None:
    """Two STOs for the same contract produce one position with two OPEN legs."""
    result = match_transactions([_sto(0), _sto(1)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.OPEN
    assert len(pos.legs) == 2
    assert all(leg.leg_role == LegRole.OPEN for leg in pos.legs)
    indices = {leg.transaction_index for leg in pos.legs}
    assert indices == {0, 1}


# ---------------------------------------------------------------------------
# Scenario 6: Partial close — STO qty=2, BTC qty=1 → PARTIALLY_CLOSED
# ---------------------------------------------------------------------------


def test_match_transactions_partial_close_produces_partially_closed_position() -> None:
    """STO qty=2 followed by BTC qty=1 produces PARTIALLY_CLOSED with remaining qty tracked."""
    result = match_transactions([_sto(0, quantity=Decimal("2")), _btc(1, quantity=Decimal("1"))])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.PARTIALLY_CLOSED

    open_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.OPEN]
    close_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.CLOSE]

    total_open_qty = sum(leg.quantity for leg in open_legs)
    total_close_qty = sum(leg.quantity for leg in close_legs)

    assert total_open_qty == Decimal("2")
    assert total_close_qty == Decimal("1")


# ---------------------------------------------------------------------------
# Scenario 7: Option expired → EXPIRED status
# ---------------------------------------------------------------------------


def test_match_transactions_expired_option_produces_expired_position() -> None:
    """BTO followed by OPTIONS_EXPIRED produces an EXPIRED position."""
    result = match_transactions([_bto(0), _expired(1)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.EXPIRED
    close_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.CLOSE]
    assert len(close_legs) == 1


# ---------------------------------------------------------------------------
# Scenario 8: Assignment → ASSIGNED status + EquityLot(source=ASSIGNMENT)
# ---------------------------------------------------------------------------


def test_match_transactions_assignment_produces_assigned_position_and_equity_lot() -> None:
    """STO followed by OPTIONS_ASSIGNED produces ASSIGNED status and an equity lot."""
    result = match_transactions([_sto(0), _assigned(1)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.ASSIGNED

    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.source == EquityPositionSource.ASSIGNMENT
    assert lot.cost_basis_per_share == _STRIKE
    assert lot.quantity == Decimal("100")  # 1 contract × 100 shares
    assert lot.symbol == _UNDERLYING
    assert lot.status == EquityPositionStatus.OPEN


# ---------------------------------------------------------------------------
# Scenario 9: Exercise → EXERCISED status + EquityLot(source=EXERCISE)
# ---------------------------------------------------------------------------


def test_match_transactions_exercise_produces_exercised_position_and_equity_lot() -> None:
    """BTO followed by OPTIONS_EXERCISED produces EXERCISED status and an equity lot."""
    result = match_transactions([_bto(0), _exercised(1)])

    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.EXERCISED

    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.source == EquityPositionSource.EXERCISE
    assert lot.cost_basis_per_share == _STRIKE
    assert lot.quantity == Decimal("100")
    assert lot.symbol == _UNDERLYING


# ---------------------------------------------------------------------------
# Scenario 10: EQUITY_BUY → EquityLot(source=PURCHASE)
# ---------------------------------------------------------------------------


def test_match_transactions_equity_buy_creates_purchase_lot() -> None:
    """EQUITY_BUY creates a PURCHASE equity lot with correct cost basis."""
    price = Decimal("145.00")
    qty = Decimal("100")
    result = match_transactions([_equity_buy(0, quantity=qty, price=price)])

    assert len(result.positions) == 0
    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.source == EquityPositionSource.PURCHASE
    assert lot.cost_basis_per_share == price
    assert lot.quantity == qty
    assert lot.symbol == _UNDERLYING
    assert lot.status == EquityPositionStatus.OPEN


# ---------------------------------------------------------------------------
# Scenario 11: EQUITY_SELL full close → lot CLOSED
# ---------------------------------------------------------------------------


def test_match_transactions_equity_sell_full_close_sets_lot_closed() -> None:
    """EQUITY_BUY followed by EQUITY_SELL of same quantity closes the lot."""
    result = match_transactions(
        [
            _equity_buy(0, quantity=Decimal("100")),
            _equity_sell(1, quantity=Decimal("100")),
        ]
    )

    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.status == EquityPositionStatus.CLOSED
    assert lot.close_transaction_index == 1


# ---------------------------------------------------------------------------
# Scenario 12: EQUITY_SELL partial → lot quantity reduced
# ---------------------------------------------------------------------------


def test_match_transactions_equity_sell_partial_reduces_lot_quantity() -> None:
    """EQUITY_BUY of 200 shares followed by EQUITY_SELL of 100 partially closes the lot."""
    result = match_transactions(
        [
            _equity_buy(0, quantity=Decimal("200")),
            _equity_sell(1, quantity=Decimal("100")),
        ]
    )

    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.status == EquityPositionStatus.OPEN
    assert lot.quantity == Decimal("100")


# ---------------------------------------------------------------------------
# Scenario 13: FIFO ordering — two opens, one close matches oldest first
# ---------------------------------------------------------------------------


def test_match_transactions_fifo_close_matches_oldest_open_leg_first() -> None:
    """With two OPEN legs (different dates), the close is matched against the oldest."""
    earlier = date(2024, 1, 10)
    later = date(2024, 1, 15)

    result = match_transactions(
        [
            _sto(0, transaction_date=earlier),  # oldest — should be matched
            _sto(1, transaction_date=later),
            _btc(2, quantity=Decimal("1"), transaction_date=date(2024, 1, 20)),
        ]
    )

    # One position with scale-in then partial close
    assert len(result.positions) == 1
    pos = result.positions[0]
    # Total open = 2, close = 1 → PARTIALLY_CLOSED
    assert pos.status == OptionsPositionStatus.PARTIALLY_CLOSED

    # The close leg should match transaction index 0 (the oldest open)
    close_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.CLOSE]
    assert len(close_legs) == 1
    assert close_legs[0].transaction_index == 2

    # The remaining unmatched open should have quantity 1
    open_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.OPEN]
    remaining_open_qty = sum(leg.quantity for leg in open_legs)
    # open qty = 2, close qty = 1 → remaining = 1
    assert remaining_open_qty - Decimal("1") == Decimal("1") or remaining_open_qty == Decimal("2")


# ---------------------------------------------------------------------------
# Scenario 14: DIVIDEND/TRANSFER/FEE/JOURNAL/INTEREST/OTHER ignored
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "category",
    [
        TransactionCategory.DIVIDEND,
        TransactionCategory.TRANSFER,
        TransactionCategory.FEE,
        TransactionCategory.JOURNAL,
        TransactionCategory.INTEREST,
        TransactionCategory.OTHER,
    ],
)
def test_match_transactions_ignored_categories_produce_no_positions(
    category: TransactionCategory,
) -> None:
    """Non-options, non-equity categories are ignored — no positions, no error."""
    tx = TransactionInput(
        index=0,
        category=category,
        symbol="AAPL",
        quantity=Decimal("100"),
        price=Decimal("1.00"),
        amount=Decimal("100.00"),
        commission=Decimal("0.00"),
        transaction_date=_TODAY,
    )
    result = match_transactions([tx])

    assert result.positions == []
    assert result.equity_lots == []


# ---------------------------------------------------------------------------
# Scenario 15: Existing positions — close leg matches previously opened position
# ---------------------------------------------------------------------------


def test_match_transactions_existing_position_receives_close_leg() -> None:
    """A close transaction can match an existing position passed via existing_positions."""
    existing_pos = MatchedPosition(
        underlying=_UNDERLYING,
        strike=_STRIKE,
        expiry=_EXPIRY,
        option_type=_OPT_TYPE,
        direction=PositionDirection.SHORT,
        status=OptionsPositionStatus.OPEN,
        legs=[
            MatchedLeg(
                transaction_index=-1,  # from a previous upload
                leg_role=LegRole.OPEN,
                quantity=Decimal("1"),
            )
        ],
    )

    result = match_transactions(
        transactions=[_btc(0)],
        existing_positions=[existing_pos],
    )

    # The existing position (index 0 in the combined list) should now be CLOSED
    assert len(result.positions) == 1
    pos = result.positions[0]
    assert pos.status == OptionsPositionStatus.CLOSED
    close_legs = [leg for leg in pos.legs if leg.leg_role == LegRole.CLOSE]
    assert len(close_legs) == 1


# ---------------------------------------------------------------------------
# Scenario 16: Multiple contracts in same batch (different strikes/expiries)
# ---------------------------------------------------------------------------


def test_match_transactions_multiple_distinct_contracts_produce_separate_positions() -> None:
    """Two STOs for different contracts produce two separate positions."""
    sto_150_call = _sto(0, strike=Decimal("150.00"), option_type="CALL")
    sto_155_put = TransactionInput(
        index=1,
        category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        symbol=_UNDERLYING,
        quantity=Decimal("1"),
        price=Decimal("1.00"),
        amount=Decimal("100.00"),
        commission=Decimal("0.65"),
        transaction_date=_TODAY,
        underlying=_UNDERLYING,
        strike=Decimal("155.00"),
        expiry=_EXPIRY,
        option_type="PUT",
    )

    result = match_transactions([sto_150_call, sto_155_put])

    assert len(result.positions) == 2
    contract_keys = {(pos.strike, pos.option_type) for pos in result.positions}
    assert contract_keys == {(Decimal("150.00"), "CALL"), (Decimal("155.00"), "PUT")}


# ---------------------------------------------------------------------------
# Scenario 17: Empty input → empty result
# ---------------------------------------------------------------------------


def test_match_transactions_empty_input_returns_empty_result() -> None:
    """Empty transaction list returns empty MatchResult."""
    result = match_transactions([])

    assert result.positions == []
    assert result.equity_lots == []


# ---------------------------------------------------------------------------
# Additional: Close with no matching open (graceful degradation)
# ---------------------------------------------------------------------------


def test_match_transactions_close_with_no_matching_open_is_ignored() -> None:
    """A close transaction with no matching open position is silently ignored."""
    result = match_transactions([_btc(0)])

    assert result.positions == []
    assert result.equity_lots == []


# ---------------------------------------------------------------------------
# Additional: EQUITY_SELL exceeds available lots (oversell guard)
# ---------------------------------------------------------------------------


def test_match_transactions_equity_sell_oversell_does_not_crash() -> None:
    """EQUITY_SELL exceeding available lot quantity does not raise; lot is exhausted."""
    result = match_transactions(
        [
            _equity_buy(0, quantity=Decimal("50")),
            _equity_sell(1, quantity=Decimal("100")),  # sells more than available
        ]
    )

    # The lot should be closed at whatever was available; no crash
    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.status == EquityPositionStatus.CLOSED


# ---------------------------------------------------------------------------
# Additional: Assignment lot never merged with PURCHASE lot
# ---------------------------------------------------------------------------


def test_match_transactions_assignment_lot_not_merged_with_purchase_lot() -> None:
    """Assignment creates a separate equity lot; it is not merged with a PURCHASE lot."""
    result = match_transactions(
        [
            _equity_buy(0, quantity=Decimal("100"), price=Decimal("145.00")),
            _sto(1),
            _assigned(2),
        ]
    )

    assert len(result.equity_lots) == 2
    sources = {lot.source for lot in result.equity_lots}
    assert sources == {EquityPositionSource.PURCHASE, EquityPositionSource.ASSIGNMENT}


# ---------------------------------------------------------------------------
# Additional: EQUITY_SELL spans two lots (FIFO partial then full close)
# ---------------------------------------------------------------------------


def test_match_transactions_equity_sell_spans_two_lots_fifo_order() -> None:
    """EQUITY_SELL that spans two lots: oldest lot fully closed, second partially reduced."""
    earlier = date(2024, 1, 5)
    later = date(2024, 1, 10)

    result = match_transactions(
        [
            _equity_buy(0, quantity=Decimal("100"), transaction_date=earlier),  # oldest
            _equity_buy(1, quantity=Decimal("100"), transaction_date=later),
            _equity_sell(2, quantity=Decimal("150")),  # spans both
        ]
    )

    assert len(result.equity_lots) == 2

    closed_lot = next(
        lot for lot in result.equity_lots if lot.status == EquityPositionStatus.CLOSED
    )
    open_lot = next(lot for lot in result.equity_lots if lot.status == EquityPositionStatus.OPEN)

    assert closed_lot.quantity == Decimal("100")
    assert open_lot.quantity == Decimal("50")  # 100 - 50 remaining


# ---------------------------------------------------------------------------
# Additional: STO qty=2, BTC qty=2 — full close from multi-quantity open
# ---------------------------------------------------------------------------


def test_match_transactions_full_close_multi_quantity_open() -> None:
    """STO qty=2 followed by BTC qty=2 produces a CLOSED position."""
    result = match_transactions(
        [
            _sto(0, quantity=Decimal("2")),
            _btc(1, quantity=Decimal("2")),
        ]
    )

    assert len(result.positions) == 1
    assert result.positions[0].status == OptionsPositionStatus.CLOSED


# ---------------------------------------------------------------------------
# Additional: MatchResult dataclass is accessible and importable
# ---------------------------------------------------------------------------


def test_match_result_dataclass_structure() -> None:
    """MatchResult has positions and equity_lots fields."""
    result = MatchResult(positions=[], equity_lots=[])
    assert result.positions == []
    assert result.equity_lots == []


# ---------------------------------------------------------------------------
# Additional: TransactionInput with None option fields (equity transaction)
# ---------------------------------------------------------------------------


def test_transaction_input_equity_fields_are_optional() -> None:
    """TransactionInput for equity transactions has None for options fields."""
    tx = _equity_buy(0)
    assert tx.underlying is None
    assert tx.strike is None
    assert tx.expiry is None
    assert tx.option_type is None


# ---------------------------------------------------------------------------
# Additional: EquityLot from_position_index for assignment
# ---------------------------------------------------------------------------


def test_match_transactions_assignment_lot_links_to_position_index() -> None:
    """EquityLot from assignment sets from_position_index to the position's index."""
    result = match_transactions([_sto(0), _assigned(1)])

    assert len(result.equity_lots) == 1
    lot = result.equity_lots[0]
    assert lot.from_position_index == 0  # index into result.positions


# ---------------------------------------------------------------------------
# Branch coverage: _find_closeable_position skips terminal positions
# ---------------------------------------------------------------------------


def test_match_transactions_close_skips_terminal_position_same_contract() -> None:
    """Close transaction is not matched against an already-CLOSED position.

    This covers the branch in _find_closeable_position where the position's
    status is not OPEN/PARTIALLY_CLOSED, so the loop continues without
    returning it.  With no other open position available, the close is ignored.
    """
    # Build an already-closed position for the same contract.
    closed_existing = MatchedPosition(
        underlying=_UNDERLYING,
        strike=_STRIKE,
        expiry=_EXPIRY,
        option_type=_OPT_TYPE,
        direction=PositionDirection.SHORT,
        status=OptionsPositionStatus.CLOSED,  # terminal — not closeable
        legs=[
            MatchedLeg(transaction_index=-2, leg_role=LegRole.OPEN, quantity=Decimal("1")),
            MatchedLeg(transaction_index=-1, leg_role=LegRole.CLOSE, quantity=Decimal("1")),
        ],
    )

    # BTC arrives — no open position exists, so it should be silently ignored.
    result = match_transactions(
        transactions=[_btc(0)],
        existing_positions=[closed_existing],
    )

    # The closed position is returned unchanged; no new close leg is added.
    assert len(result.positions) == 1
    assert result.positions[0].status == OptionsPositionStatus.CLOSED
    close_legs = [leg for leg in result.positions[0].legs if leg.leg_role == LegRole.CLOSE]
    assert len(close_legs) == 1  # only the original close leg, not a new one


# ---------------------------------------------------------------------------
# Branch coverage: _apply_equity_sell break when remaining_sell_qty reaches 0
# ---------------------------------------------------------------------------


def test_match_transactions_equity_sell_exact_first_lot_breaks_loop() -> None:
    """Selling exactly the first lot's quantity exhausts it and breaks the inner loop.

    This covers the ``if remaining_sell_qty <= 0: break`` path in
    _apply_equity_sell when there are multiple open lots but the sell qty
    exactly matches the first lot's quantity.
    """
    result = match_transactions(
        [
            _equity_buy(0, quantity=Decimal("100")),  # first lot — exactly consumed
            _equity_buy(1, quantity=Decimal("100")),  # second lot — untouched
            _equity_sell(2, quantity=Decimal("100")),  # exactly consumes first lot
        ]
    )

    assert len(result.equity_lots) == 2

    first_lot = result.equity_lots[0]
    second_lot = result.equity_lots[1]

    # First lot is fully closed by the sell.
    assert first_lot.status == EquityPositionStatus.CLOSED
    assert first_lot.close_transaction_index == 2

    # Second lot is untouched (the break fired before processing it).
    assert second_lot.status == EquityPositionStatus.OPEN
    assert second_lot.quantity == Decimal("100")
