"""
tests/conftest.py

Shared fixtures for unit tests.
All fixtures mock external dependencies (DB, LLM) so tests run without
any real services.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from core.models import OHLCV

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    ts: datetime | None = None,
    close: float = 100.0,
) -> OHLCV:
    """Create an OHLCV instance with sensible defaults."""
    if ts is None:
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return OHLCV(
        symbol=symbol,
        timestamp=ts,
        open=close - 1,
        high=close + 2,
        low=close - 3,
        close=close,
        volume=1000.0,
        timeframe=timeframe,
    )


# ---------------------------------------------------------------------------
# FastAPI test app (DB dependency overridden)
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Import the real app but override the DB dependency with a mock."""
    from api.main import app
    from db.database import get_db_connection

    mock_conn = AsyncMock()

    async def _mock_db_dep() -> AsyncGenerator[AsyncMock, None]:
        yield mock_conn

    app.dependency_overrides[get_db_connection] = _mock_db_dep
    return app


@pytest.fixture()
def app_client() -> httpx.AsyncClient:
    """Async HTTP client bound to the FastAPI app (no real server needed)."""
    from httpx import ASGITransport

    test_app = _build_test_app()
    transport = ASGITransport(app=test_app)  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture()
def mock_conn() -> AsyncMock:
    """Standalone mock asyncpg connection for direct function tests."""
    return AsyncMock()
