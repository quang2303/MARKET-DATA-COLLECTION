from typing import Any, List, Tuple

import asyncpg  # type: ignore

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


async def upsert_ohlcv(
    connection: asyncpg.Connection, data: List[OHLCV]
) -> None:
    """
    Idempotent bulk upsert of OHLCV data using INSERT ... ON CONFLICT DO UPDATE.

    Safe to call multiple times with the same data — re-fetching will never
    create duplicate candles. If the exchange corrects a live candle, the
    updated open/high/low/close/volume values will be written to the DB.

    Args:
        connection: An active asyncpg connection.
        data: The list of OHLCV models to upsert.
    """
    if not data:
        return

    records: List[Tuple[Any, ...]] = [
        (
            record.symbol,
            record.timestamp,
            record.open,
            record.high,
            record.low,
            record.close,
            record.volume,
            record.timeframe,
        )
        for record in data
    ]

    await connection.executemany(_UPSERT_SQL, records)


async def bulk_insert_ohlcv(
    connection: asyncpg.Connection, table_name: str, data: List[OHLCV]
) -> None:
    """
    DEPRECATED: Use upsert_ohlcv() instead.

    This function uses copy_records_to_table which does NOT enforce the unique
    constraint and will create duplicate rows on re-fetch.

    Kept for backward compatibility only — do not call for new code.
    """
    if not data:
        return

    records: List[Tuple[Any, ...]] = [
        (
            record.symbol,
            record.timestamp,
            record.open,
            record.high,
            record.low,
            record.close,
            record.volume,
            record.timeframe,
        )
        for record in data
    ]

    columns = (
        "symbol",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "timeframe",
    )

    await connection.copy_records_to_table(table_name, records=records, columns=columns)
