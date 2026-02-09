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


def all_base_timeframes():
    return ["4h", "1d", "1w", "1M"]
