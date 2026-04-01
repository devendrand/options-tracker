"""Upload processing orchestrator — coordinates the full CSV pipeline.

Pipeline: parse → classify → (persist raw + classified) → dedup → match → P&L
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    RawTransactionStatus,
    TransactionCategory,
    TransactionStatus,
)
from app.models.raw_transaction import RawTransaction
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.services.classifier import classify_transaction
from app.services.deduplicator import deduplicate_rows
from app.services.parser.etrade import ParsedRow, parse_etrade_csv


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

    Position matching and P&L calculation are handled separately
    after initial persistence.
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

    await session.flush()
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
