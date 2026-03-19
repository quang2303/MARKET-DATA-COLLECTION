import logging
from typing import Any, List, Optional

import asyncpg

from core.models import OHLCV

logger = logging.getLogger(__name__)

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


class TimescaleDBClient:
    """
    Client for interacting with TimescaleDB using asyncpg.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool[asyncpg.Record]] = None

    async def connect(self) -> None:
        """Initialize the asyncpg connection pool."""
        self.pool = await asyncpg.create_pool(self.dsn)
        logger.info("Connected to TimescaleDB.")

    async def close(self) -> None:
        """Close the asyncpg connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed TimescaleDB connection pool.")

    async def upsert_ohlcv(self, data: List[OHLCV]) -> None:
        """
        Idempotent bulk upsert of OHLCV data using INSERT ... ON CONFLICT DO UPDATE.

        Safe to call multiple times with the same data — re-fetching will never
        create duplicate candles. If the exchange corrects a live candle, the
        updated open/high/low/close/volume values will be written to the DB.
        """
        if not self.pool:
            raise RuntimeError("Database connection pool is not initialized.")

        if not data:
            return

        records: List[tuple[str, Any, float, float, float, float, float, str]] = [
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

        async with self.pool.acquire() as connection:
            await connection.executemany(_UPSERT_SQL, records)
            logger.debug(f"Successfully upserted {len(records)} OHLCV records.")

    async def bulk_insert_ohlcv(self, data: List[OHLCV]) -> None:
        """
        DEPRECATED: Use upsert_ohlcv() instead.

        This function uses copy_records_to_table which does NOT enforce the unique
        constraint and will create duplicate rows on re-fetch.
        """
        if not self.pool:
            raise RuntimeError("Database connection pool is not initialized.")

        if not data:
            return

        records: List[tuple[str, Any, float, float, float, float, float, str]] = [
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

        async with self.pool.acquire() as connection:
            await connection.copy_records_to_table(
                "ohlcv_data",
                records=records,
                columns=[
                    "symbol",
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "timeframe",
                ],
            )
            logger.debug(f"Successfully inserted {len(records)} OHLCV records.")
