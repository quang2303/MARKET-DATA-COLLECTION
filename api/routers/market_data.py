from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime
import asyncpg

from core.models import OHLCV
from core.schemas import MarketDataQuery, TextQueryRequest
from db.database import get_db_connection, get_market_data
from api.llm import parse_text_to_query

router = APIRouter(prefix="/api/v1", tags=["Market Data"])

@router.get("/market-data", response_model=List[OHLCV])
async def get_market_data_endpoint(
    symbol: str = Query(..., description="Trading pair (e.g., BTC/USDT)"),
    timeframe: str = Query(..., description="Timeframe (e.g., 1m, 1h, 1d)"),
    start_time: datetime = Query(..., description="Start timestamp"),
    end_time: datetime = Query(..., description="End timestamp"),
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> List[OHLCV]:
    """
    Query OHLCV market data from TimescaleDB.
    """
    try:
        data = await get_market_data(conn, symbol, timeframe, start_time, end_time)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/query-by-text", response_model=List[OHLCV])
async def query_by_text_endpoint(
    request: TextQueryRequest,
    conn: asyncpg.Connection = Depends(get_db_connection),
) -> List[OHLCV]:
    """
    Accept natural language input from the User, then use Gemini API to extract
    structured parameters and use those parameters to call the DB query function.
    """
    try:
        # 1. Call Gemini API to automatically extract params -> JSON Schema
        parsed_query: MarketDataQuery = parse_text_to_query(request.text)
        
        # 2. Log out for Quant Researcher verification
        print(f"Parsed LLM Output: {parsed_query.model_dump_json(indent=2)}")
        
        # 3. Use the above parameters to invoke the old endpoint/function
        data = await get_market_data(
            conn,
            symbol=parsed_query.symbol,
            timeframe=parsed_query.timeframe,
            start_time=parsed_query.start_time,
            end_time=parsed_query.end_time
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Processing or DB Query Failed: {str(e)}")
