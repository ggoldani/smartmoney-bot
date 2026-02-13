"""
Timeframe definitions and display mappings.
Single source of truth for all timeframe-related constants.
"""

VALID_TF = {"4h": "4h", "1d": "1d", "1w": "1w", "1M": "1M"}

# Display names in Portuguese (used by formatter and templates)
TIMEFRAME_DISPLAY = {
    "1m": "1 minuto",
    "5m": "5 minutos",
    "15m": "15 minutos",
    "30m": "30 minutos",
    "1h": "1 hora",
    "2h": "2 horas",
    "4h": "4 horas",
    "1d": "1 dia",
    "3d": "3 dias",
    "1w": "1 semana",
    "1M": "1 mês",
}

# Interval duration in milliseconds (matches Binance open_time format)
# 1M uses 30-day approximation — acceptable for pivot range checks [5, 60]
INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,
}


def interval_to_ms(interval: str) -> int:
    """Convert interval string to duration in milliseconds.

    Args:
        interval: Binance-style interval string (e.g., "4h", "1d", "1w", "1M")

    Returns:
        Duration of one candle in milliseconds.

    Raises:
        ValueError: If interval is not recognized.
    """
    if interval not in INTERVAL_MS:
        raise ValueError(f"Unknown interval: {interval}")
    return INTERVAL_MS[interval]


def all_base_timeframes():
    return ["4h", "1d", "1w", "1M"]
