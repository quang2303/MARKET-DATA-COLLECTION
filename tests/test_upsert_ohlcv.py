"""
tests/test_upsert_ohlcv.py

Regression tests for idempotent OHLCV upsert behaviour.

Requirements:
- A running PostgreSQL/TimescaleDB instance reachable via DATABASE_URL in .env
- The ohlcv_data table must already exist with the unique index applied
  (run db/init.sql or db/migrations/001_add_unique_constraint_ohlcv.sql first)

Run:
    python -m pytest tests/test_upsert_ohlcv.py -v
"""

import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from core.models import OHLCV
from db.crud import upsert_ohlcv

load_dotenv(override=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/market_data"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def conn() -> AsyncGenerator[asyncpg.Connection, None]:
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
    close: float = 100.0,
) -> OHLCV:
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
# Test 1 — Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_is_idempotent(conn: asyncpg.Connection) -> None:
    """
    Inserting the same list of candles twice must not create duplicate rows.
    COUNT(*) after the second call must equal len(data), not 2*len(data).
    """
    data = [
        _make_candle(ts=datetime(2025, 1, 1, h, 0, 0, tzinfo=timezone.utc))
        for h in range(5)
    ]

    await upsert_ohlcv(conn, data)
    await upsert_ohlcv(
        conn, data
    )  # second call — must be a no-op in terms of row count

    count = await conn.fetchval(
        "SELECT COUNT(*) FROM ohlcv_data WHERE symbol = $1 AND timeframe = $2",
        "BTC/USDT",
        "1h",
    )
    assert count == len(data), (
        f"Expected {len(data)} rows after double insert, got {count}. "
        "Duplicates detected — unique constraint or upsert logic is broken."
    )


# ---------------------------------------------------------------------------
# Test 2 — Upsert updates values
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_updates_close_price(conn: asyncpg.Connection) -> None:
    """
    If the same (symbol, timeframe, timestamp) is inserted with a different
    close price, the DB row must reflect the new value.
    """
    ts = datetime(2025, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
    original = _make_candle(ts=ts, close=100.0)
    corrected = _make_candle(ts=ts, close=105.0)

    await upsert_ohlcv(conn, [original])
    await upsert_ohlcv(conn, [corrected])

    row = await conn.fetchrow(
        "SELECT close FROM ohlcv_data "
        "WHERE symbol=$1 AND timeframe=$2 AND timestamp=$3",
        "BTC/USDT",
        "1h",
        ts,
    )
    assert row is not None, "Row not found after upsert."
    assert (
        row["close"] == 105.0
    ), f"Expected close=105.0 after corrected candle upsert, got {row['close']}."


# ---------------------------------------------------------------------------
# Test 3 — Different symbol or timeframe do NOT conflict
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_symbol_and_timeframe_are_independent(
    conn: asyncpg.Connection,
) -> None:
    """
    Candles with the same timestamp but different symbol or timeframe
    must be stored as separate rows — no false conflict.
    """
    ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    candles = [
        _make_candle(symbol="BTC/USDT", timeframe="1h", ts=ts),
        _make_candle(symbol="ETH/USDT", timeframe="1h", ts=ts),
        _make_candle(symbol="BTC/USDT", timeframe="15m", ts=ts),
    ]

    await upsert_ohlcv(conn, candles)

    count = await conn.fetchval(
        "SELECT COUNT(*) FROM ohlcv_data WHERE timestamp = $1",
        ts,
    )
    assert (
        count == 3
    ), f"Expected 3 distinct rows (different symbol/timeframe), got {count}."
