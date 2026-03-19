"""
seed_db.py

Incrementally seeds (or refreshes) the database using the ingest service.
Safe to re-run — upsert logic ensures no duplicates are created.

Usage:
    python seed_db.py
"""

import asyncio
import logging

from dotenv import load_dotenv

from db import database
from db.database import close_db_pool, init_db_pool
from fetchers.binance import BinanceFetcher
from services.ingest import ingest_ohlcv

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("seed_db")


async def main() -> None:
    logger.info("Loading environment variables...")
    load_dotenv(override=True)

    logger.info("Initializing database connection pool...")
    await init_db_pool()

    try:
        if database.pool is None:
            raise RuntimeError("Database connection pool failed to initialize.")

        fetcher = BinanceFetcher()

        pairs = [
            ("BTCUSDT", "15m"),
            ("BTCUSDT", "1h"),
        ]

        async with database.pool.acquire() as conn:
            for symbol, timeframe in pairs:
                n = await ingest_ohlcv(conn, fetcher, symbol, timeframe)
                logger.info(f"[{symbol}/{timeframe}] Upserted {n} candles.")

        logger.info("Seed complete.")

    except Exception as exc:
        logger.error(f"Seed failed: {exc}", exc_info=True)
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
