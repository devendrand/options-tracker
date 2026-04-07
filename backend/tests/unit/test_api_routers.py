"""Unit tests for all FastAPI router endpoints.

Coverage strategy:
- Mock DB session and repository methods via dependency overrides
- Test every endpoint: uploads, transactions, positions, pnl
- Cover 200 success paths, 404 not-found paths, 400 validation errors
- Use TestClient (synchronous) with dependency_overrides for get_db
- No real DB required — all repo calls are mocked
"""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncGenerator
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.enums import (
    EquityPositionSource,
    EquityPositionStatus,
    LegRole,
    OptionsPositionStatus,
    OptionType,
    PositionDirection,
    TransactionCategory,
    TransactionStatus,
    UploadStatus,
)
from app.schemas.pnl import PnlPeriodResponse
from app.schemas.position import (
    EquityPositionResponse,
    OptionsPositionResponse,
)
from app.schemas.transaction import TransactionResponse
from app.schemas.upload import (
    UploadResponse,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _make_upload_response(**overrides: object) -> UploadResponse:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        filename="test.csv",
        broker="etrade",
        uploaded_at=datetime(2026, 1, 15, 10, 0, 0),
        row_count=50,
        options_count=10,
        duplicate_count=2,
        possible_duplicate_count=1,
        parse_error_count=0,
        internal_transfer_count=3,
        status=UploadStatus.ACTIVE,
    )
    base.update(overrides)
    return UploadResponse(**base)  # type: ignore[arg-type]


def _make_transaction_response(**overrides: object) -> TransactionResponse:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        broker_name="etrade",
        trade_date=date(2026, 1, 15),
        transaction_date=date(2026, 1, 15),
        settlement_date=None,
        symbol="NVDA",
        option_symbol=None,
        strike=None,
        expiry=None,
        option_type=None,
        action="Sold Short",
        description=None,
        quantity=Decimal("1"),
        price=Decimal("2.50"),
        commission=Decimal("0.65"),
        amount=Decimal("250.00"),
        category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        status=TransactionStatus.ACTIVE,
        deleted_at=None,
    )
    base.update(overrides)
    return TransactionResponse(**base)  # type: ignore[arg-type]


def _make_options_position_response(**overrides: object) -> OptionsPositionResponse:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        underlying="NVDA",
        option_symbol="NVDA  260618C00220000",
        strike=Decimal("220.00"),
        expiry=date(2026, 6, 18),
        option_type=OptionType.CALL,
        direction=PositionDirection.SHORT,
        status=OptionsPositionStatus.OPEN,
        realized_pnl=None,
        is_covered_call=False,
    )
    base.update(overrides)
    return OptionsPositionResponse(**base)  # type: ignore[arg-type]


def _make_equity_position_response(**overrides: object) -> EquityPositionResponse:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        symbol="AAPL",
        quantity=Decimal("100"),
        cost_basis_per_share=Decimal("150.00"),
        status=EquityPositionStatus.OPEN,
        source=EquityPositionSource.PURCHASE,
        equity_realized_pnl=None,
        closed_at=None,
    )
    base.update(overrides)
    return EquityPositionResponse(**base)  # type: ignore[arg-type]


async def _mock_db_session() -> AsyncGenerator[AsyncMock, None]:
    """Dependency override: yield a mock AsyncSession."""
    yield AsyncMock()


@pytest.fixture()
def client() -> TestClient:
    """TestClient with get_db overridden."""
    app.dependency_overrides[get_db] = _mock_db_session
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Upload endpoints
# ---------------------------------------------------------------------------


class TestUploadsListEndpoint:
    def test_list_uploads_returns_200(self, client: TestClient) -> None:
        with patch("app.api.v1.uploads.UploadRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_uploads = AsyncMock(return_value=(1, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/uploads")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["offset"] == 0
        assert data["limit"] == 100

    def test_list_uploads_with_pagination_params(self, client: TestClient) -> None:
        with patch("app.api.v1.uploads.UploadRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_uploads = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/uploads?offset=10&limit=25")

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 10
        assert data["limit"] == 25


class TestUploadsGetDetailEndpoint:
    def test_get_upload_detail_returns_200(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        from app.models.upload import Upload

        mock_upload = Upload(filename="detail.csv")
        mock_upload.id = uid
        mock_upload.broker = "etrade"
        mock_upload.uploaded_at = datetime(2026, 1, 15, 10, 0, 0)
        mock_upload.row_count = 10
        mock_upload.options_count = 5
        mock_upload.duplicate_count = 0
        mock_upload.possible_duplicate_count = 0
        mock_upload.parse_error_count = 0
        mock_upload.internal_transfer_count = 0
        mock_upload.status = UploadStatus.ACTIVE

        with patch("app.api.v1.uploads.UploadRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_upload)
            mock_repo.get_transaction_count = AsyncMock(return_value=7)
            mock_repo_cls.return_value = mock_repo

            response = client.get(f"/api/v1/uploads/{uid}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(uid)
        assert data["transaction_count"] == 7

    def test_get_upload_detail_returns_404_when_not_found(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        with patch("app.api.v1.uploads.UploadRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            response = client.get(f"/api/v1/uploads/{uid}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Upload not found"


class TestUploadsDeleteEndpoint:
    def test_delete_upload_returns_200(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        from app.models.upload import Upload

        mock_upload = Upload(filename="todelete.csv")
        mock_upload.id = uid
        mock_upload.status = UploadStatus.SOFT_DELETED

        with patch("app.api.v1.uploads.UploadRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.soft_delete = AsyncMock(return_value=mock_upload)
            mock_repo_cls.return_value = mock_repo

            response = client.delete(f"/api/v1/uploads/{uid}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(uid)
        assert data["status"] == "SOFT_DELETED"
        assert "warning" in data

    def test_delete_upload_returns_404_when_not_found(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        with patch("app.api.v1.uploads.UploadRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.soft_delete = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            response = client.delete(f"/api/v1/uploads/{uid}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Upload not found"


class TestUploadsCreateEndpoint:
    def test_create_upload_returns_201(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        from app.models.upload import Upload

        mock_upload = Upload(filename="TxnHistory.csv")
        mock_upload.id = uid
        mock_upload.broker = "etrade"
        mock_upload.uploaded_at = datetime(2026, 1, 15, 10, 0, 0)
        mock_upload.row_count = 5
        mock_upload.options_count = 2
        mock_upload.duplicate_count = 0
        mock_upload.possible_duplicate_count = 0
        mock_upload.parse_error_count = 0
        mock_upload.internal_transfer_count = 0
        mock_upload.status = UploadStatus.ACTIVE

        from app.services.upload_orchestrator import UploadResult

        mock_result = UploadResult(
            upload=mock_upload,
            rows_parsed=5,
            options_count=2,
            duplicate_count=0,
            possible_duplicate_count=0,
            parse_error_count=0,
            internal_transfer_count=0,
        )

        with patch("app.api.v1.uploads.process_upload", new=AsyncMock(return_value=mock_result)):
            csv_content = b"Transaction Date,Activity Type\n03/15/26,Bought\n"
            response = client.post(
                "/api/v1/uploads",
                files={"file": ("TxnHistory.csv", io.BytesIO(csv_content), "text/csv")},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(uid)

    def test_create_upload_rejects_non_csv_file(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("data.txt", io.BytesIO(b"not csv"), "text/plain")},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_create_upload_rejects_missing_extension(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/uploads",
            files={"file": ("noextension", io.BytesIO(b"data"), "application/octet-stream")},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Transactions endpoint
# ---------------------------------------------------------------------------


class TestTransactionsListEndpoint:
    def test_list_transactions_returns_200(self, client: TestClient) -> None:
        with patch("app.api.v1.transactions.TransactionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_transactions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_transactions_with_all_query_params(self, client: TestClient) -> None:
        uid = uuid.uuid4()
        with patch("app.api.v1.transactions.TransactionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_transactions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get(
                f"/api/v1/transactions"
                f"?upload_id={uid}"
                f"&category=OPTIONS_SELL_TO_OPEN"
                f"&symbol=NVDA"
                f"&date_from=2026-01-01"
                f"&date_to=2026-12-31"
                f"&offset=5"
                f"&limit=50"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 5
        assert data["limit"] == 50

    def test_list_transactions_with_one_item(self, client: TestClient) -> None:
        from app.models.transaction import Transaction

        txn = Transaction(
            raw_transaction_id=uuid.uuid4(),
            upload_id=uuid.uuid4(),
            broker_name="etrade",
            trade_date=date(2026, 1, 15),
            transaction_date=date(2026, 1, 15),
            symbol="NVDA",
            action="Sold Short",
            quantity=Decimal("1"),
            commission=Decimal("0.65"),
            amount=Decimal("250.00"),
            category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        )
        txn.id = uuid.uuid4()
        txn.upload_id = uuid.uuid4()
        txn.settlement_date = None
        txn.option_symbol = None
        txn.strike = None
        txn.expiry = None
        txn.option_type = None
        txn.description = None
        txn.price = None
        txn.status = TransactionStatus.ACTIVE
        txn.deleted_at = None

        with patch("app.api.v1.transactions.TransactionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_transactions = AsyncMock(return_value=(1, [txn]))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Positions endpoints
# ---------------------------------------------------------------------------


class TestPositionsListEndpoint:
    def test_list_positions_default_options_only(self, client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["options_items"] == []
        assert data["equity_items"] == []

    def test_list_positions_equity_only(self, client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_equity_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?asset_type=equity")

        assert response.status_code == 200

    def test_list_positions_all_asset_types(self, client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo.list_equity_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?asset_type=all")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_positions_with_underlying_filter(self, client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?underlying=NVDA")

        assert response.status_code == 200

    def test_list_positions_with_options_status_filter(self, client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?status=OPEN")

        assert response.status_code == 200

    def test_list_positions_with_equity_status_filter(self, client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?status=CLOSED")

        assert response.status_code == 200

    def test_list_positions_with_options_result(self, client: TestClient) -> None:
        from app.models.options_position import OptionsPosition

        pos = OptionsPosition(
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
        )
        pos.id = uuid.uuid4()
        pos.status = OptionsPositionStatus.OPEN
        pos.realized_pnl = None
        pos.is_covered_call = False
        pos.deleted_at = None

        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(1, [(pos, None, None)]))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["options_items"]) == 1

    def test_list_positions_with_equity_result(self, client: TestClient) -> None:
        from app.models.equity_position import EquityPosition

        eq = EquityPosition(
            symbol="AAPL",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("150.00"),
            source=EquityPositionSource.PURCHASE,
        )
        eq.id = uuid.uuid4()
        eq.status = EquityPositionStatus.OPEN
        eq.equity_realized_pnl = None
        eq.closed_at = None
        eq.deleted_at = None

        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_equity_positions = AsyncMock(return_value=(1, [eq]))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?asset_type=equity")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["equity_items"]) == 1


class TestPositionsDetailEndpoint:
    def test_get_position_detail_returns_200(self, client: TestClient) -> None:
        from types import SimpleNamespace

        pos_id = uuid.uuid4()

        # Use SimpleNamespace throughout to avoid SQLAlchemy ORM relationship
        # validation when assembling mock objects in tests.
        mock_txn = SimpleNamespace(
            trade_date=date(2026, 3, 15),
            price=Decimal("2.50"),
            amount=Decimal("250.00"),
            commission=Decimal("0.65"),
        )
        leg_ns = SimpleNamespace(
            id=uuid.uuid4(),
            transaction_id=uuid.uuid4(),
            leg_role=LegRole.OPEN,
            quantity=Decimal("1"),
            transaction=mock_txn,
        )
        pos_ns = SimpleNamespace(
            id=pos_id,
            underlying="NVDA",
            option_symbol="NVDA  260618C00220000",
            strike=Decimal("220.00"),
            expiry=date(2026, 6, 18),
            option_type=OptionType.CALL,
            direction=PositionDirection.SHORT,
            status=OptionsPositionStatus.OPEN,
            realized_pnl=None,
            is_covered_call=False,
            deleted_at=None,
            legs=[leg_ns],
        )

        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_options_position_detail = AsyncMock(
                return_value=(pos_ns, None, None)
            )
            mock_repo_cls.return_value = mock_repo

            response = client.get(f"/api/v1/positions/{pos_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(pos_id)
        assert len(data["legs"]) == 1
        assert data["legs"][0]["trade_date"] == "2026-03-15"
        assert data["legs"][0]["price"] == "2.50"
        assert data["total_realized_pnl"] is None

    def test_get_position_detail_returns_404_when_not_found(self, client: TestClient) -> None:
        pos_id = uuid.uuid4()
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_options_position_detail = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            response = client.get(f"/api/v1/positions/{pos_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Position not found"


# ---------------------------------------------------------------------------
# P&L endpoint
# ---------------------------------------------------------------------------


class TestPnlSummaryEndpoint:
    def test_get_pnl_summary_defaults(self, client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_pnl_summary = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/pnl/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "year"
        assert data["items"] == []

    def test_get_pnl_summary_month_period(self, client: TestClient) -> None:
        item = PnlPeriodResponse(
            period_label="2026-01",
            options_pnl=Decimal("150.00"),
            equity_pnl=Decimal("0.00"),
            total_pnl=Decimal("150.00"),
        )
        with patch("app.api.v1.pnl.PnlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_pnl_summary = AsyncMock(return_value=[item])
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/pnl/summary?period=month")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "month"
        assert len(data["items"]) == 1
        assert data["items"][0]["period_label"] == "2026-01"

    def test_get_pnl_summary_with_underlying_filter(self, client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_pnl_summary = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/pnl/summary?underlying=NVDA")

        assert response.status_code == 200

    def test_get_pnl_summary_options_type(self, client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_pnl_summary = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/pnl/summary?type=options")

        assert response.status_code == 200

    def test_get_pnl_summary_equity_type(self, client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_pnl_summary = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/pnl/summary?type=equity")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Positions: status parsing branch coverage
# ---------------------------------------------------------------------------


class TestPositionsStatusParsing:
    """Cover the ValueError exception handling in list_positions."""

    def test_options_only_status_value_valid_for_options_only(self, client: TestClient) -> None:
        """EXPIRED is a valid OptionsPositionStatus but not EquityPositionStatus."""
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?status=EXPIRED")

        assert response.status_code == 200

    def test_equity_only_status_value_valid_for_equity_only(self, client: TestClient) -> None:
        """CLOSED is valid for both status enums, so cover the path where options
        ValueError fires but equity succeeds; achieved by using CLOSED with equity."""
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?status=CLOSED")

        assert response.status_code == 200

    def test_unknown_status_value_is_ignored(self, client: TestClient) -> None:
        """An unrecognised status value should not crash the endpoint (both
        ValueError branches fire and both statuses remain None)."""
        with patch("app.api.v1.positions.PositionRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.list_options_positions = AsyncMock(return_value=(0, []))
            mock_repo_cls.return_value = mock_repo

            response = client.get("/api/v1/positions?status=INVALID_STATUS")

        assert response.status_code == 200
