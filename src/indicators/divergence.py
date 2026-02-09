"""RSI Divergence detection (bullish/bearish) - TradingView-style pivot detection."""
from typing import Optional, List
from loguru import logger


def find_rsi_pivot_low(
    rsi_values: List[Optional[float]], center: int, left: int, right: int
) -> bool:
    """
    Check if RSI at center index is the lowest within the window [center-left, center+right].
    Equivalent to ta.pivotlow(rsi, left, right) in PineScript.

    Args:
        rsi_values: Full list of RSI values (oldest first)
        center: Index of the candidate pivot
        left: Number of bars to check to the left
        right: Number of bars to check to the right

    Returns:
        True if rsi[center] is strictly less than all neighbors in the window
    """
    if center < left or center + right >= len(rsi_values):
        return False

    center_val = rsi_values[center]
    if center_val is None:
        return False

    for i in range(center - left, center + right + 1):
        if i == center:
            continue
        if rsi_values[i] is None:
            return False
        if center_val >= rsi_values[i]:
            return False

    return True


def find_rsi_pivot_high(
    rsi_values: List[Optional[float]], center: int, left: int, right: int
) -> bool:
    """
    Check if RSI at center index is the highest within the window [center-left, center+right].
    Equivalent to ta.pivothigh(rsi, left, right) in PineScript.

    Args:
        rsi_values: Full list of RSI values (oldest first)
        center: Index of the candidate pivot
        left: Number of bars to check to the left
        right: Number of bars to check to the right

    Returns:
        True if rsi[center] is strictly greater than all neighbors in the window
    """
    if center < left or center + right >= len(rsi_values):
        return False

    center_val = rsi_values[center]
    if center_val is None:
        return False

    for i in range(center - left, center + right + 1):
        if i == center:
            continue
        if rsi_values[i] is None:
            return False
        if center_val <= rsi_values[i]:
            return False

    return True


def detect_divergence(
    current_price: float,
    current_rsi: float,
    prev_price: float,
    prev_rsi: float,
    div_type: str,
    bullish_rsi_max: float = 40,
    bearish_rsi_min: float = 60
) -> Optional[str]:
    """
    Detect divergence between two pivots.

    For bullish: current_price and prev_price should be candle LOWs.
    For bearish: current_price and prev_price should be candle HIGHs.

    Args:
        current_price: Price of current pivot (low for bullish, high for bearish)
        current_rsi: RSI of current pivot
        prev_price: Price of previous pivot (low for bullish, high for bearish)
        prev_rsi: RSI of previous pivot
        div_type: "BULLISH" or "BEARISH"
        bullish_rsi_max: Maximum RSI value for bullish divergence (default: 40)
        bearish_rsi_min: Minimum RSI value for bearish divergence (default: 60)

    Returns:
        "BULLISH" or "BEARISH" if divergence detected, None otherwise
    """
    if div_type == "BULLISH":
        # Bullish: Price makes lower low, RSI makes higher low
        # AND both RSI values < bullish_rsi_max
        if (current_price < prev_price and
            current_rsi > prev_rsi and
            current_rsi < bullish_rsi_max and
            prev_rsi < bullish_rsi_max):
            return "BULLISH"

    elif div_type == "BEARISH":
        # Bearish: Price makes higher high, RSI makes lower high
        # AND both RSI values > bearish_rsi_min
        if (current_price > prev_price and
            current_rsi < prev_rsi and
            current_rsi > bearish_rsi_min and
            prev_rsi > bearish_rsi_min):
            return "BEARISH"

    return None


def fetch_candles_for_divergence(
    symbol: str,
    interval: str,
    lookback: int = 80
) -> List[dict]:
    """
    Fetch recent candles for divergence detection.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "4h", "1d", "1w")
        lookback: Number of candles to fetch (default 80)

    Returns:
        List of candle dicts (oldest first) with keys: close, low, high, open_time, is_closed.
        Empty list if failed.
    """
    from src.storage.db import SessionLocal
    from src.storage.models import Candle
    from sqlalchemy import and_

    try:
        with SessionLocal() as session:
            candles = session.query(Candle).filter(
                and_(
                    Candle.symbol == symbol,
                    Candle.interval == interval
                )
            ).order_by(Candle.open_time.desc()).limit(lookback).all()

            if not candles:
                logger.debug(f"No candles found for divergence {symbol} {interval}")
                return []

            # Convert to dicts inside session to avoid detached ORM objects
            result = [
                {
                    "close": c.close,
                    "low": c.low,
                    "high": c.high,
                    "open_time": c.open_time,
                    "is_closed": c.is_closed,
                }
                for c in reversed(candles)
            ]
            return result

    except Exception as e:
        logger.error(f"Failed to fetch divergence candles {symbol} {interval}: {e}")
        return []


def calculate_rsi_for_candles(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Calculate RSI for each candle using Wilder's incremental smoothing (O(n)).

    Args:
        closes: List of closing prices (oldest first)
        period: RSI period (default 14)

    Returns:
        List of RSI values (oldest first), None for first `period` candles
    """
    n = len(closes)
    rsi_values: List[Optional[float]] = [None] * n

    if n < period + 1:
        return rsi_values

    # Calculate price changes
    changes = [closes[i] - closes[i - 1] for i in range(1, n)]

    # Initial average gain/loss (SMA for first period)
    avg_gain = sum(max(c, 0) for c in changes[:period]) / period
    avg_loss = sum(abs(min(c, 0)) for c in changes[:period]) / period

    # RSI for the first complete period
    if avg_loss == 0:
        rsi_values[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_values[period] = round(100 - (100 / (1 + rs)), 2)

    # Wilder's smoothing for subsequent values
    for i in range(period, len(changes)):
        change = changes[i]
        gain = max(change, 0)
        loss = abs(min(change, 0))

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[i + 1] = round(100 - (100 / (1 + rs)), 2)

    return rsi_values
