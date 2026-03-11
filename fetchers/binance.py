import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.models import OHLCV

logger = logging.getLogger(__name__)


class BinanceFetcher:
    """
    Client components for fetching Market Data from Binance API.
    """

    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        """
        Initializes the Binance URL fetcher.

        Args:
            base_url (str): The base URL for the Binance API.
        """
        self.base_url = base_url

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def fetch_ohlcv(
        self, symbol: str, interval: str, limit: int = 500
    ) -> List[OHLCV]:
        """
        Fetches OHLCV data from Binance API and parses it to a List[OHLCV].
        Handles HTTP 429 Too Many Requests with exponential backoff strategy.

        Args:
            symbol (str): Trading pair symbol (e.g., "BTCUSDT")
            interval (str): Timeframe interval (e.g., "1m", "1h", "1d")
            limit (int, optional): Number of records. Defaults to 500.

        Returns:
            List[OHLCV]: A list of validated OHLCV Pydantic models.
        """
        endpoint = f"{self.base_url}/api/v3/klines"
        params: Dict[str, str | int] = {"symbol": symbol, "interval": interval, "limit": limit}

        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, params=params)

            # Raise an HTTPStatusError if one occurred.
            if response.status_code == 429:
                logger.warning("Binance API Rate Limit Exceeded (HTTP 429). Retrying...")
                response.raise_for_status()
            elif response.status_code != 200:
                logger.error(f"Binance API returned {response.status_code}: {response.text}")
                response.raise_for_status()

            data: List[List[Any]] = response.json()

        return self._parse_binance_klines(symbol, interval, data)

    def _parse_binance_klines(
        self, symbol: str, timeframe: str, data: List[List[Any]]
    ) -> List[OHLCV]:
        """
        Parses raw list of lists responses from Binance into OHLCV core models.

        Args:
            symbol (str): The trading symbol.
            timeframe (str): The requested timeframe.
            data (List[List[Any]]): Raw klines from Binance.

        Returns:
            List[OHLCV]: Parsed list of models.
        """
        parsed_data: List[OHLCV] = []
        for row in data:
            # Binance kline format:
            # [
            #   Open time (0), Open (1), High (2), Low (3), Close (4), Volume (5),
            #   Close time (6), Quote asset volume (7), ...
            # ]
            open_time_ms = int(row[0])
            open_price = float(row[1])
            high_price = float(row[2])
            low_price = float(row[3])
            close_price = float(row[4])
            volume = float(row[5])

            timestamp = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc)

            # Standardize symbol formatting (e.g. BTCUSDT -> BTC/USDT)
            standard_symbol = f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith("USDT") else symbol

            ohlcv = OHLCV(
                symbol=standard_symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                timeframe=timeframe,
            )
            parsed_data.append(ohlcv)

        return parsed_data
