from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from typing import AsyncGenerator
import logging

# Set up simple logging
logger = logging.getLogger("market_data_api")

# Import database lifecycle events
from db.database import init_db_pool, close_db_pool

# Import the market data router
from api.routers.market_data import router as market_data_router

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup event: Initialize DB pool
    try:
        await init_db_pool()
        logger.info("Database connection pool initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize database pool: {e}. Some endpoints may not work.")
    yield
    # Shutdown event: Close DB pool
    await close_db_pool()

app = FastAPI(
    title="Market Data Collection & Distribution System",
    description="A robust system for handling crypto and stock market data, augmented with an LLM.",
    version="0.1.0",
    lifespan=lifespan,
)

# Include Routers
app.include_router(market_data_router)

@app.get("/health")
async def health_check() -> dict[str, str]:
    """
    Basic health check endpoint.
    """
    return {"status": "ok"}
