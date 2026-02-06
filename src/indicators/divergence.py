"""RSI Divergence detection (bullish/bearish) - detects pivots by RSI extremes."""
from typing import Optional, List
from loguru import logger


def is_rsi_bullish_pivot(rsi_values: List[Optional[float]]) -> bool:
    """
    Check if middle RSI (index 1) is a bullish pivot (lowest RSI).

    Args:
        rsi_values: List of 3 RSI values [rsi0, rsi1, rsi2] (oldest first)

    Returns:
        True if rsi[1] < rsi[0] AND rsi[1] < rsi[2]
    """
    if len(rsi_values) != 3:
        return False
    if any(r is None for r in rsi_values):
        return False
    return rsi_values[1] < rsi_values[0] and rsi_values[1] < rsi_values[2]


def is_rsi_bearish_pivot(rsi_values: List[Optional[float]]) -> bool:
    """
    Check if middle RSI (index 1) is a bearish pivot (highest RSI).

    Args:
        rsi_values: List of 3 RSI values [rsi0, rsi1, rsi2] (oldest first)

    Returns:
        True if rsi[1] > rsi[0] AND rsi[1] > rsi[2]
    """
    if len(rsi_values) != 3:
        return False
    if any(r is None for r in rsi_values):
        return False
    return rsi_values[1] > rsi_values[0] and rsi_values[1] > rsi_values[2]


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

    Args:
        current_price: Price of current pivot (close)
        current_rsi: RSI of current pivot
        prev_price: Price of previous pivot (close)
        prev_rsi: RSI of previous pivot
        div_type: "BULLISH" or "BEARISH"
        bullish_rsi_max: Maximum RSI value for bullish divergence (default: 40)
        bearish_rsi_min: Minimum RSI value for bearish divergence (default: 60)

    Returns:
        "BULLISH" or "BEARISH" if divergence detected, None otherwise
    """
    if div_type == "BULLISH":
        # Bullish: Current price < previous price (new minimum)
        # AND current RSI > previous RSI (RSI didn't hit new low)
        # AND both RSI values < bullish_rsi_max
        if (current_price < prev_price and
            current_rsi > prev_rsi and
            current_rsi < bullish_rsi_max and
            prev_rsi < bullish_rsi_max):
            return "BULLISH"

    elif div_type == "BEARISH":
        # Bearish: Current price > previous price (new maximum)
        # AND current RSI < previous RSI (RSI didn't hit new high)
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
    lookback: int = 20
) -> List:
    """
    Fetch recent closed candles for divergence detection.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "4h", "1d", "1w")
        lookback: Number of candles to fetch (default 20)

    Returns:
        List of Candle ORM objects (oldest first), or empty list if failed
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

            # Return oldest -> newest (expected by RSI calc and pivot logic)
            return list(reversed(candles))

    except Exception as e:
        logger.error(f"Failed to fetch divergence candles {symbol} {interval}: {e}")
        return []


def calculate_rsi_for_candles(closes: List[float]) -> List[Optional[float]]:
    """
    Calculate RSI(14) for each candle using incremental approach.

    Args:
        closes: List of closing prices (oldest first)

    Returns:
        List of RSI values (oldest first), None for first 14 candles
    """
    from src.indicators.rsi import calculate_rsi

    rsi_values = []
    for i in range(len(closes)):
        if i < 14:  # Need 14 candles minimum
            rsi_values.append(None)
        else:
            # Calculate RSI up to current index
            rsi = calculate_rsi(closes[:i + 1], period=14)
            rsi_values.append(rsi)

    return rsi_values
