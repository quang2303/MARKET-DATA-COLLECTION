-- db/init.sql

CREATE TABLE IF NOT EXISTS ohlcv_data (
    symbol TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    timeframe TEXT NOT NULL
);

-- Convert to hypertable, partitioned by timestamp
SELECT create_hypertable('ohlcv_data', 'timestamp', if_not_exists => TRUE);

-- Unique constraint to prevent duplicate candles on re-fetch.
-- TimescaleDB requires the partition column (timestamp) to be part of any
-- unique index on a hypertable, which is satisfied here.
-- Migration for existing DB: ALTER TABLE ohlcv_data
--   ADD CONSTRAINT uq_ohlcv_symbol_timeframe_timestamp UNIQUE (symbol, timeframe, timestamp);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ohlcv_symbol_timeframe_timestamp
    ON ohlcv_data (symbol, timeframe, timestamp);

-- Add compression policy (compress chunks older than 30 days)
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe'
);
SELECT add_compression_policy('ohlcv_data', compress_after => INTERVAL '30 days', if_not_exists => TRUE);

-- Add retention policy (drop chunks older than 1 year)
SELECT add_retention_policy('ohlcv_data', drop_after => INTERVAL '1 year', if_not_exists => TRUE);

-- Create users table for API authentication
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL
);
