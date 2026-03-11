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

-- Add compression policy (compress chunks older than 30 days)
ALTER TABLE ohlcv_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe'
);
SELECT add_compression_policy('ohlcv_data', compress_after => INTERVAL '30 days', if_not_exists => TRUE);

-- Add retention policy (drop chunks older than 1 year)
SELECT add_retention_policy('ohlcv_data', drop_after => INTERVAL '1 year', if_not_exists => TRUE);
