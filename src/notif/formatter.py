# -*- coding: utf-8 -*-
"""
Brazilian formatting utilities for alerts.
Handles timezone conversion, number formatting, and date formatting.
"""
from datetime import datetime, timezone
from typing import Optional
import pytz


def format_price_br(price: float) -> str:
    """
    Format price in Brazilian format: $67.420,50
    (dot for thousands, comma for decimals)

    Args:
        price: Price value (e.g., 67420.50)

    Returns:
        Formatted string (e.g., "$67.420,50")
    """
    # Format with 2 decimal places
    formatted = f"{price:,.2f}"

    # Replace default formatting (comma for thousands, dot for decimals)
    # with BR format (dot for thousands, comma for decimals)
    formatted = formatted.replace(",", "TEMP")
    formatted = formatted.replace(".", ",")
    formatted = formatted.replace("TEMP", ".")

    return f"${formatted}"


def format_percentage_br(value: float) -> str:
    """
    Format percentage in Brazilian format: 0,15%

    Args:
        value: Percentage value (e.g., 0.15 for 0.15%)

    Returns:
        Formatted string (e.g., "0,15%")
    """
    formatted = f"{value:.2f}".replace(".", ",")
    return f"{formatted}%"


def get_brazil_time() -> datetime:
    """
    Get current time in BRT (Brazil Time = UTC-3).

    Returns:
        datetime object in America/Sao_Paulo timezone
    """
    brt = pytz.timezone('America/Sao_Paulo')
    return datetime.now(brt)


def format_datetime_br(dt: Optional[datetime] = None) -> str:
    """
    Format datetime in Brazilian format: 11/11/2025 11:30 BRT

    Args:
        dt: datetime object (if None, uses current time)

    Returns:
        Formatted string (e.g., "11/11/2025 11:30 BRT")
    """
    if dt is None:
        dt = get_brazil_time()
    elif dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=timezone.utc)
        brt = pytz.timezone('America/Sao_Paulo')
        dt = dt.astimezone(brt)
    elif not (hasattr(dt.tzinfo, 'zone') and dt.tzinfo.zone == 'America/Sao_Paulo'):
        # Convert to BRT if not already in BRT
        brt = pytz.timezone('America/Sao_Paulo')
        dt = dt.astimezone(brt)

    # Format: DD/MM/YYYY HH:MM BRT
    return dt.strftime("%d/%m/%Y %H:%M BRT")


def format_timestamp_br(timestamp_ms: int) -> str:
    """
    Format Unix timestamp (milliseconds) to Brazilian format.

    Args:
        timestamp_ms: Unix timestamp in milliseconds

    Returns:
        Formatted string (e.g., "11/11/2025 11:30 BRT")
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    return format_datetime_br(dt)


def format_rsi_value(rsi: float) -> str:
    """
    Format RSI value in Brazilian format: 75,30

    Args:
        rsi: RSI value (0-100)

    Returns:
        Formatted string (e.g., "75,30")
    """
    return f"{rsi:.2f}".replace(".", ",")


def format_symbol_display(symbol: str) -> str:
    """
    Format symbol for display (e.g., BTCUSDT -> BTC/USDT).

    Args:
        symbol: Trading pair symbol

    Returns:
        Formatted symbol
    """
    # Simple heuristic: split common pairs
    if symbol.endswith("USDT"):
        base = symbol[:-4]
        return f"{base}/USDT"
    elif symbol.endswith("BTC"):
        base = symbol[:-3]
        return f"{base}/BTC"
    elif symbol.endswith("ETH"):
        base = symbol[:-3]
        return f"{base}/ETH"
    else:
        return symbol


def format_timeframe_display(interval: str) -> str:
    """
    Format timeframe for display in Portuguese.

    Args:
        interval: Binance interval (e.g., "1h", "4h", "1d", "1w")

    Returns:
        Human-readable timeframe in Portuguese
    """
    from src.utils.timeframes import TIMEFRAME_DISPLAY
    return TIMEFRAME_DISPLAY.get(interval, interval)
