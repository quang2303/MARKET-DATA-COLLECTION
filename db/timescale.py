import logging
from typing import Any, List, Optional

import asyncpg

from core.models import OHLCV

logger = logging.getLogger(__name__)


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

    async def bulk_insert_ohlcv(self, data: List[OHLCV]) -> None:
        """
        Perform high-speed bulk insert of OHLCV data using copy_records_to_table.
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
