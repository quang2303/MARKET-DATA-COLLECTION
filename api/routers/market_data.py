from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Query
from google.api_core.exceptions import GoogleAPIError
from pydantic import ValidationError

from api.errors import StructuredHTTPException
from api.llm import parse_text_to_query
from api.routers.auth import get_current_user
from core.models import OHLCV
from core.schemas import MarketDataQuery, TextQueryRequest
from db.crud import get_market_data
from db.database import get_db_connection

router = APIRouter(prefix="/api/v1", tags=["Market Data"])


@router.get("/market-data", response_model=list[OHLCV])
async def get_market_data_endpoint(
    query: MarketDataQuery = Depends(),
    conn: asyncpg.Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> list[OHLCV]:
    """
    Query OHLCV market data from TimescaleDB.
    """
    try:
        data = await get_market_data(
            conn, query.symbol, query.timeframe, query.start_time, query.end_time, query.limit
        )
        if not data:
            raise StructuredHTTPException(
                status_code=404,
                error="Not Found",
                detail="No market data found for the given parameters.",
                code="NO_DATA_FOUND",
                source="database",
            )
        return data
    except StructuredHTTPException:
        raise
    except asyncpg.PostgresError as e:
        raise StructuredHTTPException(
            status_code=500,
            error="Database Error",
            detail="Failed to query the database.",
            code="DB_QUERY_FAILED",
            source="database",
        ) from e
    except Exception as e:
        raise StructuredHTTPException(
            status_code=500,
            error="Internal Server Error",
            detail="An unexpected error occurred while processing the request.",
            code="INTERNAL_ERROR",
        ) from e


@router.post("/query-by-text", response_model=list[OHLCV])
async def query_by_text_endpoint(
    request: TextQueryRequest,
    conn: asyncpg.Connection = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user),
) -> list[OHLCV]:
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
            end_time=parsed_query.end_time,
            limit=parsed_query.limit,
        )
        
        if not data:
            raise StructuredHTTPException(
                status_code=404,
                error="Not Found",
                detail="The extracted query resulted in no market data.",
                code="NO_DATA_FOUND",
                source="database",
            )
            
        return data
    except StructuredHTTPException:
        raise
    except ValidationError:
        raise StructuredHTTPException(
            status_code=400,
            error="Bad Request",
            detail="LLM failed to parse the natural language query into valid parameters.",
            code="LLM_PARSE_FAILED",
            source="llm_provider",
        )
    except ValueError as e:
        if "empty response" in str(e).lower():
            raise StructuredHTTPException(
                status_code=502,
                error="Bad Gateway",
                detail="LLM returned empty response.",
                code="LLM_EMPTY_OUTPUT",
                source="llm_provider",
            ) from e
        
        raise StructuredHTTPException(
            status_code=500,
            error="Internal Server Error",
            detail="An unexpected error occurred.",
            code="INTERNAL_ERROR",
        ) from e
    except GoogleAPIError as e:
        raise StructuredHTTPException(
            status_code=502,
            error="Bad Gateway",
            detail="External LLM provider error (timeout or unavailable).",
            code="LLM_PROVIDER_ERROR",
            source="llm_provider",
        ) from e
    except asyncpg.PostgresError as e:
        raise StructuredHTTPException(
            status_code=500,
            error="Database Error",
            detail="Failed to query the database using the extracted parameters.",
            code="DB_QUERY_FAILED",
            source="database",
        ) from e
    except Exception as e:
        raise StructuredHTTPException(
            status_code=500,
            error="Internal Server Error",
            detail="An unexpected error occurred while processing the natural language query.",
            code="INTERNAL_ERROR",
        ) from e
