import asyncio
from dotenv import load_dotenv

from fetchers.binance import BinanceFetcher
from db.timescale import TimescaleDBClient
from db.database import init_db_pool, pool, close_db_pool, upsert_ohlcv

async def main():
    print("Loading environment variables...")
    load_dotenv(override=True)
    
    print("Initializing Database connection...")
    await init_db_pool()
    
    try:
        from db import database
        if database.pool is None:
            raise RuntimeError("Database connection failed.")
            
        print("Fetching data from Binance...")
        fetcher = BinanceFetcher()
        # Fetch 500 candles of 15m timeframe for BTC/USDT
        data_15m = await fetcher.fetch_ohlcv("BTCUSDT", "15m", limit=500)
        print(f"Fetched {len(data_15m)} 15m candles.")
        
        # Fetch 500 candles of 1h timeframe for BTC/USDT
        data_1h = await fetcher.fetch_ohlcv("BTCUSDT", "1h", limit=500)
        print(f"Fetched {len(data_1h)} 1h candles.")
        
        print("Upserting data into TimescaleDB (idempotent — safe to re-run)...")
        async with database.pool.acquire() as conn:
            await upsert_ohlcv(conn, data_15m)
            await upsert_ohlcv(conn, data_1h)
            
        print("Successfully seeded the database!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await close_db_pool()

if __name__ == "__main__":
    asyncio.run(main())
