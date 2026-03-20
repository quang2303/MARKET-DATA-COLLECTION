"""
tests/test_query_by_text_api.py

Tests for POST /api/v1/query-by-text.
Both the LLM call (parse_text_to_query) and DB are mocked.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from core.schemas import MarketDataQuery
from tests.conftest import make_ohlcv


async def test_query_by_text_success(app_client) -> None:  # type: ignore[no-untyped-def]
    """Valid text query → LLM is mocked → 200 with OHLCV list."""
    fake_parsed = MarketDataQuery(
        symbol="BTC/USDT",
        timeframe="1h",
        start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )
    fake_data = [
        make_ohlcv(ts=datetime(2025, 1, 1, h, 0, 0, tzinfo=timezone.utc))
        for h in range(3)
    ]

    with (
        patch(
            "api.routers.market_data.parse_text_to_query",
            return_value=fake_parsed,
        ),
        patch(
            "api.routers.market_data.get_market_data",
            new=AsyncMock(return_value=fake_data),
        ),
    ):
        resp = await app_client.post(
            "/api/v1/query-by-text",
            json={"text": "Get BTC 1h candles for the last 3 days"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3


async def test_query_by_text_empty_body(app_client) -> None:  # type: ignore[no-untyped-def]
    """Missing request body → 422."""
    resp = await app_client.post("/api/v1/query-by-text")
    assert resp.status_code == 422
