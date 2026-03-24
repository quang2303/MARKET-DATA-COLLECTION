from datetime import datetime, timedelta
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    limit: int = Field(default=1000, le=10000, description="Max number of records to return")
    
    ALLOWED_TIMEFRAMES: ClassVar[set[str]] = {
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M"
    }

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Symbol cannot be empty")
        return v

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        if v not in cls.ALLOWED_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe. Allowed: {', '.join(sorted(cls.ALLOWED_TIMEFRAMES))}")
        return v

    @model_validator(mode="after")
    def validate_times(self) -> "MarketDataQuery":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        if self.end_time - self.start_time > timedelta(days=365):
            raise ValueError("Time range cannot exceed 365 days")
        return self


class TextQueryRequest(BaseModel):
    """
    Schema for the request body of the POST /query-by-text endpoint.
    """

    text: str = Field(
        ...,
        description=(
            "Natural language query from user "
            "(e.g., 'Get BTC 1H price for the last 3 days')"
        ),
    )
