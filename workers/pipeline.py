import argparse
import asyncio
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv

from db.database import close_db_pool, init_db_pool, pool
from fetchers.binance import BinanceFetcher
from services.ingest import ingest_ohlcv

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("worker")


async def run_once(
    symbol: str, timeframe: str, start_time: datetime | None, end_time: datetime | None
) -> None:
    """Run a single ingest cycle (or backfill window) and exit."""
    logger.info("Initializing database connection pool...")
    await init_db_pool()
    try:
        if pool is None:
            raise RuntimeError("Database connection pool failed to initialize.")

        fetcher = BinanceFetcher()

        async with pool.acquire() as conn:
            n = await ingest_ohlcv(
                conn, fetcher, symbol, timeframe, start_time, end_time
            )
            logger.info(
                f"[INGEST] Processed {n} candles for {symbol} ({timeframe})."
            )
    except Exception as exc:
        logger.error(f"Ingest failed: {exc}", exc_info=True)
    finally:
        await close_db_pool()


async def run_daemon(symbol: str, timeframe: str, interval_seconds: int) -> None:
    """Run an infinite ingest loop, pausing for 'interval_seconds'."""
    logger.info("Initializing database connection pool...")
    await init_db_pool()
    try:
        if pool is None:
            raise RuntimeError("Database connection pool failed to initialize.")

        fetcher = BinanceFetcher()
        logger.info(
            f"[DAEMON] Starting loop for {symbol} ({timeframe}) "
            f"every {interval_seconds}s."
        )

        while True:
            try:
                async with pool.acquire() as conn:
                    n = await ingest_ohlcv(conn, fetcher, symbol, timeframe)
                    logger.info(f"    -> Upserted {n} candles.")
            except Exception as e:
                logger.error(f"Daemon encountered an error: {e}", exc_info=True)

            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        logger.info("[DAEMON] Received cancellation signal. Shutting down...")
    finally:
        await close_db_pool()


def main() -> None:
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(
        description="Market Data Ingestion Pipeline",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Sub-command 1: ingest
    ingest_parser = subparsers.add_parser(
        "ingest", help="Run a single incremental ingest or explicit backfill"
    )
    ingest_parser.add_argument(
        "--symbol", type=str, required=True, help="Trading pair, e.g., BTCUSDT"
    )
    ingest_parser.add_argument(
        "--timeframe", type=str, required=True, help="Candle interval, e.g., 1h, 15m"
    )
    ingest_parser.add_argument(
        "--start", type=str, help="ISO 8601 start time (UTC), e.g., 2024-01-01T00:00:00Z"
    )
    ingest_parser.add_argument(
        "--end", type=str, help="ISO 8601 end time (UTC)"
    )

    # Sub-command 2: daemon
    daemon_parser = subparsers.add_parser(
        "daemon", help="Run ingest periodically in an infinite loop"
    )
    daemon_parser.add_argument(
        "--symbol", type=str, required=True, help="Trading pair, e.g., BTCUSDT"
    )
    daemon_parser.add_argument(
        "--timeframe", type=str, required=True, help="Candle interval, e.g., 1h, 15m"
    )
    daemon_parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Wait time between syncs in seconds (default: 3600)",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        start_time = None
        if args.start:
            start_time = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)

        end_time = None
        if args.end:
            end_time = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

        asyncio.run(run_once(args.symbol, args.timeframe, start_time, end_time))

    elif args.command == "daemon":
        try:
            asyncio.run(run_daemon(args.symbol, args.timeframe, args.interval))
        except KeyboardInterrupt:
            logger.info("Exiting daemon gracefully...")


if __name__ == "__main__":
    main()
