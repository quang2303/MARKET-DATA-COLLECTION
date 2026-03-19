-- db/migrations/001_add_unique_constraint_ohlcv.sql
--
-- Migration: Add UNIQUE index on ohlcv_data to prevent duplicate candles.
-- Run this ONCE on an existing database before using upsert_ohlcv().
--
-- Note: On TimescaleDB hypertables the partition column (timestamp) MUST be
-- part of any unique index. This index satisfies that requirement.
--
-- Rollback:
--   DROP INDEX IF EXISTS uq_ohlcv_symbol_timeframe_timestamp;

-- STEP 1: Clean up existing duplicates, keeping the latest inserted row.
-- Skip this step if the table is empty or you are certain there are no duplicates.
DELETE FROM ohlcv_data
WHERE ctid NOT IN (
    SELECT MAX(ctid)
    FROM ohlcv_data
    GROUP BY symbol, timeframe, timestamp
);

-- STEP 2: Create the unique index.
CREATE UNIQUE INDEX IF NOT EXISTS uq_ohlcv_symbol_timeframe_timestamp
    ON ohlcv_data (symbol, timeframe, timestamp);
