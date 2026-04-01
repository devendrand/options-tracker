"""Upload processing orchestrator — coordinates the full CSV pipeline.

Pipeline: parse → classify → (persist raw + classified) → dedup → match → P&L
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    EquityPositionStatus,
    LegRole,
    OptionType,
    OptionsPositionStatus,
    PositionDirection,
    RawTransactionStatus,
    TransactionCategory,
    TransactionStatus,
)
from app.models.equity_position import EquityPosition
from app.models.options_position import OptionsPosition
from app.models.options_position_leg import OptionsPositionLeg
from app.models.raw_transaction import RawTransaction
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.services.classifier import classify_transaction
from app.services.covered_call import EquityHolding, ShortCallPosition, evaluate_covered_calls
from app.services.deduplicator import deduplicate_rows
from app.services.matcher import MatchResult, TransactionInput, match_transactions
from app.services.parser.etrade import ParsedRow, parse_etrade_csv
from app.services.pnl import LegData, calculate_options_pnl


@dataclass
class UploadResult:
    """Summary statistics from a completed upload pipeline run."""

    upload: Upload
    rows_parsed: int
    options_count: int
    duplicate_count: int
    possible_duplicate_count: int
    parse_error_count: int
    internal_transfer_count: int


async def process_upload(
    session: AsyncSession,
    *,
    filename: str,
    csv_content: str,
) -> UploadResult:
    """Run the full upload pipeline and return summary stats.

    Steps:
    1. Parse CSV into ParsedRow list
    2. Classify each row
    3. Deduplicate against existing transactions
    4. Persist RawTransaction + Transaction records
    5. Update Upload record with stats
    6. Run FIFO position matching
    7. Calculate P&L for closed positions
    8. Detect covered calls
    """
    # Step 1: Parse
    parsed_rows = parse_etrade_csv(csv_content)

    # Step 2: Classify
    categories: list[TransactionCategory] = [classify_transaction(row) for row in parsed_rows]

    # Step 3: Deduplicate (get existing transaction data for dedup)
    existing_txns = await _fetch_existing_transactions(session)
    dedup_results = deduplicate_rows(parsed_rows, existing_txns)

    # Step 4: Create Upload record
    options_count = sum(1 for cat in categories if cat.value.startswith("OPTIONS_"))
    internal_transfer_count = sum(
        1
        for row in parsed_rows
        if row.activity_type.strip().lower() == "transfer"
        and row.description.upper().startswith("TRNSFR")
    )
    duplicate_count = sum(1 for dr in dedup_results if dr.status == RawTransactionStatus.DUPLICATE)
    possible_duplicate_count = sum(
        1 for dr in dedup_results if dr.status == RawTransactionStatus.POSSIBLE_DUPLICATE
    )

    upload = Upload(
        filename=filename,
        broker="etrade",
        row_count=len(parsed_rows),
        options_count=options_count,
        duplicate_count=duplicate_count,
        possible_duplicate_count=possible_duplicate_count,
        parse_error_count=0,
        internal_transfer_count=internal_transfer_count,
    )
    session.add(upload)
    await session.flush()

    # Step 5: Persist RawTransaction + Transaction for each non-duplicate row
    # active_txns tracks (row_index, Transaction) for all ACTIVE rows, used by the matcher.
    active_txns: list[tuple[int, Transaction]] = []

    for i, row in enumerate(parsed_rows):
        is_transfer = (
            row.activity_type.strip().lower() == "transfer"
            and row.description.upper().startswith("TRNSFR")
        )
        raw_status = dedup_results[i].status
        raw_txn = RawTransaction(
            upload_id=upload.id,
            raw_data=row.raw_data,
            is_internal_transfer=is_transfer,
            status=raw_status,
        )
        session.add(raw_txn)
        await session.flush()

        if raw_status == RawTransactionStatus.ACTIVE:
            txn = Transaction(
                raw_transaction_id=raw_txn.id,
                upload_id=upload.id,
                broker_name="etrade",
                trade_date=row.trade_date or row.transaction_date,
                transaction_date=row.transaction_date,
                settlement_date=row.settlement_date,
                symbol=row.symbol or "",
                option_symbol=_build_option_symbol(row),
                strike=row.strike,
                expiry=row.expiry,
                option_type=row.option_type,
                action=row.activity_type,
                description=row.description,
                quantity=row.quantity or Decimal("0"),
                price=row.price,
                commission=row.commission,
                amount=row.amount or Decimal("0"),
                category=categories[i],
            )
            session.add(txn)
            active_txns.append((i, txn))

    await session.flush()

    # Steps 6–8: Match positions, calculate P&L, detect covered calls.
    if active_txns:
        tx_inputs = _build_transaction_inputs(active_txns, categories)
        match_result = match_transactions(tx_inputs)
        await _persist_match_result(session, match_result, active_txns)

    await session.refresh(upload)

    return UploadResult(
        upload=upload,
        rows_parsed=len(parsed_rows),
        options_count=options_count,
        duplicate_count=duplicate_count,
        possible_duplicate_count=possible_duplicate_count,
        parse_error_count=0,
        internal_transfer_count=internal_transfer_count,
    )


def _build_option_symbol(row: ParsedRow) -> str | None:
    """Build an option symbol string if the row represents an option."""
    if not row.is_option:
        return None
    parts = [
        row.underlying or "",
        str(row.expiry) if row.expiry else "",
        row.option_type or "",
        str(row.strike) if row.strike else "",
    ]
    return " ".join(p for p in parts if p)


def _build_transaction_inputs(
    active_txns: list[tuple[int, Transaction]],
    categories: list[TransactionCategory],
) -> list[TransactionInput]:
    """Build TransactionInput list from persisted active transactions.

    :param active_txns: (row_index, Transaction) pairs for every ACTIVE row.
    :param categories: Full category list indexed by original row position.
    :returns: TransactionInput list using local index (position in active_txns).
    """
    result: list[TransactionInput] = []
    for local_idx, (row_index, txn) in enumerate(active_txns):
        category = categories[row_index]
        is_options = category.value.startswith("OPTIONS_")

        # option_type may be a str (freshly constructed) or OptionType enum (from DB).
        ot = txn.option_type
        if ot is None:
            option_type_str: str | None = None
        elif isinstance(ot, OptionType):
            option_type_str = ot.value
        else:
            option_type_str = str(ot)

        result.append(
            TransactionInput(
                index=local_idx,
                category=category,
                symbol=txn.symbol,
                quantity=txn.quantity,
                price=txn.price,
                amount=txn.amount,
                commission=txn.commission,
                transaction_date=txn.transaction_date,
                underlying=txn.symbol if is_options else None,
                strike=txn.strike if is_options else None,
                expiry=txn.expiry if is_options else None,
                option_type=option_type_str if is_options else None,
            )
        )
    return result


async def _persist_match_result(
    session: AsyncSession,
    match_result: MatchResult,
    active_txns: list[tuple[int, Transaction]],
) -> None:
    """Persist MatchResult to the session: positions, legs, equity lots, P&L, covered calls.

    Positions are flushed individually so their UUIDs are available for
    leg foreign keys.

    :param session: The active SQLAlchemy async session.
    :param match_result: Output of :func:`match_transactions`.
    :param active_txns: (row_index, Transaction) pairs — used to map
        ``MatchedLeg.transaction_index`` back to the real Transaction UUID.
    """

    def get_txn(local_idx: int) -> Transaction:
        return active_txns[local_idx][1]

    # ------------------------------------------------------------------ #
    # 1. Persist OptionsPositions, their legs, and calculate P&L          #
    # ------------------------------------------------------------------ #
    persisted_positions: list[OptionsPosition] = []

    for matched_pos in match_result.positions:
        option_type_enum = OptionType(matched_pos.option_type)

        option_symbol = " ".join(
            p
            for p in [
                matched_pos.underlying,
                str(matched_pos.expiry),
                matched_pos.option_type,
                str(matched_pos.strike),
            ]
            if p
        )

        db_pos = OptionsPosition(
            underlying=matched_pos.underlying,
            option_symbol=option_symbol,
            strike=matched_pos.strike,
            expiry=matched_pos.expiry,
            option_type=option_type_enum,
            direction=matched_pos.direction,
            status=matched_pos.status,
            realized_pnl=None,
            is_covered_call=False,
        )
        session.add(db_pos)
        await session.flush()

        for leg in matched_pos.legs:
            txn = get_txn(leg.transaction_index)
            session.add(
                OptionsPositionLeg(
                    position_id=db_pos.id,
                    transaction_id=txn.id,
                    leg_role=leg.leg_role,
                    quantity=leg.quantity,
                )
            )

        # Calculate P&L for positions that have at least one close leg.
        close_legs = [leg for leg in matched_pos.legs if leg.leg_role == LegRole.CLOSE]
        if close_legs:
            # Deduplicate by transaction_index — a single close transaction can
            # appear in multiple MatchedLegs when it partially matches several open legs.
            seen: set[int] = set()
            leg_data_list: list[LegData] = []
            for leg in matched_pos.legs:
                if leg.transaction_index not in seen:
                    seen.add(leg.transaction_index)
                    txn = get_txn(leg.transaction_index)
                    leg_data_list.append(
                        LegData(
                            quantity=txn.quantity,
                            price=txn.price if txn.price is not None else Decimal("0"),
                            amount=txn.amount,
                            commission=txn.commission,
                            is_open=(leg.leg_role == LegRole.OPEN),
                        )
                    )
            pnl_result = calculate_options_pnl(leg_data_list)
            db_pos.realized_pnl = pnl_result.realized_pnl

        persisted_positions.append(db_pos)

    # ------------------------------------------------------------------ #
    # 2. Persist EquityPositions                                          #
    # ------------------------------------------------------------------ #
    for lot in match_result.equity_lots:
        assigned_pos_id = (
            persisted_positions[lot.from_position_index].id
            if lot.from_position_index is not None
            else None
        )
        session.add(
            EquityPosition(
                symbol=lot.symbol,
                quantity=lot.quantity,
                cost_basis_per_share=lot.cost_basis_per_share,
                source=lot.source,
                status=lot.status,
                assigned_position_id=assigned_pos_id,
            )
        )

    # ------------------------------------------------------------------ #
    # 3. Covered call detection                                           #
    # ------------------------------------------------------------------ #
    _COVERABLE_STATUSES = {OptionsPositionStatus.OPEN, OptionsPositionStatus.PARTIALLY_CLOSED}

    # Aggregate open equity holdings from lots created in this upload.
    holdings_map: dict[str, Decimal] = {}
    for lot in match_result.equity_lots:
        if lot.status == EquityPositionStatus.OPEN:
            holdings_map[lot.symbol] = (
                holdings_map.get(lot.symbol, Decimal("0")) + lot.quantity
            )

    equity_holdings = [
        EquityHolding(symbol=sym, total_shares=qty) for sym, qty in holdings_map.items()
    ]

    short_call_positions: list[ShortCallPosition] = []
    short_call_db_positions: list[OptionsPosition] = []

    for db_pos, matched_pos in zip(persisted_positions, match_result.positions):
        if (
            matched_pos.direction == PositionDirection.SHORT
            and matched_pos.option_type == "CALL"
            and matched_pos.status in _COVERABLE_STATUSES
        ):
            open_qty = sum(
                leg.quantity for leg in matched_pos.legs if leg.leg_role == LegRole.OPEN
            )
            close_qty = sum(
                leg.quantity for leg in matched_pos.legs if leg.leg_role == LegRole.CLOSE
            )
            net_qty = open_qty - close_qty
            short_call_positions.append(
                ShortCallPosition(
                    underlying=matched_pos.underlying,
                    option_type=matched_pos.option_type,
                    direction=matched_pos.direction.value,
                    quantity=net_qty,
                )
            )
            short_call_db_positions.append(db_pos)

    coverage_results = evaluate_covered_calls(short_call_positions, equity_holdings)
    for idx, is_covered in coverage_results:
        short_call_db_positions[idx].is_covered_call = is_covered

    await session.flush()


async def _fetch_existing_transactions(
    session: AsyncSession,
) -> list[dict[str, object]]:
    """Fetch active transactions as dicts for deduplication lookup."""
    from sqlalchemy import select

    from app.models.transaction import Transaction as TxnModel

    q = select(TxnModel).where(TxnModel.status == TransactionStatus.ACTIVE)
    result = await session.execute(q)
    txns: list[dict[str, object]] = []
    for txn in result.scalars().all():
        txns.append(
            {
                "trade_date": txn.trade_date,
                "transaction_date": txn.transaction_date,
                "settlement_date": txn.settlement_date,
                "activity_type": txn.action,
                "description": txn.description or "",
                "symbol": txn.symbol,
                "quantity": txn.quantity,
                "price": txn.price,
                "amount": txn.amount,
                "commission": txn.commission,
            }
        )
    return txns
