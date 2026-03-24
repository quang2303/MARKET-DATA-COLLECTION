"""
services/ingest.py

Incremental + idempotent OHLCV ingest orchestrator.

Usage — normal incremental run (resumes from last stored candle):

    async with pool.acquire() as conn:
        n = await ingest_ohlcv(conn, fetcher, "BTCUSDT", "1h")
        print(f"Upserted {n} candles")

Usage — explicit backfill of a missed window:

    from datetime import datetime, timezone
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end   = datetime(2026, 3, 10, tzinfo=timezone.utc)
    async with pool.acquire() as conn:
        n = await ingest_ohlcv(conn, fetcher, "BTCUSDT", "1h",
                               start_time=start, end_time=end)
"""

import logging
from datetime import datetime, timedelta, timezone

import asyncpg

from db.crud import get_latest_timestamp, upsert_ohlcv
from fetchers.binance import BinanceFetcher

logger = logging.getLogger(__name__)

# Safety overlap subtracted from max(timestamp) on each incremental run.
# Ensures the boundary candle is always re-fetched and compared, protecting
# against partial writes or late corrections by the exchange.
_DEFAULT_OVERLAP = timedelta(minutes=1)

# How far back to seed when the DB has no data at all for a given pair.
_DEFAULT_INITIAL_LOOKBACK = timedelta(days=7)


async def ingest_ohlcv(
    conn: asyncpg.Connection,
    fetcher: BinanceFetcher,
    symbol: str,
    timeframe: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    overlap: timedelta = _DEFAULT_OVERLAP,
    initial_lookback: timedelta = _DEFAULT_INITIAL_LOOKBACK,
) -> int:
    """
    Fetch candles from Binance and upsert them into the DB — incrementally
    and idempotently.

    Behaviour
    ---------
    1. If ``start_time`` is **not** provided, read ``MAX(timestamp)`` from the
       DB for (symbol, timeframe).  Subtract ``overlap`` from that value to
       create a small safety window that recaptures any candle that may have
       been missed right at the boundary.
    2. If the DB is completely empty for this pair, fall back to
       ``now() - initial_lookback`` as the start time.
    3. Call the paginated ``BinanceFetcher.fetch_ohlcv()`` with the resolved
       ``[start_time, end_time]`` range — multiple HTTP pages are handled
       transparently inside the fetcher.
    4. Call ``upsert_ohlcv()`` which executes ``INSERT … ON CONFLICT DO UPDATE``
       — completely safe to call with overlapping / duplicate rows from the
       safety window.

    Args:
        conn: Active asyncpg connection (acquired from pool by caller).
        fetcher: Configured ``BinanceFetcher`` instance.
        symbol: Exchange-native symbol, e.g. ``"BTCUSDT"``.
        timeframe: Candle interval, e.g. ``"1h"``, ``"15m"``.
        start_time: Explicit range start (UTC-aware).  If ``None``, the DB
            max-timestamp is used (incremental mode).
        end_time: Explicit range end (UTC-aware).  Defaults to ``datetime.now(UTC)``.
        overlap: Safety window subtracted from ``max(timestamp)`` in incremental
            mode.  Default: 1 minute.
        initial_lookback: How far back to seed when the DB is empty.  Default: 7 days.

    Returns:
        Number of candle records passed to ``upsert_ohlcv()`` (includes
        overlap rows that will be no-ops in the DB).
    """
    # --- Standardise symbol for DB queries (BinanceFetcher handles native format) ---
    std_symbol = f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith("USDT") else symbol

    # --- Resolve start_time ---
    if start_time is None:
        latest_ts = await get_latest_timestamp(conn, std_symbol, timeframe)
        if latest_ts is not None:
            start_time = latest_ts - overlap
            logger.info(
                f"[{std_symbol}/{timeframe}] Incremental mode: "
                f"DB max_ts={latest_ts.isoformat()}, "
                f"fetching from {start_time.isoformat()} (overlap={overlap})"
            )
        else:
            start_time = datetime.now(tz=timezone.utc) - initial_lookback
            logger.info(
                f"[{std_symbol}/{timeframe}] No data in DB yet — "
                f"seeding from {start_time.isoformat()} (lookback={initial_lookback})"
            )

    # --- Fetch (paginated internally by BinanceFetcher) ---
    data = await fetcher.fetch_ohlcv(
        symbol=symbol,
        interval=timeframe,
        start_time=start_time,
        end_time=end_time,
    )

    if not data:
        logger.info(f"[{std_symbol}/{timeframe}] No new candles returned by fetcher.")
        return 0

    # --- Upsert (idempotent: ON CONFLICT DO UPDATE) ---
    await upsert_ohlcv(conn, data)
    logger.info(
        f"[{std_symbol}/{timeframe}] Upserted {len(data)} candles "
        f"(latest: {data[-1].timestamp.isoformat()})"
    )
    return len(data)
