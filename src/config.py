import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Environment variables (secrets)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_CHAT_ID = os.getenv("CHANNEL_CHAT_ID", "")
ADMIN_CHANNEL_ID = os.getenv("ADMIN_CHANNEL_ID", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CONFIG_FILE = os.getenv("CONFIG_FILE", "./configs/free.yaml")

# Legacy env vars (for backward compatibility)
ENABLE_CHARTS = os.getenv("ENABLE_CHARTS", "false").lower() == "true"
USE_COINGECKO_FOR_BTCD = os.getenv("USE_COINGECKO_FOR_BTCD", "true").lower() == "true"


class ConfigLoader:
    """Loads and validates YAML configuration with environment variable substitution."""

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
        self._load()

    def _load(self):
        """Load YAML config file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

        # Validate required sections
        required_sections = ['bot', 'telegram', 'symbols', 'indicators', 'alerts']
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Missing required config section: {section}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value by dot-notation path.
        Example: config.get('bot.version') -> '1.0.0'
        """
        keys = key_path.split('.')
        value = self._config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        # Handle environment variable substitution in strings
        if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
            env_var = value[2:-1]
            return os.getenv(env_var, default)

        return value

    @property
    def raw(self) -> Dict[str, Any]:
        """Get raw config dict."""
        return self._config


# Global config instance (lazy-loaded)
_config_instance: Optional[ConfigLoader] = None


def get_config() -> ConfigLoader:
    """Get global config instance (singleton pattern)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigLoader(CONFIG_FILE)
    return _config_instance


def reload_config():
    """Reload config from file (useful for hot reload in future)."""
    global _config_instance
    _config_instance = ConfigLoader(CONFIG_FILE)


# Helper functions for common config access
def get_bot_version() -> str:
    return get_config().get('bot.version', '1.0.0')


def get_bot_tier() -> str:
    return get_config().get('bot.tier', 'free')


def get_bot_name() -> str:
    return get_config().get('bot.name', 'SmartMoney Bot')


def get_symbols() -> List[Dict[str, Any]]:
    return get_config().get('symbols', [])


def get_timeframes_for_symbol(symbol: str) -> List[str]:
    """Get timeframes for specific symbol."""
    symbols = get_symbols()
    for sym_config in symbols:
        if sym_config.get('name') == symbol:
            return sym_config.get('timeframes', [])
    return []


def is_indicator_enabled(indicator_name: str) -> bool:
    return get_config().get(f'indicators.{indicator_name}.enabled', False)


def get_rsi_config() -> Dict[str, Any]:
    """Get RSI config with validation and safe defaults."""
    rsi_config = get_config().get('indicators.rsi', {})

    # Validate and apply safe defaults
    if not isinstance(rsi_config, dict):
        rsi_config = {}

    # Ensure all critical fields exist with safe defaults
    rsi_config.setdefault('period', 14)
    rsi_config.setdefault('overbought', 70)
    rsi_config.setdefault('oversold', 30)
    rsi_config.setdefault('extreme_overbought', 75)
    rsi_config.setdefault('extreme_oversold', 25)
    rsi_config.setdefault('timeframes', [])
    rsi_config.setdefault('alert_on_touch', True)

    # Validate thresholds (safety checks)
    try:
        period = int(rsi_config.get('period', 14))
        if period < 2 or period > 100:
            rsi_config['period'] = 14
        else:
            rsi_config['period'] = period
    except (ValueError, TypeError):
        rsi_config['period'] = 14

    try:
        overbought = float(rsi_config.get('overbought', 70))
        if overbought <= 50 or overbought >= 100:
            overbought = 70
        rsi_config['overbought'] = overbought
    except (ValueError, TypeError):
        rsi_config['overbought'] = 70

    try:
        oversold = float(rsi_config.get('oversold', 30))
        if oversold <= 0 or oversold >= 50:
            oversold = 30
        rsi_config['oversold'] = oversold
    except (ValueError, TypeError):
        rsi_config['oversold'] = 30

    try:
        extreme_overbought = float(rsi_config.get('extreme_overbought', 85))
        if extreme_overbought <= rsi_config['overbought'] or extreme_overbought >= 100:
            extreme_overbought = 85
        rsi_config['extreme_overbought'] = extreme_overbought
    except (ValueError, TypeError):
        rsi_config['extreme_overbought'] = 85

    try:
        extreme_oversold = float(rsi_config.get('extreme_oversold', 15))
        if extreme_oversold >= rsi_config['oversold'] or extreme_oversold <= 0:
            extreme_oversold = 15
        rsi_config['extreme_oversold'] = extreme_oversold
    except (ValueError, TypeError):
        rsi_config['extreme_oversold'] = 15

    return rsi_config


def get_breakout_config() -> Dict[str, Any]:
    return get_config().get('indicators.breakout', {})


def get_alert_config() -> Dict[str, Any]:
    return get_config().get('alerts', {})


def should_send_startup_message() -> bool:
    return get_config().get('telegram.startup_message', True)


def should_send_shutdown_message() -> bool:
    return get_config().get('telegram.shutdown_message', True)


def get_backfill_config() -> Dict[str, Any]:
    return get_config().get('backfill', {})


def get_database_cleanup_config() -> Dict[str, Any]:
    return get_config().get('database.cleanup', {})


def get_logging_config() -> Dict[str, Any]:
    return get_config().get('logging', {})


def get_daily_summary_config() -> Dict[str, Any]:
    """Get daily summary configuration with safe defaults."""
    return {
        'enabled': get_config().get('alerts.daily_summary.enabled', False),
        'send_time_brt': get_config().get('alerts.daily_summary.send_time_brt', '21:00'),
        'send_window_minutes': get_config().get('alerts.daily_summary.send_window_minutes', 5)
    }


def get_divergence_config() -> Dict[str, Any]:
    """Get divergence detection configuration with safe defaults."""
    div_config = get_config().get('indicators.divergence', {})

    if not isinstance(div_config, dict):
        div_config = {}

    div_config.setdefault('enabled', True)
    div_config.setdefault('timeframes', ['4h', '1d', '1w'])
    div_config.setdefault('lookback', 20)
    div_config.setdefault('debug_divergence', False)

    return div_config


# Validate critical env vars on import
if not BOT_TOKEN:
    import sys
    print("WARNING: BOT_TOKEN not set - running in dry-run mode")
    # Don't exit, allow dry-run mode

if not CHANNEL_CHAT_ID:
    import sys
    print("WARNING: CHANNEL_CHAT_ID not set - alerts will be logged only")

# Validate Fear & Greed API key
COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY", "").strip()
if not COINMARKETCAP_API_KEY:
    print("WARNING: COINMARKETCAP_API_KEY not set - Fear & Greed Index will show 'Indisponível'")
