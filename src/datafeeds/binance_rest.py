"""
Binance REST API for historical data backfill.
Implements retry logic with exponential backoff for resilience.
"""
import asyncio
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone
import requests
from loguru import logger

BINANCE_API_BASE = "https://api.binance.com"


class BinanceRESTClient:
    """Client for Binance REST API with retry logic."""

    def __init__(self, max_retries: int = 3, timeout: int = 10):
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = requests.Session()

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff on failure."""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
                if attempt == self.max_retries - 1:
                    # Final attempt failed
                    logger.error(f"Binance REST API failed after {self.max_retries} attempts: {e}")
                    raise

                # Exponential backoff: 1s, 2s, 4s
                backoff = 2 ** attempt
                logger.warning(f"Binance REST API attempt {attempt + 1} failed, retrying in {backoff}s: {e}")
                time.sleep(backoff)

    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[List]:
        """
        Fetch historical klines (candlestick data).

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "1h", "4h", "1d", "1w")
            limit: Number of candles (max 1000, default 500)
            start_time: Start timestamp in ms (optional)
            end_time: End timestamp in ms (optional)

        Returns:
            List of klines in Binance format:
            [
                [open_time, open, high, low, close, volume, close_time,
                 quote_volume, num_trades, taker_buy_base, taker_buy_quote, ignore]
            ]
        """
        def _fetch():
            url = f"{BINANCE_API_BASE}/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": min(limit, 1000)  # Binance max is 1000
            }

            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        return self._retry_with_backoff(_fetch)

    def get_server_time(self) -> int:
        """Get Binance server time in ms (for sync check)."""
        def _fetch():
            url = f"{BINANCE_API_BASE}/api/v3/time"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()["serverTime"]

        return self._retry_with_backoff(_fetch)


def normalize_binance_kline(symbol: str, interval: str, kline: List) -> Dict:
    """
    Convert Binance REST kline format to our internal format.

    Binance format:
    [open_time, open, high, low, close, volume, close_time,
     quote_volume, num_trades, taker_buy_base, taker_buy_quote, ignore]
    """
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "open_time": int(kline[0]),
        "close_time": int(kline[6]),
        "open": float(kline[1]),
        "high": float(kline[2]),
        "low": float(kline[3]),
        "close": float(kline[4]),
        "volume": float(kline[5]),
        "is_closed": True  # Historical data is always closed
    }


async def backfill_historical_data(
    symbol: str,
    timeframes: List[str],
    limit: int = 200
) -> Dict[str, int]:
    """
    Backfill historical candles for given symbol and timeframes.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        timeframes: List of intervals (e.g., ["1h", "4h", "1d", "1w"])
        limit: Number of candles to fetch per timeframe

    Returns:
        Dict with count of candles saved per timeframe
        Example: {"1h": 200, "4h": 200, "1d": 200, "1w": 200}
    """
    from src.storage.repo import save_candle_event

    client = BinanceRESTClient()
    results = {}

    logger.info(f"Starting backfill for {symbol} on timeframes: {timeframes}")

    for interval in timeframes:
        try:
            # Fetch historical klines
            logger.info(f"Fetching {limit} candles for {symbol} {interval}...")
            klines = await asyncio.to_thread(
                client.get_klines,
                symbol=symbol,
                interval=interval,
                limit=limit
            )

            # Normalize and save
            saved_count = 0
            for kline in klines:
                candle = normalize_binance_kline(symbol, interval, kline)
                if save_candle_event(candle):
                    saved_count += 1

            results[interval] = saved_count
            logger.info(f"Backfill {symbol} {interval}: {saved_count}/{len(klines)} candles saved")

        except Exception as e:
            logger.error(f"Backfill failed for {symbol} {interval}: {e}")
            results[interval] = 0

    total_saved = sum(results.values())
    logger.info(f"Backfill completed: {total_saved} total candles saved across {len(timeframes)} timeframes")

    return results


async def backfill_all_symbols(config_symbols: List[Dict]) -> Dict[str, Dict[str, int]]:
    """
    Backfill all symbols from config.

    Args:
        config_symbols: List of symbol configs from YAML
            Example: [{"name": "BTCUSDT", "timeframes": ["1h", "4h", "1d", "1w"]}]

    Returns:
        Dict with results per symbol
        Example: {"BTCUSDT": {"1h": 200, "4h": 200, ...}}
    """
    results = {}

    for sym_config in config_symbols:
        symbol = sym_config["name"]
        timeframes = sym_config["timeframes"]

        results[symbol] = await backfill_historical_data(symbol, timeframes)

    return results
