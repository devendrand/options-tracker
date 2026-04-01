"""Unit tests for all API v1 route handlers.

Coverage strategy:
- Override get_db dependency with a mock AsyncSession per test
- Patch repository classes and process_upload service to avoid real DB
- Cover all success paths, 404 paths, 400 paths, and query-param branches
- Tests are sync (TestClient) — FastAPI handles the async event loop internally
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
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
from app.services.upload_orchestrator import UploadResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_ns(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        filename="TxnHistory.csv",
        broker="etrade",
        uploaded_at=datetime(2026, 3, 30, 12, 0, 0),
        row_count=5,
        options_count=3,
        duplicate_count=0,
        possible_duplicate_count=0,
        parse_error_count=0,
        internal_transfer_count=0,
        status=UploadStatus.ACTIVE,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _txn_ns(**overrides: object) -> SimpleNamespace:
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
        description="CALL NVDA",
        quantity=Decimal("1"),
        price=Decimal("2.50"),
        commission=Decimal("0.65"),
        amount=Decimal("250.00"),
        category=TransactionCategory.OPTIONS_SELL_TO_OPEN,
        status=TransactionStatus.ACTIVE,
        deleted_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _opts_pos_ns(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        underlying="NVDA",
        option_symbol="NVDA 260618C00220000",
        strike=Decimal("220.00"),
        expiry=date(2026, 6, 18),
        option_type=OptionType.CALL,
        direction=PositionDirection.SHORT,
        status=OptionsPositionStatus.OPEN,
        realized_pnl=None,
        is_covered_call=False,
        legs=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _eq_pos_ns(**overrides: object) -> SimpleNamespace:
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
    return SimpleNamespace(**base)


def _leg_ns(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = dict(
        id=uuid.uuid4(),
        transaction_id=uuid.uuid4(),
        leg_role=LegRole.OPEN,
        quantity=Decimal("1"),
        trade_date=date(2026, 3, 15),
        price=Decimal("2.50"),
        amount=Decimal("250.00"),
        commission=Decimal("0.65"),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ---------------------------------------------------------------------------
# Fixture: TestClient with mocked DB session
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client() -> TestClient:  # type: ignore[misc]
    """TestClient with get_db overridden to yield an AsyncMock session."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    async def override_get_db():  # type: ignore[misc]
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Uploads router
# ---------------------------------------------------------------------------


class TestCreateUpload:
    def test_create_upload_success(self, api_client: TestClient) -> None:
        upload_ns = _upload_ns()

        mock_result = MagicMock(spec=UploadResult)
        mock_result.upload = upload_ns

        with (
            patch("app.api.v1.uploads.process_upload", new=AsyncMock(return_value=mock_result)),
        ):
            response = api_client.post(
                "/api/v1/uploads",
                files={"file": ("TxnHistory.csv", b"col1,col2\nval1,val2", "text/csv")},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "TxnHistory.csv"
        assert data["broker"] == "etrade"
        assert data["status"] == "ACTIVE"

    def test_create_upload_rejects_non_csv(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/v1/uploads",
            files={"file": ("data.txt", b"not csv", "text/plain")},
        )
        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_create_upload_rejects_missing_extension(self, api_client: TestClient) -> None:
        response = api_client.post(
            "/api/v1/uploads",
            files={"file": ("noextension", b"data", "application/octet-stream")},
        )
        assert response.status_code == 400


class TestListUploads:
    def test_list_uploads_empty(self, api_client: TestClient) -> None:
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.list_uploads = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/uploads")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["offset"] == 0
        assert data["limit"] == 100

    def test_list_uploads_with_items(self, api_client: TestClient) -> None:
        upload_ns = _upload_ns()
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.list_uploads = AsyncMock(return_value=(1, [upload_ns]))
            response = api_client.get("/api/v1/uploads?offset=0&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["limit"] == 10

    def test_list_uploads_pagination(self, api_client: TestClient) -> None:
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.list_uploads = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/uploads?offset=50&limit=25")

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 50
        assert data["limit"] == 25


class TestGetUploadDetail:
    def test_get_detail_found(self, api_client: TestClient) -> None:
        upload_ns = _upload_ns()
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=upload_ns)
            MockRepo.return_value.get_transaction_count = AsyncMock(return_value=3)
            response = api_client.get(f"/api/v1/uploads/{upload_ns.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["transaction_count"] == 3
        assert data["filename"] == "TxnHistory.csv"

    def test_get_detail_not_found(self, api_client: TestClient) -> None:
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.get_by_id = AsyncMock(return_value=None)
            response = api_client.get(f"/api/v1/uploads/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Upload not found"


class TestDeleteUpload:
    def test_delete_upload_success(self, api_client: TestClient) -> None:
        upload_ns = _upload_ns(status=UploadStatus.SOFT_DELETED)
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.soft_delete = AsyncMock(return_value=upload_ns)
            response = api_client.delete(f"/api/v1/uploads/{upload_ns.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SOFT_DELETED"
        assert "warning" in data

    def test_delete_upload_not_found(self, api_client: TestClient) -> None:
        with patch("app.api.v1.uploads.UploadRepository") as MockRepo:
            MockRepo.return_value.soft_delete = AsyncMock(return_value=None)
            response = api_client.delete(f"/api/v1/uploads/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Upload not found"


# ---------------------------------------------------------------------------
# Transactions router
# ---------------------------------------------------------------------------


class TestListTransactions:
    def test_list_transactions_empty(self, api_client: TestClient) -> None:
        with patch("app.api.v1.transactions.TransactionRepository") as MockRepo:
            MockRepo.return_value.list_transactions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_transactions_with_items(self, api_client: TestClient) -> None:
        txn_ns = _txn_ns()
        with patch("app.api.v1.transactions.TransactionRepository") as MockRepo:
            MockRepo.return_value.list_transactions = AsyncMock(return_value=(1, [txn_ns]))
            response = api_client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["symbol"] == "NVDA"

    def test_list_transactions_with_all_filters(self, api_client: TestClient) -> None:
        upload_id = uuid.uuid4()
        with patch("app.api.v1.transactions.TransactionRepository") as MockRepo:
            MockRepo.return_value.list_transactions = AsyncMock(return_value=(0, []))
            response = api_client.get(
                "/api/v1/transactions",
                params={
                    "upload_id": str(upload_id),
                    "category": "OPTIONS_SELL_TO_OPEN",
                    "symbol": "NVDA",
                    "date_from": "2026-01-01",
                    "date_to": "2026-12-31",
                    "offset": 10,
                    "limit": 50,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 10
        assert data["limit"] == 50


# ---------------------------------------------------------------------------
# Positions router
# ---------------------------------------------------------------------------


class TestListPositions:
    def test_list_positions_options_default(self, api_client: TestClient) -> None:
        pos_ns = _opts_pos_ns()
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(1, [pos_ns]))
            MockRepo.return_value.list_equity_positions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/positions?asset_type=options")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["options_items"]) == 1
        assert data["equity_items"] == []

    def test_list_positions_equity_only(self, api_client: TestClient) -> None:
        eq_ns = _eq_pos_ns()
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_equity_positions = AsyncMock(return_value=(1, [eq_ns]))
            response = api_client.get("/api/v1/positions?asset_type=equity")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["options_items"] == []
        assert len(data["equity_items"]) == 1
        assert data["equity_items"][0]["symbol"] == "AAPL"

    def test_list_positions_all(self, api_client: TestClient) -> None:
        pos_ns = _opts_pos_ns()
        eq_ns = _eq_pos_ns()
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(1, [pos_ns]))
            MockRepo.return_value.list_equity_positions = AsyncMock(return_value=(1, [eq_ns]))
            response = api_client.get("/api/v1/positions?asset_type=all")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_positions_with_options_only_status(self, api_client: TestClient) -> None:
        """Status valid for OptionsPositionStatus but not EquityPositionStatus."""
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(0, []))
            MockRepo.return_value.list_equity_positions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/positions?asset_type=all&status=PARTIALLY_CLOSED")

        assert response.status_code == 200

    def test_list_positions_with_invalid_status(self, api_client: TestClient) -> None:
        """Unknown status — both ValueError branches are hit."""
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(0, []))
            MockRepo.return_value.list_equity_positions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/positions?asset_type=all&status=INVALID_STATUS")

        assert response.status_code == 200

    def test_list_positions_with_equity_only_status(self, api_client: TestClient) -> None:
        """Status valid for EquityPositionStatus (OPEN is valid for both)."""
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(0, []))
            MockRepo.return_value.list_equity_positions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/positions?asset_type=all&status=OPEN")

        assert response.status_code == 200

    def test_list_positions_no_status_param(self, api_client: TestClient) -> None:
        """No status param — status is None, no parsing attempted."""
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/positions?asset_type=options")

        assert response.status_code == 200

    def test_list_positions_with_underlying_filter(self, api_client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.list_options_positions = AsyncMock(return_value=(0, []))
            response = api_client.get("/api/v1/positions?asset_type=options&underlying=NVDA")

        assert response.status_code == 200


class TestGetPositionDetail:
    def test_get_position_detail_found(self, api_client: TestClient) -> None:
        pos_ns = _opts_pos_ns()
        leg_ns = _leg_ns()
        # legs must be on the position object for the router to iterate
        pos_ns_with_legs = _opts_pos_ns()
        pos_ns_with_legs.legs = [leg_ns]

        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.get_options_position_detail = AsyncMock(
                return_value=pos_ns_with_legs
            )
            response = api_client.get(f"/api/v1/positions/{pos_ns.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["underlying"] == "NVDA"
        assert len(data["legs"]) == 1

    def test_get_position_detail_not_found(self, api_client: TestClient) -> None:
        with patch("app.api.v1.positions.PositionRepository") as MockRepo:
            MockRepo.return_value.get_options_position_detail = AsyncMock(return_value=None)
            response = api_client.get(f"/api/v1/positions/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Position not found"


# ---------------------------------------------------------------------------
# P&L router
# ---------------------------------------------------------------------------


class TestGetPnlSummary:
    def test_get_pnl_summary_default_params(self, api_client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as MockRepo:
            MockRepo.return_value.get_pnl_summary = AsyncMock(return_value=[])
            response = api_client.get("/api/v1/pnl/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "year"
        assert data["items"] == []

    def test_get_pnl_summary_month_options(self, api_client: TestClient) -> None:
        from app.schemas.pnl import PnlPeriodResponse

        item = PnlPeriodResponse(
            period_label="2026-01",
            options_pnl=Decimal("500.00"),
            equity_pnl=Decimal("0.00"),
            total_pnl=Decimal("500.00"),
        )
        with patch("app.api.v1.pnl.PnlRepository") as MockRepo:
            MockRepo.return_value.get_pnl_summary = AsyncMock(return_value=[item])
            response = api_client.get("/api/v1/pnl/summary?period=month&type=options")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "month"
        assert len(data["items"]) == 1
        assert data["items"][0]["period_label"] == "2026-01"

    def test_get_pnl_summary_with_underlying(self, api_client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as MockRepo:
            MockRepo.return_value.get_pnl_summary = AsyncMock(return_value=[])
            response = api_client.get("/api/v1/pnl/summary?underlying=NVDA&type=equity")

        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "year"

    def test_get_pnl_summary_all_type(self, api_client: TestClient) -> None:
        with patch("app.api.v1.pnl.PnlRepository") as MockRepo:
            MockRepo.return_value.get_pnl_summary = AsyncMock(return_value=[])
            response = api_client.get("/api/v1/pnl/summary?type=all")

        assert response.status_code == 200
