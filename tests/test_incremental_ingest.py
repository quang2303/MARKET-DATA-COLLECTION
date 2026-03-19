"""
tests/test_incremental_ingest.py

Regression tests for the incremental + idempotent OHLCV ingest flow.

What is tested
--------------
1. Running ingest_ohlcv twice on the same data does NOT produce duplicate rows.
2. When the DB already has data up to timestamp T, the next ingest call
   starts fetching from T - overlap (not from the beginning).
3. An explicit backfill call for a gap window fills only those candles.

Requirements
------------
- Running PostgreSQL/TimescaleDB reachable via DATABASE_URL in .env
- ohlcv_data table with unique index applied
  (run db/init.sql or db/migrations/001_add_unique_constraint_ohlcv.sql first)

Run:
    python -m pytest tests/test_incremental_ingest.py -v
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from core.models import OHLCV
from db.database import upsert_ohlcv
from fetchers.binance import BinanceFetcher
from services.ingest import ingest_ohlcv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/market_data")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def conn():
    """Provide a real DB connection and roll back after each test."""
    connection = await asyncpg.connect(DATABASE_URL)
    await connection.execute("BEGIN")
    yield connection
    await connection.execute("ROLLBACK")
    await connection.close()


def _make_candle(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    ts: datetime | None = None,
    close: float = 50_000.0,
) -> OHLCV:
    if ts is None:
        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return OHLCV(
        symbol=symbol,
        timestamp=ts,
        open=close - 100,
        high=close + 200,
        low=close - 300,
        close=close,
        volume=10_000.0,
        timeframe=timeframe,
    )


def _make_candles(
    hours: range,
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    base_ts: datetime | None = None,
) -> list[OHLCV]:
    if base_ts is None:
        base_ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return [_make_candle(symbol=symbol, timeframe=timeframe, ts=base_ts + timedelta(hours=h)) for h in hours]


# ---------------------------------------------------------------------------
# Test 1 — Double ingest does NOT create duplicates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_double_ingest_no_duplicates(conn):
    """
    Call ingest_ohlcv with the same mocked data twice.
    Row count must equal len(data), never 2*len(data).
    """
    base_ts = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    mock_candles = _make_candles(range(5), base_ts=base_ts)

    fetcher = BinanceFetcher()

    # Mock fetch_ohlcv so no real HTTP call is made
    with patch.object(fetcher, "fetch_ohlcv", new=AsyncMock(return_value=mock_candles)):
        await ingest_ohlcv(conn, fetcher, "BTCUSDT", "1h")
        await ingest_ohlcv(conn, fetcher, "BTCUSDT", "1h")

    count = await conn.fetchval(
        "SELECT COUNT(*) FROM ohlcv_data WHERE symbol = $1 AND timeframe = $2",
        "BTC/USDT",
        "1h",
    )
    assert count == len(mock_candles), (
        f"Expected {len(mock_candles)} rows, got {count}. "
        "Double ingest created duplicates — upsert is broken."
    )


# ---------------------------------------------------------------------------
# Test 2 — Incremental: fetcher receives start_time ≥ max(timestamp) - overlap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incremental_advances_from_db_latest_timestamp(conn):
    """
    After seeding T=0..4h, the next ingest (no explicit start_time) must
    pass a start_time argument to the fetcher that is >= T=4h - overlap.
    Specifically: start_time == max_ts - overlap.
    """
    base_ts = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    seed_candles = _make_candles(range(5), base_ts=base_ts)  # T=0h..T=4h

    # Seed the DB directly
    await upsert_ohlcv(conn, seed_candles)

    expected_max_ts = base_ts + timedelta(hours=4)  # T=4h
    overlap = timedelta(minutes=1)
    expected_start = expected_max_ts - overlap

    fetcher = BinanceFetcher()
    captured_start: list[datetime] = []

    async def capture_fetch(symbol, interval, **kwargs):
        if "start_time" in kwargs:
            captured_start.append(kwargs["start_time"])
        return []  # Nothing new to ingest

    with patch.object(fetcher, "fetch_ohlcv", new=AsyncMock(side_effect=capture_fetch)):
        await ingest_ohlcv(conn, fetcher, "BTCUSDT", "1h", overlap=overlap)

    assert len(captured_start) == 1, "fetch_ohlcv was not called exactly once"
    actual_start = captured_start[0]
    assert actual_start == expected_start, (
        f"Expected fetcher start_time={expected_start.isoformat()}, "
        f"got {actual_start.isoformat()}. Incremental cursor is wrong."
    )


# ---------------------------------------------------------------------------
# Test 3 — Backfill fills a gap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_fills_gap(conn):
    """
    Scenario: DB has T=0h and T=5h but nothing in between.
    An explicit backfill call for start=T1h, end=T4h must insert T=1..4h.
    """
    base_ts = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Seed T=0h and T=5h only (gap: T=1h..T=4h)
    boundary_candles = [
        _make_candle(ts=base_ts),
        _make_candle(ts=base_ts + timedelta(hours=5)),
    ]
    await upsert_ohlcv(conn, boundary_candles)

    # Gap candles that the backfill should bring in
    gap_candles = _make_candles(range(1, 5), base_ts=base_ts)  # T=1h..T=4h

    fetcher = BinanceFetcher()
    bf_start = base_ts + timedelta(hours=1)
    bf_end = base_ts + timedelta(hours=4)

    with patch.object(fetcher, "fetch_ohlcv", new=AsyncMock(return_value=gap_candles)):
        n = await ingest_ohlcv(
            conn,
            fetcher,
            "BTCUSDT",
            "1h",
            start_time=bf_start,
            end_time=bf_end,
        )

    assert n == len(gap_candles), f"Expected {len(gap_candles)} upserted, got {n}"

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM ohlcv_data WHERE symbol = $1 AND timeframe = $2",
        "BTC/USDT",
        "1h",
    )
    # 2 boundary + 4 gap = 6
    assert total == 6, (
        f"Expected 6 total rows after backfill (2 boundary + 4 gap), got {total}."
    )
