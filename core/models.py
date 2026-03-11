from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class OHLCV(BaseModel):
    """
    Standard OHLCV (Open, High, Low, Close, Volume) data model.
    Every module in the system (fetchers, db, api) must strictly use this model 
    for data exchange to ensure data integrity and consistency.
    """
    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., description="Trading pair symbol (e.g., BTC/USDT)")
    timestamp: datetime = Field(..., description="Timestamp of the candle (start time)")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price during the interval")
    low: float = Field(..., description="Lowest price during the interval")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Trading volume during the interval")
    timeframe: str = Field(..., description="Candle timeframe (e.g., 1m, 1h, 1d)")
