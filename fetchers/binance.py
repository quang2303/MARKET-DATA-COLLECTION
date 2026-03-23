import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.models import OHLCV

logger = logging.getLogger(__name__)

# Binance hard limit per request
_BINANCE_MAX_LIMIT = 1000


class BinanceFetcher:
    """
    Client components for fetching Market Data from Binance API.

    Supports both simple limit-based fetches and time-range fetches
    with automatic pagination for large time intervals.
    """

    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        """
        Initializes the Binance URL fetcher.

        Args:
            base_url (str): The base URL for the Binance API.
        """
        self.base_url = base_url

    async def fetch_ohlcv(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[OHLCV]:
        """
        Fetches OHLCV data from Binance API and parses it into List[OHLCV].

        When ``start_time`` is provided the fetcher paginates automatically
        until all candles in the requested range have been collected.
        When only ``limit`` is provided (legacy mode) a single request is made.

        Args:
            symbol (str): Trading pair symbol, exchange-native format (e.g. "BTCUSDT").
            interval (str): Timeframe interval (e.g. "1m", "1h", "1d").
            limit (int): Max candles per request when NOT using start_time.
                Defaults to 500.
            start_time (datetime | None): Inclusive range start (UTC-aware).
                If provided, pagination is used and ``limit`` is ignored.
            end_time (datetime | None): Inclusive range end (UTC-aware).
                Defaults to now.

        Returns:
            List[OHLCV]: A deduplicated, time-ordered list of validated OHLCV models.
        """
        if start_time is not None:
            return await self._fetch_range(symbol, interval, start_time, end_time)
        else:
            return await self._fetch_page(symbol, interval, limit=limit)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _fetch_page(
        self,
        symbol: str,
        interval: str,
        limit: int = _BINANCE_MAX_LIMIT,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[OHLCV]:
        """
        Fetches a single page of klines from Binance.
        Handles HTTP 429 with exponential backoff via @retry.

        Args:
            symbol (str): Exchange-native symbol (e.g. "BTCUSDT").
            interval (str): Binance interval string.
            limit (int): Max candles to return (Binance cap: 1000).
            start_time_ms (int | None): startTime in Unix milliseconds.
            end_time_ms (int | None): endTime in Unix milliseconds.

        Returns:
            List[OHLCV]: Parsed and validated OHLCV models for this page.
        """
        endpoint = f"{self.base_url}/api/v3/klines"
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, _BINANCE_MAX_LIMIT),
        }
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        if end_time_ms is not None:
            params["endTime"] = end_time_ms

        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, params=params)

            if response.status_code == 429:
                logger.warning(
                    "Binance API Rate Limit Exceeded (HTTP 429). Retrying..."
                )
                response.raise_for_status()
            elif response.status_code != 200:
                logger.error(
                    f"Binance API returned {response.status_code}: {response.text}"
                )
                response.raise_for_status()

            data: list[list[Any]] = response.json()

        return self._parse_binance_klines(symbol, interval, data)

    async def _fetch_range(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime | None = None,
    ) -> list[OHLCV]:
        """
        Paginates through Binance kline API to collect all candles in
        [start_time, end_time].  Each page advances the cursor to the
        timestamp immediately after the last returned candle.

        Args:
            symbol (str): Exchange-native symbol (e.g. "BTCUSDT").
            interval (str): Binance interval string.
            start_time (datetime): Inclusive start (UTC-aware).
            end_time (datetime | None): Inclusive end (UTC-aware). Defaults to now.

        Returns:
            List[OHLCV]: Full, ordered, time-contiguous list across all pages.
        """
        if end_time is None:
            end_time = datetime.now(tz=timezone.utc)

        cursor_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        all_candles: list[OHLCV] = []

        while cursor_ms <= end_ms:
            page = await self._fetch_page(
                symbol,
                interval,
                limit=_BINANCE_MAX_LIMIT,
                start_time_ms=cursor_ms,
                end_time_ms=end_ms,
            )

            if not page:
                # No more data available in the requested range
                break

            all_candles.extend(page)
            logger.debug(
                f"Fetched page: {len(page)} candles "
                f"({page[0].timestamp.isoformat()} → {page[-1].timestamp.isoformat()})"
            )

            # Advance cursor: last candle's timestamp + 1 ms to avoid re-fetching it
            last_ts_ms = int(page[-1].timestamp.timestamp() * 1000)
            if last_ts_ms <= cursor_ms:
                # Safety guard: if cursor didn't advance, break to avoid infinite loop
                logger.warning(
                    "Pagination cursor did not advance. "
                    "Stopping to prevent infinite loop."
                )
                break
            cursor_ms = last_ts_ms + 1

        logger.info(
            f"[{symbol}/{interval}] Fetched {len(all_candles)} candles total "
            f"from {start_time.isoformat()} to {end_time.isoformat()}"
        )
        return all_candles

    def _parse_binance_klines(
        self, symbol: str, timeframe: str, data: list[list[Any]]
    ) -> list[OHLCV]:
        """
        Parses raw list-of-lists responses from Binance into OHLCV core models.

        Args:
            symbol (str): The trading symbol.
            timeframe (str): The requested timeframe.
            data (List[List[Any]]): Raw klines from Binance.

        Returns:
            List[OHLCV]: Parsed list of models.
        """
        # Standardize symbol formatting (e.g. BTCUSDT -> BTC/USDT)
        standard_symbol = (
            f"{symbol[:-4]}/{symbol[-4:]}" if symbol.endswith("USDT") else symbol
        )

        parsed_data: list[OHLCV] = []
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
