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
    return get_config().get('indicators.rsi', {})


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


# Validate critical env vars on import
if not BOT_TOKEN:
    import sys
    print("WARNING: BOT_TOKEN not set - running in dry-run mode")
    # Don't exit, allow dry-run mode

if not CHANNEL_CHAT_ID:
    import sys
    print("WARNING: CHANNEL_CHAT_ID not set - alerts will be logged only")
