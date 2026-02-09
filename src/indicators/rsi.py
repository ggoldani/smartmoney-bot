"""
RSI (Relative Strength Index) indicator implementation.
Uses Wilder's smoothing method (standard for RSI calculation).
"""
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate RSI using Wilder's smoothing method.

    Args:
        closes: List of closing prices (oldest first)
        period: RSI period (default 14)

    Returns:
        RSI value (0-100) or None if insufficient data

    Formula:
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        - First RS uses simple moving average
        - Subsequent values use Wilder's smoothing: (prev_avg * 13 + current) / 14
    """
    if len(closes) < period + 1:
        logger.debug(f"Insufficient data for RSI: need {period + 1}, got {len(closes)}")
        return None

    # Convert to pandas Series for efficient calculation
    df = pd.DataFrame({'close': closes})

    # Calculate price changes
    df['change'] = df['close'].diff()

    # Separate gains and losses
    df['gain'] = df['change'].apply(lambda x: x if x > 0 else 0)
    df['loss'] = df['change'].apply(lambda x: abs(x) if x < 0 else 0)

    # Calculate initial average gain/loss (SMA for first period)
    avg_gain = df['gain'].iloc[1:period + 1].mean()
    avg_loss = df['loss'].iloc[1:period + 1].mean()

    # Apply Wilder's smoothing for subsequent values
    for i in range(period + 1, len(df)):
        avg_gain = (avg_gain * (period - 1) + df['gain'].iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + df['loss'].iloc[i]) / period

    # Calculate RS and RSI
    if avg_loss == 0:
        # Avoid division by zero (all gains, no losses)
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return round(rsi, 2)


def fetch_recent_candles_for_rsi(symbol: str, interval: str, period: int = 14) -> List[float]:
    """
    Fetch recent closed candles from database for RSI calculation.

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1h", "4h", "1d")
        period: RSI period (need period + 1 candles minimum)

    Returns:
        List of closing prices (oldest first), empty if insufficient data
    """
    from src.storage.db import SessionLocal
    from src.storage.models import Candle
    from sqlalchemy import and_

    # Fetch last (period + 100) candles to ensure sufficient historical data
    # +100 buffer for RMA convergence (TradingView compatibility, needs ~100+ candles)
    limit = period + 100

    try:
        with SessionLocal() as session:
            candles = session.query(Candle).filter(
                and_(
                    Candle.symbol == symbol,
                    Candle.interval == interval
                )
            ).order_by(Candle.open_time.desc()).limit(limit).all()

            if not candles:
                return []

            # Reverse to get oldest first
            candles = list(reversed(candles))

            # Extract close prices
            closes = [c.close for c in candles]

            return closes
    except Exception as e:
        logger.error(f"Failed to fetch candles for RSI {symbol} {interval}: {e}")
        return []


def analyze_rsi(
    symbol: str,
    interval: str,
    overbought: float = 70,
    oversold: float = 30,
    period: int = 14,
    extreme_overbought: float = 85,
    extreme_oversold: float = 15,
    _use_config: bool = True
) -> Optional[Dict]:
    """
    Analyze RSI for given symbol/interval and check if overbought/oversold.
    Now supports 2 levels: normal (70/30) and EXTREME (85/15).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1h", "4h", "1d")
        overbought: RSI threshold for overbought (default 70)
        oversold: RSI threshold for oversold (default 30)
        period: RSI period (default 14)
        extreme_overbought: RSI threshold for EXTREME overbought (default 85)
        extreme_oversold: RSI threshold for EXTREME oversold (default 15)
        _use_config: Internal flag to load values from config.yaml (default True)

    Returns:
        Dict with analysis result or None if insufficient data
        Example:
        {
            "symbol": "BTCUSDT",
            "interval": "4h",
            "rsi": 75.3,
            "overbought": True,
            "oversold": False,
            "condition": "OVERBOUGHT",  # or "OVERSOLD" or "EXTREME_OVERBOUGHT" or "EXTREME_OVERSOLD" or "NORMAL"
            "price": 67420.50
        }
    """
    # Load from config if available (for production use)
    if _use_config:
        try:
            from src.config import get_rsi_config
            config = get_rsi_config()
            period = config.get('period', period)
            overbought = config.get('overbought', overbought)
            oversold = config.get('oversold', oversold)
            extreme_overbought = config.get('extreme_overbought', extreme_overbought)
            extreme_oversold = config.get('extreme_oversold', extreme_oversold)
        except ImportError:
            # Fallback if config can't be loaded (shouldn't happen in production)
            logger.debug("Could not load RSI config, using function parameters")

    # Fetch recent candles
    closes = fetch_recent_candles_for_rsi(symbol, interval, period)

    if len(closes) < period + 1:
        logger.warning(f"Insufficient data for RSI {symbol} {interval}: need {period + 1}, got {len(closes)}")
        return None

    # Calculate RSI
    rsi = calculate_rsi(closes, period)

    if rsi is None:
        return None

    # Determine condition (check EXTREME first, then normal)
    is_overbought = False
    is_oversold = False
    condition = "NORMAL"

    # Check EXTREME conditions first
    if rsi >= extreme_overbought:
        condition = "EXTREME_OVERBOUGHT"
        is_overbought = True
    elif rsi <= extreme_oversold:
        condition = "EXTREME_OVERSOLD"
        is_oversold = True
    # Check normal conditions
    elif rsi >= overbought:
        condition = "OVERBOUGHT"
        is_overbought = True
    elif rsi <= oversold:
        condition = "OVERSOLD"
        is_oversold = True

    # Get current price (last close)
    current_price = closes[-1]

    result = {
        "symbol": symbol,
        "interval": interval,
        "rsi": rsi,
        "overbought": is_overbought,
        "oversold": is_oversold,
        "condition": condition,
        "price": current_price
    }

    logger.debug(f"RSI analysis {symbol} {interval}: RSI={rsi:.2f} ({condition})")

    return result


def analyze_rsi_all_timeframes(
    symbol: str,
    timeframes: List[str],
    overbought: float = 70,
    oversold: float = 30,
    period: int = 14
) -> List[Dict]:
    """
    Analyze RSI across multiple timeframes for multi-TF detection.

    Args:
        symbol: Trading pair
        timeframes: List of intervals to analyze
        overbought: RSI overbought threshold
        oversold: RSI oversold threshold
        period: RSI period

    Returns:
        List of analysis results (only critical conditions)
        Example: [
            {"interval": "1h", "rsi": 75, "condition": "OVERBOUGHT", ...},
            {"interval": "4h", "rsi": 72, "condition": "OVERBOUGHT", ...}
        ]
    """
    critical_results = []

    for interval in timeframes:
        result = analyze_rsi(symbol, interval, overbought, oversold, period)

        if result and result["condition"] != "NORMAL":
            critical_results.append(result)

    return critical_results
