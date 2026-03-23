"""
tests/test_models.py

Unit tests for Pydantic models and schemas in core/.
These are pure data-validation tests — no IO required.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.models import OHLCV
from core.schemas import MarketDataQuery, TextQueryRequest

# ---------------------------------------------------------------------------
# OHLCV model
# ---------------------------------------------------------------------------


class TestOHLCV:
    """Tests for the OHLCV data model."""

    def test_create_valid(self) -> None:
        candle = OHLCV(
            symbol="BTC/USDT",
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=5000.0,
            timeframe="1h",
        )
        assert candle.symbol == "BTC/USDT"
        assert candle.close == 105.0
        assert candle.timeframe == "1h"

    def test_frozen_model_rejects_mutation(self) -> None:
        candle = OHLCV(
            symbol="ETH/USDT",
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
            open=2000.0,
            high=2100.0,
            low=1900.0,
            close=2050.0,
            volume=3000.0,
            timeframe="1d",
        )
        with pytest.raises(ValidationError):
            candle.close = 9999.0  # type: ignore[misc]

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValidationError):
            OHLCV(  # type: ignore[call-arg]
                symbol="BTC/USDT",
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                # missing open, high, low, close, volume, timeframe
            )

    def test_round_trip_json(self) -> None:
        candle = OHLCV(
            symbol="BTC/USDT",
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            open=100.0,
            high=110.0,
            low=90.0,
            close=105.0,
            volume=5000.0,
            timeframe="1h",
        )
        json_str = candle.model_dump_json()
        restored = OHLCV.model_validate_json(json_str)
        assert restored == candle


# ---------------------------------------------------------------------------
# MarketDataQuery schema
# ---------------------------------------------------------------------------


class TestMarketDataQuery:
    """Tests for the MarketDataQuery schema."""

    def test_create_valid(self) -> None:
        q = MarketDataQuery(
            symbol="BTC/USDT",
            timeframe="1h",
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
        )
        assert q.symbol == "BTC/USDT"

    def test_frozen(self) -> None:
        q = MarketDataQuery(
            symbol="BTC/USDT",
            timeframe="1h",
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
        )
        with pytest.raises(ValidationError):
            q.symbol = "ETH/USDT"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TextQueryRequest schema
# ---------------------------------------------------------------------------


class TestTextQueryRequest:
    """Tests for the TextQueryRequest schema."""

    def test_create_valid(self) -> None:
        req = TextQueryRequest(text="Get BTC 1h candles for the last 3 days")
        assert "BTC" in req.text

    def test_missing_text_raises(self) -> None:
        with pytest.raises(ValidationError):
            TextQueryRequest()  # type: ignore[call-arg]
