import os
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import asyncpg

from core.models import OHLCV

# Upsert SQL — idempotent on (symbol, timeframe, timestamp).
# Refreshes OHLCV prices in case a live candle was corrected by the exchange.
_UPSERT_SQL = """
    INSERT INTO ohlcv_data (symbol, timestamp, open, high, low, close, volume, timeframe)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    ON CONFLICT (symbol, timeframe, timestamp)
    DO UPDATE SET
        open   = EXCLUDED.open,
        high   = EXCLUDED.high,
        low    = EXCLUDED.low,
        close  = EXCLUDED.close,
        volume = EXCLUDED.volume;
"""

# Global connection pool instance
pool: asyncpg.Pool | None = None

async def init_db_pool() -> None:
    """
    Initialize connection pool for the database.
    This function should be called at FastAPI startup.
    """
    global pool
    db_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/market_data")
    pool = await asyncpg.create_pool(db_url)

async def close_db_pool() -> None:
    """
    Close the connection pool.
    This function should be called at FastAPI shutdown.
    """
    global pool
    if pool is not None:
        await pool.close()

async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI Dependency to provide database connections for API endpoints.
    """
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with pool.acquire() as conn:
        yield conn

async def upsert_ohlcv(conn: asyncpg.Connection, data: list[OHLCV]) -> None:
    """
    Idempotent bulk upsert of OHLCV data using INSERT ... ON CONFLICT DO UPDATE.

    Safe to call multiple times with the same data — re-fetching will never
    create duplicate candles. If the exchange corrects a live candle, the
    updated open/high/low/close/volume values will be written to the DB.
    """
    if not data:
        return

    records = [
        (
            item.symbol,
            item.timestamp,
            item.open,
            item.high,
            item.low,
            item.close,
            item.volume,
            item.timeframe,
        )
        for item in data
    ]

    await conn.executemany(_UPSERT_SQL, records)


async def bulk_insert_ohlcv(conn: asyncpg.Connection, data: list[OHLCV]) -> None:
    """
    DEPRECATED: Use upsert_ohlcv() instead.

    This function uses copy_records_to_table which does NOT enforce the unique
    constraint and will create duplicate rows on re-fetch.
    """
    if not data:
        return

    # Convert List[OHLCV] (Pydantic models) to List of Tuples
    records = [
        (
            item.symbol,
            item.timestamp,
            item.open,
            item.high,
            item.low,
            item.close,
            item.volume,
            item.timeframe,
        )
        for item in data
    ]

    await conn.copy_records_to_table(
        "ohlcv_data",
        records=records,
        columns=["symbol", "timestamp", "open", "high", "low", "close", "volume", "timeframe"],
    )

async def get_market_data(
    conn: asyncpg.Connection,
    symbol: str,
    timeframe: str,
    start_time: datetime,
    end_time: datetime,
) -> list[OHLCV]:
    """
    Retrieve OHLCV data from the DB based on parameters.
    The result is parsed into a unified OHLCV model.
    """
    query = """
        SELECT symbol, timestamp, open, high, low, close, volume, timeframe
        FROM ohlcv_data
        WHERE symbol = $1
          AND timeframe = $2
          AND timestamp >= $3
          AND timestamp <= $4
        ORDER BY timestamp ASC
    """
    rows = await conn.fetch(query, symbol, timeframe, start_time, end_time)

    # Map the returned results to OHLCV models
    return [OHLCV(**dict(row)) for row in rows]


async def get_latest_timestamp(
    conn: asyncpg.Connection,
    symbol: str,
    timeframe: str,
) -> datetime | None:
    """
    Return the most recent candle timestamp stored for a given (symbol, timeframe).

    Used by the incremental ingest service to determine where to resume fetching
    so that no data is missed and no unnecessary re-fetching occurs.

    Args:
        conn: Active asyncpg connection.
        symbol: Standardised symbol, e.g. ``"BTC/USDT"``.
        timeframe: Candle interval, e.g. ``"1h"``.

    Returns:
        The latest ``datetime`` (UTC-aware) stored in the DB, or ``None`` if the
        table contains no rows for this (symbol, timeframe) pair.
    """
    row = await conn.fetchrow(
        "SELECT MAX(timestamp) AS latest FROM ohlcv_data WHERE symbol = $1 AND timeframe = $2",
        symbol,
        timeframe,
    )
    if row is None or row["latest"] is None:
        return None
    ts: datetime = row["latest"]
    # asyncpg returns TIMESTAMPTZ as an aware datetime — ensure UTC tzinfo is set.
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts
