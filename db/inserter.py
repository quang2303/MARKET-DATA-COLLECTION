from typing import Any, List, Tuple

import asyncpg  # type: ignore

from core.models import OHLCV


async def bulk_insert_ohlcv(
    connection: asyncpg.Connection, table_name: str, data: List[OHLCV]
) -> None:
    """
    Bulk inserts a list of OHLCV Pydantic models into a PostgreSQL table using
    asyncpg's copy_records_to_table for maximum insertion performance.

    Args:
        connection (asyncpg.Connection): An active asyncpg connection.
        table_name (str): The target table name for the insertion.
        data (List[OHLCV]): The sequence of OHLCV models to be inserted.
    """
    if not data:
        return

    # Transform List[OHLCV] to List[Tuple] matching the column order exactly
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
