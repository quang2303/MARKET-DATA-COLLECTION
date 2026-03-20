"""
tests/test_market_data_api.py

Tests for GET /api/v1/market-data.
DB dependency is mocked — no real database required.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import make_ohlcv


async def test_get_market_data_success(app_client) -> None:  # type: ignore[no-untyped-def]
    """Valid query params → 200 with list of OHLCV objects."""
    fake_data = [
        make_ohlcv(ts=datetime(2025, 1, 1, h, 0, 0, tzinfo=timezone.utc))
        for h in range(3)
    ]

    with patch("api.routers.market_data.get_market_data", new=AsyncMock(return_value=fake_data)):
        resp = await app_client.get(
            "/api/v1/market-data",
            params={
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_time": "2025-01-01T00:00:00Z",
                "end_time": "2025-01-01T03:00:00Z",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3
    assert data[0]["symbol"] == "BTC/USDT"


async def test_get_market_data_missing_params(app_client) -> None:  # type: ignore[no-untyped-def]
    """Missing required query parameters → 422 Unprocessable Entity."""
    resp = await app_client.get("/api/v1/market-data")
    assert resp.status_code == 422
