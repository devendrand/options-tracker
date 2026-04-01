"""Tests for the health endpoint, JSON logging, and app lifespan."""

import json
import logging
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import JSONFormatter, app, configure_logging

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_check_returns_ok(client: TestClient) -> None:
    """GET /health returns 200 with status ok (no lifespan required)."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_with_lifespan() -> None:
    """GET /health succeeds when the full lifespan runs (init_db mocked)."""
    with patch("app.main.init_db"), patch("app.main.configure_logging"):
        with TestClient(app) as lc:
            response = lc.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Lifespan: init_db and configure_logging are called
# ---------------------------------------------------------------------------


def test_lifespan_calls_init_db_and_configure_logging() -> None:
    """Lifespan should call configure_logging then init_db on startup."""
    with patch("app.main.init_db") as mock_init, patch("app.main.configure_logging") as mock_log:
        with TestClient(app):
            pass
    mock_log.assert_called_once()
    mock_init.assert_called_once()


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


def test_json_formatter_produces_valid_json() -> None:
    """JSONFormatter.format() emits a parseable JSON object."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="options.test",
        level=logging.WARNING,
        pathname="test.py",
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "WARNING"
    assert data["logger"] == "options.test"
    assert data["message"] == "something happened"


def test_json_formatter_with_format_args() -> None:
    """JSONFormatter renders %-style format args correctly."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname="x.py",
        lineno=0,
        msg="value is %s",
        args=("42",),
        exc_info=None,
    )
    data = json.loads(formatter.format(record))
    assert data["message"] == "value is 42"


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------


def test_configure_logging_sets_level_and_adds_handler() -> None:
    """configure_logging attaches a JSONFormatter handler to the root logger."""
    # Isolate: remove handlers we add during this test
    root = logging.getLogger()
    before_count = len(root.handlers)

    configure_logging("DEBUG")

    assert root.level == logging.DEBUG
    # At least one new handler was added with our JSONFormatter
    json_handlers = [h for h in root.handlers if isinstance(h.formatter, JSONFormatter)]
    assert json_handlers

    # Restore: remove the extra handler we added
    for h in root.handlers[before_count:]:
        root.removeHandler(h)


def test_configure_logging_default_level() -> None:
    """configure_logging defaults to INFO when no level is passed."""
    root = logging.getLogger()
    before_count = len(root.handlers)

    configure_logging()

    assert root.level == logging.INFO

    for h in root.handlers[before_count:]:
        root.removeHandler(h)


# ---------------------------------------------------------------------------
# CORS header
# ---------------------------------------------------------------------------


def test_cors_header_present_for_frontend_origin(client: TestClient) -> None:
    """CORS allows requests from the Angular dev server."""
    response = client.get("/health", headers={"Origin": "http://localhost:4200"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:4200"
