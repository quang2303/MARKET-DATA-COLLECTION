from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketDataQuery(BaseModel):
    """
    Schema for Market Data query parameters.
    Used for both GET API query parameters and Gemini API Structured Output.
    """
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTC/USDT)")
    timeframe: str = Field(..., description="Candle timeframe (e.g., 1m, 1h, 1d)")
    start_time: datetime = Field(..., description="Start time for the data query")
    end_time: datetime = Field(..., description="End time for the data query")

class TextQueryRequest(BaseModel):
    """
    Schema for the request body of the POST /query-by-text endpoint.
    """
    text: str = Field(..., description="Natural language query from user (e.g., 'Get BTC 1H price for the last 3 days')")
