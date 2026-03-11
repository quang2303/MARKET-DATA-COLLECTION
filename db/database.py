import os
from typing import List, AsyncGenerator
from datetime import datetime
import asyncpg
from core.models import OHLCV

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

async def bulk_insert_ohlcv(conn: asyncpg.Connection, data: List[OHLCV]) -> None:
    """
    Bulk insert raw OHLCV data into the database using asyncpg's copy_records_to_table.
    This respects the data interface requirement where input is List[OHLCV].
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
) -> List[OHLCV]:
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
