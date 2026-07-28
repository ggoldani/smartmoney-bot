"""
Bollinger Bands indicator and trend-follow breach detection.
BB(period, std_mult) calculated on CLOSED candles only (avoids self-healing).
"""
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger


def calculate_bb(closes: List[float], period: int = 21, std_mult: float = 2.0) -> Optional[Dict[str, float]]:
    """
    Calculate Bollinger Bands using population std (ddof=0, TradingView-compatible).

    Args:
        closes: List of closing prices (oldest order), CLOSED candles only
        period: SMA period (default 21)
        std_mult: Standard deviation multiplier (default 2.0)

    Returns:
        Dict with 'upper', 'middle', 'lower' (last values) or None if insufficient data.
        Example: {"upper": 105.0, "middle": 100.0, "lower": 95.0}
    """
    if len(closes) < period:
        logger.debug(f"Insufficient data for BB: need {period}, got {len(closes)}")
        return None

    df = pd.DataFrame({"close": closes})
    df["sma"] = df["close"].rolling(window=period).mean()
    df["std"] = df["close"].rolling(window=period).std(ddof=0)  # population std

    last_row = df.iloc[-1]
    if pd.isna(last_row["sma"]) or pd.isna(last_row["std"]):
        return None

    middle = float(last_row["sma"])
    std = float(last_row["std"])
    upper = middle + std_mult * std
    lower = middle - std_mult * std

    return {"upper": upper, "middle": middle, "lower": lower}


def fetch_closed_candles_for_bb(symbol: str, interval: str, period: int = 21) -> List[float]:
    """
    Fetch recent CLOSED candles from database for BB calculation.
    Filters is_closed=1 to avoid self-healing (band shifting by current forming candle).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1d")
        period: Number of closed candles needed

    Returns:
        List of closing prices (oldest first), empty if insufficient data.
    """
    from src.storage.db import SessionLocal
    from src.storage.models import Candle
    from sqlalchemy import and_

    try:
        with SessionLocal() as session:
            candles = session.query(Candle).filter(
                and_(
                    Candle.symbol == symbol,
                    Candle.interval == interval,
                    Candle.is_closed == 1
                )
            ).order_by(Candle.open_time.desc()).limit(period).all()

            if not candles:
                return []

            candles = list(reversed(candles))
            return [c.close for c in candles]
    except Exception as e:
        logger.error(f"Failed to fetch closed candles for BB {symbol} {interval}: {e}")
        return []


def check_bb_breach(
    symbol: str,
    interval: str,
    current_price: float,
    period: int = 21,
    std_mult: float = 2.0,
    buffer_pct: float = 0.5,
) -> Optional[Dict]:
    """
    Check if current price breaches Bollinger Bands (with buffer).

    Args:
        symbol: Trading pair
        interval: Timeframe for BB calculation
        current_price: Live/tick price to check against bands
        period: BB period
        std_mult: BB std multiplier
        buffer_pct: Buffer percentage (0.5 = 0.5%). Applied as:
                    upper_effective = upper * (1 + buffer/100)
                    lower_effective = lower * (1 - buffer/100)

    Returns:
        Dict with breach data or None:
        {
            "type": "UPPER" | "LOWER",
            "symbol": "BTCUSDT",
            "interval": "1d",
            "price": 67500.0,
            "bb_upper": 105.0,   # raw band value (if UPPER)
            "bb_lower": 95.0,    # raw band value (if LOWER)
            "bb_middle": 100.0,
            "effective_band": 105.525  # the threshold actually crossed
        }
    """
    closes = fetch_closed_candles_for_bb(symbol, interval, period)
    if len(closes) < period:
        logger.warning(f"Insufficient closed candles for BB {symbol} {interval}: {len(closes)}/{period}")
        return None

    bands = calculate_bb(closes, period, std_mult)
    if not bands:
        return None

    buffer_mult = 1 + (buffer_pct / 100)
    upper_effective = bands["upper"] * buffer_mult
    lower_effective = bands["lower"] * (2 - buffer_mult)  # = lower * (1 - buffer/100)

    # Breach upper band
    if current_price > upper_effective:
        return {
            "type": "UPPER",
            "symbol": symbol,
            "interval": interval,
            "price": current_price,
            "bb_upper": bands["upper"],
            "bb_middle": bands["middle"],
            "effective_band": upper_effective,
        }

    # Breach lower band
    if current_price < lower_effective:
        return {
            "type": "LOWER",
            "symbol": symbol,
            "interval": interval,
            "price": current_price,
            "bb_lower": bands["lower"],
            "bb_middle": bands["middle"],
            "effective_band": lower_effective,
        }

    # Price inside bands (between raw lower and raw upper, no buffer)
    return None


def is_price_inside_bands(
    symbol: str,
    interval: str,
    current_price: float,
    period: int = 21,
    std_mult: float = 2.0,
) -> bool:
    """
    Check if price is INSIDE the raw Bollinger Bands (between lower and upper, no buffer).
    Used for anti-spam state reset: when price returns inside, BB alert state resets.

    Args:
        symbol: Trading pair
        interval: Timeframe
        current_price: Live/tick price
        period: BB period
        std_mult: BB std multiplier

    Returns:
        True if lower < price < upper (strict, raw bands without buffer).
    """
    closes = fetch_closed_candles_for_bb(symbol, interval, period)
    if len(closes) < period:
        return False  # can't determine, don't reset

    bands = calculate_bb(closes, period, std_mult)
    if not bands:
        return False

    return bands["lower"] < current_price < bands["upper"]
