# -*- coding: utf-8 -*-
"""
Real-time breakout detection.
Detects when current price breaks previous candle's high/low.
"""
from typing import Optional, Dict
from loguru import logger
from src.storage.db import SessionLocal
from src.storage.models import Candle


def get_previous_candle(symbol: str, interval: str, current_open_time: int) -> Optional[Dict]:
    """
    Get the previous closed candle before the current one.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1d", "1w")
        current_open_time: Open time of current candle in ms

    Returns:
        Dict with candle data or None if not found
    """
    try:
        with SessionLocal() as session:
            candle = session.query(Candle).filter(
                Candle.symbol == symbol,
                Candle.interval == interval,
                Candle.open_time < current_open_time,
                Candle.is_closed == 1  # Only closed candles
            ).order_by(Candle.open_time.desc()).first()

            if not candle:
                return None

            return {
                "symbol": candle.symbol,
                "interval": candle.interval,
                "open_time": candle.open_time,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
            }
    except Exception as e:
        logger.error(f"Failed to get previous candle {symbol} {interval}: {e}")
        return None


def check_breakout(symbol: str, interval: str, current_price: float,
                   current_open_time: int, margin_pct: float = 0.1) -> Optional[Dict]:
    """
    Check if current price is breaking previous candle's high or low.

    Args:
        symbol: Trading symbol
        interval: Timeframe
        current_price: Current market price
        current_open_time: Open time of current candle
        margin_pct: Margin percentage to avoid false positives (e.g., 0.1 = 0.1%)

    Returns:
        Dict with breakout data if detected, None otherwise:
        {
            "type": "BULL" | "BEAR",
            "symbol": "BTCUSDT",
            "interval": "1d",
            "price": 67500.00,
            "prev_high": 67000.00,  # if BULL
            "prev_low": 66000.00,   # if BEAR
            "change_pct": 0.75
        }
    """
    prev_candle = get_previous_candle(symbol, interval, current_open_time)
    if not prev_candle:
        return None

    # Apply margin to prevent noise (e.g., 0.1% above high or below low)
    margin_up = 1 + (margin_pct / 100)      # For bull: 1.001 (0.1% above)
    margin_down = 1 - (margin_pct / 100)    # For bear: 0.999 (0.1% below)

    # Bullish breakout: current price > previous high + margin
    if current_price > prev_candle["high"] * margin_up:
        change_pct = ((current_price - prev_candle["high"]) / prev_candle["high"]) * 100
        return {
            "type": "BULL",
            "symbol": symbol,
            "interval": interval,
            "price": current_price,
            "prev_high": prev_candle["high"],
            "change_pct": change_pct,
        }

    # Bearish breakdown: current price < previous low - margin
    if current_price < prev_candle["low"] * margin_down:
        change_pct = ((prev_candle["low"] - current_price) / prev_candle["low"]) * 100
        return {
            "type": "BEAR",
            "symbol": symbol,
            "interval": interval,
            "price": current_price,
            "prev_low": prev_candle["low"],
            "change_pct": change_pct,
        }

    return None
