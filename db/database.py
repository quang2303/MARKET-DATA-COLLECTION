import os
from collections.abc import AsyncGenerator

import asyncpg

# Global connection pool instance
pool: asyncpg.Pool | None = None


async def init_db_pool() -> None:
    """
    Initialize connection pool for the database.
    This function should be called at FastAPI startup.
    """
    global pool
    db_url = os.getenv(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/market_data"
    )
    pool = await asyncpg.create_pool(db_url)


async def close_db_pool() -> None:
    """
    Close the connection pool.
    This function should be called at FastAPI shutdown.
    """
    global pool
    if pool is not None:
        await pool.close()


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    FastAPI Dependency to provide database connections for API endpoints.
    """
    if pool is None:
        raise RuntimeError("Database pool is not initialized")
    async with pool.acquire() as conn:
        yield conn
